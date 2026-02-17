"""
Backward-compatible entrypoint for building the protocol DeepWiki KB.

This file used to build a KB via a character splitter. For paper alignment we now
use semantic atomization + fixed window chunking:
  - semantic atoms: headings / paragraphs / lists / tables / fenced code
  - windowing: L_max=1024, L_overlap=50 (chars)
  - storage: Chroma (HNSW)

Use:
  python3 xpgfuzz/protocol_seeds/build_vector_db.py --reset
or keep using:
  python3 xpgfuzz/protocol_seeds/create_protocol_db.py
"""

from __future__ import annotations

try:
    from .build_vector_db import main
except Exception:  # pragma: no cover
    from build_vector_db import main


if __name__ == "__main__":
    raise SystemExit(main())