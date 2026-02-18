## XPGFuzz Artifact (Anonymous)

XPGFuzz is a stateful network protocol fuzzing artifact built on a modified AFLNet-style workflow and integrates two LLM-assisted capabilities:

- **Seed enrichment**: enrich recorded client request sequences by inserting missing message types using retrieved protocol documentation.
- **Structure-aware mutation & scheduling**: mutate messages with template/constraint guidance and adaptive scheduling (explore vs. exploit; optional bandit-based operator selection).

This repository is intended to be shared as an **anonymous artifact**. It contains **no hardcoded API keys**.

To help researchers try it quickly, we built an online **protocol seed enrichment agent** with Dify: [Protocol seed enrichment agent](https://udify.app/chat/M8RJNTTQfaHwWesh).

---

## TL;DR (Quick start)

If you only want to run **baselines** (`aflnet`, `chatafl`), you can focus on the Docker experiment harness.
If you want to run **XPGFuzz** (or the ablation **`aflnet+s1`**), you must build the protocol KB and run the seed enrichment agent first.

```bash
# 0) Configure LLM/embedding (required for xpgfuzz / aflnet+s1)
cp .env.example .env
# Edit .env and set at least: XPGFUZZ_LLM_API_KEY

# 1) Build protocol KB (Chroma)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 xpgfuzz/protocol_seeds/build_vector_db.py --reset \
  --deepwikis-dir xpgfuzz/protocol_seeds/deepwikis \
  --persist-dir xpgfuzz/protocol_seeds/chroma_db_protocols \
  --collection protocols_wiki

# 2) Enrich one seed sequence (example)
python3 xpgfuzz/protocol_seeds/seed_enricher_agent.py \
  --protocol-family SMTP \
  --implementation Exim \
  --input path/to/seed.raw \
  --output path/to/enriched.raw \
  --topk 2 --k-missing 2 --temperature 0.5

# 3) Build subject images (experiment harness)
./setup_all.sh

# 4) Run experiments + analyze
./run.sh 1 5 lighttpd1 xpgfuzz
./analyze.sh lighttpd1 240
```

---

## Configuration (LLM / Embeddings)

This artifact uses **OpenAI-compatible** HTTP APIs for both chat and embeddings. No secrets are hardcoded.

Required:
- `XPGFUZZ_LLM_API_KEY`

Common optional variables:
- `XPGFUZZ_LLM_BASE_URL` (OpenAI-compatible, typically ends with `/v1`)
- `XPGFUZZ_LLM_MODEL`
- `XPGFUZZ_EMBEDDING_MODEL`
- `XPGFUZZ_EMBEDDING_BASE_URL` (defaults to `XPGFUZZ_LLM_BASE_URL`)

Chroma (KB persistence):
- `XPGFUZZ_CHROMA_DIR`
- `XPGFUZZ_CHROMA_COLLECTION`

See `.env.example` for a full template.

---

## Folder structure

```text
XPGFuzz
├── xpgfuzz/                               # core fuzzer (C)
│   ├── afl-fuzz.c                         # main fuzzer entry (stateful network fuzzing)
│   ├── chat-llm.c                         # C-side LLM HTTP client (OpenAI-compatible)
│   ├── chat-llm.h
│   └── protocol_seeds/                    # Python: KB + seed enrichment tooling
│       ├── deepwikis/                     # protocol documentation corpus (markdown)
│       ├── kb_clean.py
│       ├── semantic_chunker.py
│       ├── build_vector_db.py
│       ├── seed_enricher_agent.py
│       ├── env_config.py
│       └── chroma_db_protocols/           # generated Chroma DB directory
├── benchmark/                             # standalone experiment runner + post-analysis
├── aflnet/                                # baseline fuzzer variant
├── chatafl/                               # baseline fuzzer variant
├── aflnet+s1/                             # ablation: seed enrichment only
├── setup_all.sh
├── setup_*.sh
├── run.sh
├── analyze.sh
├── clean.sh
├── requirements.txt
└── .env.example
```

---

## Key features & module overview (high level)

### Key features / advantages

- **End-to-end workflow for stateful protocols**: docs → KB → enriched sequences → fuzzing → analysis.
- **Seed enrichment agent (core)**: `seed_enricher_agent.py` performs RAG over the KB and inserts missing message types to produce fuzzing-ready raw request sequences.
- **Structure-aware mutation & adaptive scheduling (C side)**: integrates structure/constraint-guided mutation and adaptive explore-vs-exploit scheduling.
- **Independent experiment replication + post-analysis**: `benchmark/` is a standalone post-processing/replication toolchain used after runs.
- **Clear ablation variant**: `aflnet+s1` is seed-enrichment-only; `xpgfuzz` can be viewed as `aflnet+s1+s2`.

### Modules (by directory)

- **`xpgfuzz/`**: core stateful fuzzer and C-side LLM glue.
- **`xpgfuzz/protocol_seeds/`**: KB builder + seed enrichment agent.
- **`benchmark/`**: standalone experiment/post-analysis toolchain (not core fuzzing logic).

### Inputs / outputs

- **Protocol docs**: `xpgfuzz/protocol_seeds/deepwikis/`
- **Vector KB**: `xpgfuzz/protocol_seeds/chroma_db_protocols/`
- **Seed enrichment**:
  - Input: `--input path/to/seed.raw`
  - Output: `--output path/to/enriched.raw`
- **Analysis outputs**: `res_<subject>_<timestamp>/` in repo root.

---

## English (Usage)

### 0) Choose a fuzzer variant

- `aflnet`, `chatafl`: baseline variants (no KB/enrichment required).
- `aflnet+s1`: **seed enrichment only** (KB + enrichment required).
- `xpgfuzz`: full system, can be viewed as **`aflnet+s1+s2`** (KB + enrichment required).

### 1) Requirements

Recommended setup:
- Linux (Ubuntu/Debian) + Docker
- Python 3

If you are on an `apt`-based system, you can try:

```bash
./deps.sh
```

### 2) Build Docker images

```bash
./setup_all.sh
```

### 3) Run experiments

```bash
./run.sh <NUM_CONTAINERS> <TIMEOUT_MIN> <SUBJECTS> <FUZZERS>
```

Example:

```bash
./run.sh 1 5 lighttpd1 xpgfuzz
```

### 4) Analyze results

```bash
./analyze.sh <subjects> <time_in_minutes>
```

### 5) Cleanup

```bash
./clean.sh
FORCE_STOP=1 ./clean.sh
```

---

## License

See `xpgfuzz/LICENSE`.
