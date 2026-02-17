from __future__ import annotations

import argparse
import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:  # allow both module and script execution
    from .env_config import require_llm_api_key, get_llm_base_url, get_llm_model
except Exception:  # pragma: no cover
    from env_config import require_llm_api_key, get_llm_base_url, get_llm_model


_RE_JSON_BLOCK = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    text: str
    metadata: Dict[str, object]


def _load_openai_client():
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Missing dependency: openai. Install with: pip install openai") from e

    api_key = require_llm_api_key()
    base_url = get_llm_base_url()
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def _load_chroma_collection(persist_dir: Path, collection_name: str):
    try:
        import chromadb  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Missing dependency: chromadb. Install with: pip install chromadb") from e

    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_or_create_collection(name=collection_name)


def _embed(client, text: str, model: str) -> List[float]:
    r = client.embeddings.create(model=model, input=[text])
    return r.data[0].embedding


def retrieve(
    *,
    chroma_collection,
    openai_client,
    embedding_model: str,
    query: str,
    top_k: int,
    where: Dict[str, object],
) -> List[RetrievedChunk]:
    q_emb = _embed(openai_client, query, embedding_model)
    res = chroma_collection.query(
        query_embeddings=[q_emb],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas"],
    )

    docs = res.get("documents", [[]])[0] or []
    metas = res.get("metadatas", [[]])[0] or []

    out: List[RetrievedChunk] = []
    for i, (d, m) in enumerate(zip(docs, metas), start=1):
        out.append(RetrievedChunk(source_id=f"S{i}", text=d, metadata=m or {}))
    return out


def extract_present_message_types(sequence: str) -> List[str]:
    """
    Robust-ish command/method extraction.

    Heuristic: take the first token of each non-empty line, normalize to upper-case,
    strip trailing ':' (headers), and ignore obvious non-command lines.
    """
    seq = sequence.replace("\r\n", "\n").replace("\r", "\n")
    present: List[str] = []
    for line in seq.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        # HTTP request line: "GET /path HTTP/1.1"
        tok = s.split()[0] if s.split() else ""
        tok = tok.strip().rstrip(":").upper()
        if not tok:
            continue
        # filter out common non-command tokens
        if tok.startswith("HTTP/") or tok in {"SIP/2.0", "RTSP/1.0"}:
            continue
        if tok.isdigit():
            continue
        present.append(tok)
    # keep stable unique order
    seen = set()
    uniq: List[str] = []
    for x in present:
        if x not in seen:
            uniq.append(x)
            seen.add(x)
    return uniq


def _extract_json_object(text: str) -> Dict[str, object]:
    """
    Best-effort JSON object extractor from an LLM response.
    """
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    m = _RE_JSON_BLOCK.search(text)
    if not m:
        raise ValueError("No JSON object found in response")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("Extracted JSON is not an object")
    return obj


def infer_command_universe(
    *,
    openai_client,
    model: str,
    protocol_family: str,
    implementation: str,
    present: Sequence[str],
    context_chunks: Sequence[RetrievedChunk],
    max_commands: int = 64,
) -> List[str]:
    context = "\n\n".join(
        [
            f"[{c.source_id}] source_file={c.metadata.get('source_file','')} document_path={c.metadata.get('document_path','')}\n{c.text}"
            for c in context_chunks
        ]
    )
    prompt = f"""
You are extracting a canonical list of client request message types (commands/methods) for fuzzing.

Protocol family: {protocol_family}
Implementation: {implementation}

Observed message types in a seed (may be incomplete): {", ".join(present) if present else "(none)"}

Authoritative context (may mention valid commands/methods):
{context}

Return a JSON object with this schema:
{{
  "commands": ["CMD1", "CMD2", ...]
}}

Rules:
- Commands must be UPPERCASE strings.
- Prefer protocol request commands/methods (not internal function names).
- Include at most {max_commands} commands.
""".strip()

    r = openai_client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    out = _extract_json_object(r.choices[0].message.content or "")
    cmds = out.get("commands", [])
    if not isinstance(cmds, list):
        return []
    cleaned: List[str] = []
    for x in cmds:
        if not isinstance(x, str):
            continue
        t = x.strip().upper()
        if not t:
            continue
        cleaned.append(t)
    # stable unique
    seen = set()
    uniq: List[str] = []
    for c in cleaned:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    return uniq[:max_commands]


def choose_missing_set(universe: Sequence[str], present: Sequence[str], k: int) -> List[str]:
    missing = [c for c in universe if c not in set(present)]
    if not missing:
        return []
    if k <= 0:
        return missing
    if len(missing) <= k:
        return missing
    return random.sample(missing, k)


def _format_context(chunks: Sequence[RetrievedChunk]) -> str:
    blocks: List[str] = []
    for c in chunks:
        meta = c.metadata
        blocks.append(
            "\n".join(
                [
                    f"[{c.source_id}] source_file={meta.get('source_file','')} document_path={meta.get('document_path','')} lines={meta.get('start_line','')}-{meta.get('end_line','')}",
                    c.text,
                ]
            )
        )
    return "\n\n".join(blocks)


def validate_evidence_map(evidence_map: object, chunks: Sequence[RetrievedChunk]) -> Tuple[bool, str]:
    if not isinstance(evidence_map, dict):
        return False, "evidence_map is not a JSON object"
    by_id = {c.source_id: c.text for c in chunks}
    for cmd, evids in evidence_map.items():
        if not isinstance(cmd, str):
            return False, "evidence_map key is not a string"
        if not isinstance(evids, list) or not evids:
            return False, f"evidence_map[{cmd}] must be a non-empty list"
        for e in evids:
            if not isinstance(e, dict):
                return False, f"evidence entry for {cmd} is not an object"
            sid = e.get("source_id")
            quote = e.get("quote")
            if sid not in by_id:
                return False, f"invalid source_id in evidence for {cmd}: {sid}"
            if not isinstance(quote, str) or not quote.strip():
                return False, f"missing quote in evidence for {cmd}"
            if quote.strip() not in by_id[sid]:
                return False, f"quote not found in referenced context for {cmd} ({sid})"
    return True, "ok"


def enrich_one_command_react(
    *,
    openai_client,
    chroma_collection,
    embedding_model: str,
    llm_model: str,
    protocol_family: str,
    implementation: str,
    sequence: str,
    target_command: str,
    temperature: float,
    top_k: int,
    max_iters: int,
) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
    """
    ReAct-style loop:
      Retrieve -> Insert -> Validate (with evidence_map) -> repeat on failure.
    """
    where = {"protocol_family": protocol_family, "implementation": implementation}

    last_error: Optional[str] = None
    cur = sequence
    for it in range(1, max_iters + 1):
        query = f"{protocol_family} {implementation} client request {target_command} syntax examples"
        chunks = retrieve(
            chroma_collection=chroma_collection,
            openai_client=openai_client,
            embedding_model=embedding_model,
            query=query,
            top_k=top_k,
            where=where,
        )
        context = _format_context(chunks)

        prompt = f"""
You are a protocol fuzzing seed enrichment agent.

Goal: insert EXACTLY ONE missing message type into the given client request sequence.

Protocol family: {protocol_family}
Implementation: {implementation}
Target command/method to insert: {target_command}

Authoritative context (with Source IDs):
{context}

Current sequence (raw):
<<<SEQUENCE
{cur}
SEQUENCE

Return a JSON object with the schema:
{{
  "enriched_sequence": "<raw sequence only>",
  "evidence_map": {{
    "{target_command}": [
      {{"source_id": "S1", "quote": "<verbatim substring from that source>"}}
    ]
  }}
}}

Rules:
- Output MUST be valid JSON (no markdown).
- enriched_sequence must be ONLY the raw sequence content (no code fences).
- Insert {target_command} in a logically valid position (do not delete existing lines).
- evidence_map.quote MUST be copied verbatim from the referenced source chunk.
- Only cite sources from S1..S{len(chunks)}.
""".strip()

        if last_error:
            prompt += f"\n\nPrevious attempt failed validation: {last_error}\nFix and retry."

        r = openai_client.chat.completions.create(
            model=llm_model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = r.choices[0].message.content or ""
        try:
            obj = _extract_json_object(raw)
        except Exception as e:
            last_error = f"JSON parse failed: {e}"
            continue

        enriched = obj.get("enriched_sequence")
        evidence_map = obj.get("evidence_map")
        if not isinstance(enriched, str) or not enriched.strip():
            last_error = "enriched_sequence missing/empty"
            continue
        if "```" in enriched:
            last_error = "enriched_sequence contains markdown code fences"
            continue

        # Basic command presence check
        present = extract_present_message_types(enriched)
        if target_command.upper() not in set(present):
            last_error = f"target command not present in enriched_sequence: {target_command}"
            continue

        ok, msg = validate_evidence_map(evidence_map, chunks)
        if not ok:
            last_error = msg
            continue

        return enriched, evidence_map  # success

    return None, None


def write_output_sequence(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Paper-aligned seed enricher (RAG + ReAct + evidence).")
    ap.add_argument("--protocol-family", required=True, help="e.g., SMTP / FTP / HTTP / RTSP / SIP / DAAP")
    ap.add_argument("--implementation", required=True, help="e.g., Exim / proftpd / forked-daapd")
    ap.add_argument("--input", required=True, help="Seed file or directory")
    ap.add_argument("--output", required=True, help="Output file or directory")
    ap.add_argument("--chroma-dir", default=os.getenv("XPGFUZZ_CHROMA_DIR", "xpgfuzz/protocol_seeds/chroma_db_protocols"))
    ap.add_argument("--collection", default=os.getenv("XPGFUZZ_CHROMA_COLLECTION", "protocols_wiki"))
    ap.add_argument("--embedding-model", default=os.getenv("XPGFUZZ_EMBEDDING_MODEL", "text-embedding-3-small"))
    ap.add_argument("--llm-model", default=get_llm_model(default="DeepSeek-V3.1"))
    ap.add_argument("--temperature", type=float, default=0.5)
    ap.add_argument("--topk", type=int, default=2)
    ap.add_argument("--k-missing", type=int, default=2)
    ap.add_argument("--max-iters", type=int, default=5)
    ap.add_argument("--max-corpus-size", type=int, default=10)
    ap.add_argument("--command-universe", default=None, help="Optional: comma-separated command list (overrides auto inference)")
    args = ap.parse_args(argv)

    openai_client = _load_openai_client()
    chroma_collection = _load_chroma_collection(Path(args.chroma_dir), args.collection)

    in_path = Path(args.input)
    out_path = Path(args.output)

    seed_files: List[Path] = []
    if in_path.is_dir():
        seed_files = sorted([p for p in in_path.iterdir() if p.is_file()])
        if args.max_corpus_size > 0 and len(seed_files) > args.max_corpus_size:
            seed_files = random.sample(seed_files, args.max_corpus_size)
    else:
        seed_files = [in_path]

    where = {"protocol_family": args.protocol_family, "implementation": args.implementation}

    for seed_file in seed_files:
        seq = seed_file.read_text(encoding="utf-8", errors="ignore")
        present = extract_present_message_types(seq)

        if args.command_universe:
            universe = [c.strip().upper() for c in args.command_universe.split(",") if c.strip()]
        else:
            # Use a broad query once to infer the command universe.
            broad_chunks = retrieve(
                chroma_collection=chroma_collection,
                openai_client=openai_client,
                embedding_model=args.embedding_model,
                query=f"{args.protocol_family} {args.implementation} client request commands methods list",
                top_k=args.topk,
                where=where,
            )
            universe = infer_command_universe(
                openai_client=openai_client,
                model=args.llm_model,
                protocol_family=args.protocol_family,
                implementation=args.implementation,
                present=present,
                context_chunks=broad_chunks,
            )

        missing = choose_missing_set(universe, present, args.k_missing)
        if not missing:
            # Nothing to do; still write-through if output is a file.
            if not out_path.is_dir():
                write_output_sequence(out_path, seq)
            continue

        cur = seq
        for cmd in missing:
            enriched, _evidence = enrich_one_command_react(
                openai_client=openai_client,
                chroma_collection=chroma_collection,
                embedding_model=args.embedding_model,
                llm_model=args.llm_model,
                protocol_family=args.protocol_family,
                implementation=args.implementation,
                sequence=cur,
                target_command=cmd,
                temperature=args.temperature,
                top_k=args.topk,
                max_iters=args.max_iters,
            )
            if enriched:
                cur = enriched

        if out_path.is_dir():
            write_output_sequence(out_path / seed_file.name, cur)
        else:
            write_output_sequence(out_path, cur)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

