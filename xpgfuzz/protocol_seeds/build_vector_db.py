from __future__ import annotations

import argparse
import os
import shutil
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:  # allow both "python -m xpgfuzz.protocol_seeds.build_vector_db" and direct script execution
    from .env_config import require_llm_api_key, get_embedding_base_url, get_embedding_model
    from .kb_clean import clean_markdown
    from .semantic_chunker import atoms_to_chunks, parse_markdown_atoms
except Exception:  # pragma: no cover
    from env_config import require_llm_api_key, get_embedding_base_url, get_embedding_model
    from kb_clean import clean_markdown
    from semantic_chunker import atoms_to_chunks, parse_markdown_atoms


@dataclass(frozen=True)
class SourceMeta:
    protocol_family: str
    implementation: str
    source_file: str  # path relative to deepwikis root
    document_path: str  # heading stack joined
    start_line: int
    end_line: int


@dataclass(frozen=True)
class KBChunk:
    """
    A single chunk to be embedded and stored.
    """

    chunk_id: str
    text: str
    metadata: Dict[str, object]


def _infer_meta(deepwikis_root: Path, md_path: Path) -> Tuple[str, str, str]:
    rel = md_path.relative_to(deepwikis_root).as_posix()
    parts = rel.split("/")
    protocol_family = parts[0] if len(parts) >= 1 else "unknown"
    implementation = parts[1] if len(parts) >= 2 else "unknown"
    return protocol_family, implementation, rel


def iter_markdown_files(deepwikis_root: Path) -> Iterable[Path]:
    yield from deepwikis_root.rglob("*.md")


def build_documents_from_deepwikis(
    deepwikis_root: Path,
    l_max: int = 1024,
    l_overlap: int = 50,
    do_clean: bool = True,
) -> List[KBChunk]:
    docs: List[KBChunk] = []

    for md_path in sorted(iter_markdown_files(deepwikis_root)):
        try:
            raw = md_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        text = clean_markdown(raw) if do_clean else raw
        atoms = parse_markdown_atoms(text)
        chunks = atoms_to_chunks(atoms, l_max=l_max, l_overlap=l_overlap)

        protocol_family, implementation, rel = _infer_meta(deepwikis_root, md_path)

        for idx, ch in enumerate(chunks):
            doc_path = " > ".join(ch.heading_path) if ch.heading_path else ""
            meta = SourceMeta(
                protocol_family=protocol_family,
                implementation=implementation,
                source_file=rel,
                document_path=doc_path,
                start_line=ch.start_line,
                end_line=ch.end_line,
            )

            # Ensure metadata values are Chroma-friendly primitives.
            m: Dict[str, object] = asdict(meta)
            m["chunk_index"] = idx
            h = hashlib.sha1(f"{rel}:{idx}".encode("utf-8")).hexdigest()[:16]
            chunk_id = f"{protocol_family}:{implementation}:{h}"
            docs.append(KBChunk(chunk_id=chunk_id, text=ch.text, metadata=m))

    return docs


def build_chroma(
    documents: List[KBChunk],
    persist_dir: Path,
    collection_name: str,
    reset: bool,
    batch_size: int,
) -> None:
    try:
        import chromadb  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency: chromadb. Install with: pip install chromadb"
        ) from e

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency: openai. Install with: pip install openai"
        ) from e

    if reset and persist_dir.exists():
        shutil.rmtree(persist_dir)

    api_key = require_llm_api_key()
    base_url = get_embedding_base_url()
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    chroma = chromadb.PersistentClient(path=str(persist_dir))
    collection = chroma.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    model = get_embedding_model()

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        texts = [x.text for x in batch]
        ids = [x.chunk_id for x in batch]
        metas = [x.metadata for x in batch]

        emb = client.embeddings.create(model=model, input=texts)
        vectors = [d.embedding for d in emb.data]

        collection.add(ids=ids, documents=texts, metadatas=metas, embeddings=vectors)

    print(f"[kb] persist_dir={persist_dir}")
    print(f"[kb] collection={collection_name}")
    print(f"[kb] vectors={collection.count()}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build semantic-chunked DeepWiki KB into Chroma (HNSW).")
    ap.add_argument(
        "--deepwikis-dir",
        default=str(Path(__file__).parent / "deepwikis"),
        help="DeepWiki root directory (default: xpgfuzz/protocol_seeds/deepwikis)",
    )
    ap.add_argument(
        "--persist-dir",
        default=os.getenv("XPGFUZZ_CHROMA_DIR", str(Path(__file__).parent / "chroma_db_protocols")),
        help="Chroma persist directory",
    )
    ap.add_argument(
        "--collection",
        default=os.getenv("XPGFUZZ_CHROMA_COLLECTION", "protocols_wiki"),
        help="Chroma collection name",
    )
    ap.add_argument("--lmax", type=int, default=1024, help="Max chunk length (chars)")
    ap.add_argument("--overlap", type=int, default=50, help="Chunk overlap (chars)")
    ap.add_argument("--no-clean", action="store_true", help="Disable markdown cleaning")
    ap.add_argument("--reset", action="store_true", help="Delete persist-dir before building")
    ap.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    args = ap.parse_args(argv)

    deepwikis_root = Path(args.deepwikis_dir).resolve()
    if not deepwikis_root.exists():
        raise FileNotFoundError(f"deepwikis dir not found: {deepwikis_root}")

    documents = build_documents_from_deepwikis(
        deepwikis_root=deepwikis_root,
        l_max=args.lmax,
        l_overlap=args.overlap,
        do_clean=not args.no_clean,
    )

    if not documents:
        print("[kb] No documents produced (empty deepwikis?).")
        return 1

    persist_dir = Path(args.persist_dir).resolve()
    build_chroma(
        documents=documents,
        persist_dir=persist_dir,
        collection_name=args.collection,
        reset=args.reset,
        batch_size=args.batch_size,
    )

    print(f"[kb] done: chunks={len(documents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

