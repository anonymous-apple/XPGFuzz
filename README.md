## XPGFuzz Artifact (Anonymous)

XPGFuzz is a stateful network protocol fuzzing artifact built on a modified AFLNet-style workflow and integrates two LLM-assisted capabilities:

- **Seed enrichment**: enrich recorded client request sequences by inserting missing message types using retrieved protocol documentation.
- **Structure-aware mutation & scheduling**: mutate messages with template/constraint guidance and adaptive scheduling (explore vs. exploit; optional bandit-based operator selection).

This repository is intended to be shared as an **anonymous artifact**. It contains **no hardcoded API keys** and provides a sanitization checker for release packaging.

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
- `XPGFUZZ_CHROMA_DIR` (default in `.env.example`)
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
│       │   └── <PROTO>/<IMPL>/*.md
│       ├── kb_clean.py                    # markdown cleaning/normalization
│       ├── semantic_chunker.py            # semantic atomization + fixed-window chunking
│       ├── build_vector_db.py             # build Chroma KB from deepwikis/
│       ├── seed_enricher_agent.py         # enrichment agent (RAG + iterative insert + evidence validation)
│       ├── env_config.py                  # env-driven config (no hardcoded keys/URLs)
│       └── chroma_db_protocols/            # (generated) persistent Chroma DB directory
├── benchmark/                             # independent experiment runner + post-analysis (used after runs)
│   ├── subjects/                          # per-subject docker build context + run scripts
│   │   ├── FTP/ (BFTPD, LightFTP, ProFTPD, PureFTPD)
│   │   ├── HTTP/ (Lighttpd1)
│   │   ├── SMTP/ (Exim)
│   │   ├── SIP/ (Kamailio)
│   │   ├── RTSP/ (Live555)
│   │   └── DAAP/ (forked-daapd)
│   ├── scripts/
│   │   ├── execution/                     # batch run/replay orchestration
│   │   │   ├── profuzzbench_exec_all.sh
│   │   │   ├── profuzzbench_exec_common.sh
│   │   │   ├── profuzzbench_replay_all.sh
│   │   │   └── profuzzbench_replay_common.sh
│   │   └── analysis/                      # plotting scripts (coverage/state over time)
│   └── comprehensive_analysis.py           # summary analysis across protocols
├── aflnet/                                 # baseline fuzzer variant
├── chatafl/                                # baseline fuzzer variant
├── aflnet+s1/                               # ablation: seed enrichment only
├── deps.sh                                 # helper dependency installer (Linux/apt)
├── requirements.txt                        # python deps for KB/enrichment tools
├── setup_all.sh                            # build all docker images (runs setup_*.sh)
├── setup_*.sh                              # build individual subject image
├── run.sh                                  # run fuzzing in benchmark containers
├── analyze.sh                               # generate coverage/state plots + bug stats
├── clean.sh                                # cleanup docker containers (keeps images)
└── .env.example                             # environment template (no secrets)
```

---

## Key features & module overview (high level)

### Key features / advantages

- **End-to-end workflow for stateful protocols**: docs → KB → enriched sequences → fuzzing → analysis, designed as a closed loop rather than a single standalone component.
  - Input docs: `xpgfuzz/protocol_seeds/deepwikis/` (Markdown).
  - KB: cleaned/atomized/chunked docs persisted to Chroma for vector retrieval.
  - Enrichment: raw sessions are augmented into state-coverage-friendly request sequences.
  - Fuzzing: the C fuzzer consumes enriched seeds to drive server interaction and feedback.
- **Seed enrichment agent (core)**: `seed_enricher_agent.py` performs RAG over the KB and inserts missing message types to produce fuzzing-ready **raw request sequences**.
  - Typical flow: extract present message types → choose Missing-set (default \(K=2\)) → retrieve Top-k (default \(k=2\)) → iterative insertion/refinement → output enriched sequence.
  - Traceability: produces an `evidence_map` linking inserted content to retrieved KB snippets.
- **Structure-aware mutation & adaptive scheduling (C side)**: integrates structure/constraint-guided mutation and adaptive explore-vs-exploit scheduling into an AFLNet-style stateful fuzzing workflow.
- **Independent experiment replication + post-analysis**: `benchmark/` is a standalone post-processing/replication toolchain used after runs for aggregation, plotting, and comparison.
- **Clear ablation variant**: `aflnet+s1` is the **seed-enrichment-only** ablation; `xpgfuzz` can be viewed as **`aflnet+s1+s2`** (adding structure-aware mutation and scheduling on top of `s1`) to quantify the full-system gain over the ablation.

### Modules (by directory)

- **`xpgfuzz/` (C core fuzzer)**: turns request sequences into stateful network interactions and drives feedback-guided fuzzing.
  - `afl-fuzz.c`: main loop (queue/scheduling, state handling, execution/feedback, saving interesting inputs).
  - `chat-llm.c/h`: C-side OpenAI-compatible client (env-driven key/base_url/model).
- **`xpgfuzz/protocol_seeds/` (Python: KB + enrichment)**: builds a retrievable protocol KB and enriches raw sessions into fuzzing-ready seeds.
  - **KB builder**: `kb_clean.py` → `semantic_chunker.py` → `build_vector_db.py` (persist to Chroma).
  - **Enrichment agent**: `seed_enricher_agent.py` (RAG + iterative insertion + evidence validation).
  - **Unified config**: `.env.example` / `env_config.py`, no hardcoded secrets.
- **`benchmark/` (standalone: experiment replication + post-analysis)**: not a core fuzzing module; used after runs for aggregation/plotting/comparison.
  - `benchmark/scripts/execution/`: batch execution & replay scripts (container orchestration + result collection).
  - `benchmark/scripts/analysis/`: plotting scripts; `benchmark/comprehensive_analysis.py` for summary analysis.
  - `benchmark/subjects/`: per-subject Dockerfiles, run scripts, and seeds/dicts (to reproduce experiment environments).
- **Top-level scripts**:
  - `setup_all.sh` / `setup_*.sh`: build subject Docker images.
  - `run.sh`: one entrypoint to run fuzzing (supports `aflnet+s1`).
  - `analyze.sh`: analyze and plot results.

### Inputs / outputs (what the tools consume/produce)

- **Protocol docs**: Markdown under `xpgfuzz/protocol_seeds/deepwikis/`.
- **Vector KB**: persisted Chroma DB under `xpgfuzz/protocol_seeds/chroma_db_protocols/` (generated by `build_vector_db.py`).
- **Raw seed sequences**:
  - Input to enrichment: `--input path/to/seed.raw`
  - Output of enrichment: `--output path/to/enriched.raw`
  - The exact per-protocol seed conventions vary (e.g., line-based command sequences for FTP, request sequences for RTSP/SIP).
    For concrete examples, see the per-subject seed folders under `benchmark/subjects/**/in-*`.
- **Experiment outputs**:
  - `run.sh` will produce per-run output directories and archived `.tar.gz` results inside the harness.
  - `analyze.sh` creates `res_<subject>_<timestamp>/` in the repo root with plots + aggregated CSVs.

## 项目特色与模块概览

### 项目特色 

- **面向有状态协议的端到端流水线**：把“文档 → 知识 → 结构化输入 → fuzzing → 统计”串成闭环，避免只做单点能力。
  - 输入：协议文档（`xpgfuzz/protocol_seeds/deepwikis/`，Markdown）。
  - 知识化：清洗 + 语义原子化 + 分块后写入 Chroma（向量检索）。
  - 生成：用种子丰富智能体把原始会话补全为更“状态机覆盖友好”的请求序列。
  - 执行：C 侧 fuzzer 消耗 enriched seeds，驱动网络服务端并反馈覆盖/状态信息。
- **LLM 辅助的种子丰富智能体（核心）**：`seed_enricher_agent.py` 用 RAG 检索协议知识库，做“缺失消息类型”的选择与插入，输出可直接用于 fuzzing 的 **raw request sequence**。
  - 典型流程：抽取已出现的 message types → 选择 Missing-set（默认 \(K=2\)）→ Top-k 检索（默认 \(k=2\)）→ 迭代插入/修正 → 输出 enriched sequence。
  - 可追溯性：输出包含 `evidence_map`（把新增内容与检索到的片段关联），便于复查与调参。
- **结构感知的变异与调度（C 侧实现）**：在 AFLNet 风格的状态化网络 fuzzing 基础上，加入更贴近协议字段/模板的变异策略，并通过自适应调度在探索与利用之间切换。
  - 目标：减少“完全随机字节翻转”对协议解析的破坏，提升有效交互与状态覆盖的概率。
- **独立的实验复现与结果分析**：`benchmark/` 是**独立工具链**，用于实验跑完后的结果汇总、绘图与对比，不属于核心 fuzzing 模块本体。
  - 你可以把它当作“post-processing + replication harness”：统一脚本跑多轮、收集结果包、生成覆盖/状态随时间曲线与汇总表。
- **消融变体明确**：`aflnet+s1` 是 **仅包含种子丰富（seed enrichment only）** 的消融版本；`xpgfuzz` 可视为 **`aflnet+s1+s2`**（在 `s1` 的基础上进一步加入结构感知变异与调度等增强），用于评估完整方案相对消融的增益。

### 模块说明

- **`xpgfuzz/`（C 核心 fuzzer）**：负责“把输入序列变成对 server 的网络交互”，并在反馈（覆盖/状态）驱动下执行状态化 fuzzing。
  - `afl-fuzz.c`：主流程（队列调度、状态管理、执行/反馈、保存 interesting case）。
  - `chat-llm.c/h`：C 侧 LLM 调用封装（OpenAI-compatible；从环境变量读取 key/base_url/model）。
- **`xpgfuzz/protocol_seeds/`（Python：知识库 + 种子丰富）**：负责“把协议知识转化为可检索 KB”，并把“原始会话”丰富成 fuzzing-ready seeds。
  - **知识库构建**：`kb_clean.py`（清洗）→ `semantic_chunker.py`（语义原子化 + 分块）→ `build_vector_db.py`（向量化并写入 Chroma）。
  - **种子丰富智能体**：`seed_enricher_agent.py`（RAG 检索 + 迭代插入 + `evidence_map` 校验）。
  - **配置统一**：`env_config.py` + `.env.example`，统一 LLM/Embedding/Chroma 配置，确保匿名发布不包含硬编码密钥。

### 输入 / 输出（工具链产物）

- **协议文档**：`xpgfuzz/protocol_seeds/deepwikis/` 下的 Markdown。
- **向量知识库（KB）**：`build_vector_db.py` 生成并持久化到 `xpgfuzz/protocol_seeds/chroma_db_protocols/`。
- **种子序列（raw/enriched）**：
  - enrichment 输入：`--input path/to/seed.raw`
  - enrichment 输出：`--output path/to/enriched.raw`
  - 不同协议的 seed 细节格式会不同（例如 FTP 更像命令行序列，RTSP/SIP 是请求序列）。可以参考 `benchmark/subjects/**/in-*` 的示例 seeds。
- **实验结果**：
  - `run.sh` 运行后会在工具链侧生成每次 run 的输出目录，并打包为 `.tar.gz`。
  - `analyze.sh` 会在仓库根目录生成 `res_<subject>_<timestamp>/`，包含图表与汇总 CSV。

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

On macOS, please install Docker Desktop and Python3 manually.

### 2) Configuration (LLM / Embeddings)

The repo contains **no hardcoded secrets**. Configure via environment or `.env`:

```bash
cp .env.example .env
```

At minimum set `XPGFUZZ_LLM_API_KEY`. Optionally set base URL/model and embedding options.

Notes:
- `XPGFUZZ_LLM_BASE_URL` is OpenAI-compatible and typically ends with `/v1` (see `.env.example`).
- If you only run baselines (`aflnet`, `chatafl`), you do not need LLM configuration.

### 3) Build Docker images

Build all subject images (may take a while):

```bash
./setup_all.sh
```

### 4) Run experiments

```bash
./run.sh <NUM_CONTAINERS> <TIMEOUT_MIN> <SUBJECTS> <FUZZERS>
```

Example:

```bash
./run.sh 1 5 lighttpd1 xpgfuzz
```

The wrapper delegates to the standalone execution toolchain under `benchmark/`.
Common `FUZZERS` values: `aflnet`, `chatafl`, `xpgfuzz`, `aflnet+s1` (ablation variant with **seed enrichment only**).

### 5) Analyze results

```bash
./analyze.sh <subjects> <time_in_minutes>
```

Example:

```bash
./analyze.sh lighttpd1 240
```

An analysis folder `res_<subject>_<timestamp>/` will be created in the repo root.

### 6) Cleanup (containers only, keeps images)

```bash
./clean.sh
```

To stop & remove running containers:

```bash
FORCE_STOP=1 ./clean.sh
```

### 7) Required: build KB + run seed enrichment agent (Python)

`aflnet+s1` and `xpgfuzz` rely on **seed enrichment**, so this step is part of the required workflow:
- Build the protocol KB (for RAG retrieval)
- Run `seed_enricher_agent.py` to enrich raw request sequences into fuzzing-ready seeds

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 xpgfuzz/protocol_seeds/build_vector_db.py --reset \
  --deepwikis-dir xpgfuzz/protocol_seeds/deepwikis \
  --persist-dir xpgfuzz/protocol_seeds/chroma_db_protocols \
  --collection protocols_wiki
```

Run enrichment (output is raw sequences only):

```bash
python3 xpgfuzz/protocol_seeds/seed_enricher_agent.py \
  --protocol-family SMTP \
  --implementation Exim \
  --input path/to/seed.raw \
  --output path/to/enriched.raw \
  --topk 2 --k-missing 2 --temperature 0.5
```

### 8) Troubleshooting

```bash
docker ps -a | grep <subject>
docker logs <container_id>
```

---

## 中文（使用指南）

### 0) 选择 fuzzer 变体

- `aflnet`、`chatafl`：baseline（不依赖 KB/种子丰富）。
- `aflnet+s1`：**仅种子丰富**（需要先构建 KB + 跑 enrichment）。
- `xpgfuzz`：完整方案，可视为 **`aflnet+s1+s2`**（需要先构建 KB + 跑 enrichment）。

### 1) 依赖与环境

#### 推荐环境

- Linux (Ubuntu/Debian) + Docker
- Python 3

`deps.sh` 适用于 `apt` 系统：

```bash
./deps.sh
```

如果你在 macOS 上运行，建议自行安装：Docker Desktop、Python3，以及 `matplotlib/pandas`（用于 `analyze.sh`）。

### 2) 配置（LLM/Embedding）

本项目**不包含任何硬编码 token**。需要自行配置环境变量（或 `.env`）：

```bash
cp .env.example .env
```

至少需要设置：
- `XPGFUZZ_LLM_API_KEY`

可选：
- `XPGFUZZ_LLM_BASE_URL`（OpenAI-compatible，通常以 `/v1` 结尾）
- `XPGFUZZ_LLM_MODEL`
- `XPGFUZZ_EMBEDDING_MODEL` / `XPGFUZZ_EMBEDDING_BASE_URL`

### 3) 准备 Docker 镜像（~数十分钟，取决于机器/网络）

该仓库包含多个 `setup_*.sh` 用于构建 benchmark subjects 的镜像。

```bash
./setup_all.sh
```

### 4) 运行实验

使用 `run.sh`（它会进入 `benchmark/` 并调用执行脚本）：

```bash
./run.sh <NUM_CONTAINERS> <TIMEOUT_MIN> <SUBJECTS> <FUZZERS>
```

示例：

```bash
./run.sh 1 5 lighttpd1 xpgfuzz
```

说明：
- `SUBJECTS` / `FUZZERS` 支持逗号分隔或 `all`。
- `FUZZERS` 常用取值示例：`aflnet`、`chatafl`、`xpgfuzz`、`aflnet+s1`（消融：**仅种子丰富**）。
- 可用环境变量：
  - `IMAGE_DATE`：指定镜像日期（脚本会使用该日期格式的镜像名）
  - `SKIPCOUNT`、`TEST_TIMEOUT`：执行侧参数（详见 `run.sh` / benchmark 执行脚本）

### 5) 分析结果（绘图 + 统计）

```bash
./analyze.sh <subjects> <time_in_minutes>
```

示例：

```bash
./analyze.sh lighttpd1 240
```

完成后会在仓库根目录生成 `res_<subject>_<timestamp>/`，包含：
- 覆盖/状态随时间变化的 PNG 图
- 运行结果归档（`results-<subject>`）
- 去重后的 bug 统计与详情（若脚本支持）

### 6) 清理（只删容器，不删镜像）

```bash
./clean.sh
```

如需强制停止并删除运行中的容器：

```bash
FORCE_STOP=1 ./clean.sh
```

### 7) 必须：构建协议知识库 + 运行种子丰富智能体（Python）

`aflnet+s1` 与 `xpgfuzz` 都依赖**种子丰富**（seed enrichment）。因此在跑实验前，你需要先：
- 构建协议知识库（用于 RAG 检索）
- 用 `seed_enricher_agent.py` 对原始会话序列进行丰富，生成后续 fuzzing 使用的 seed 序列

构建 KB（Chroma 持久化）：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 xpgfuzz/protocol_seeds/build_vector_db.py --reset \
  --deepwikis-dir xpgfuzz/protocol_seeds/deepwikis \
  --persist-dir xpgfuzz/protocol_seeds/chroma_db_protocols \
  --collection protocols_wiki
```

运行种子丰富（输出文件只包含“纯序列”）：

```bash
python3 xpgfuzz/protocol_seeds/seed_enricher_agent.py \
  --protocol-family SMTP \
  --implementation Exim \
  --input path/to/seed.raw \
  --output path/to/enriched.raw \
  --topk 2 --k-missing 2 --temperature 0.5
```

### 8) 故障排查（Troubleshooting）

- 容器运行状态：

```bash
docker ps -a | grep <subject>
```

- 查看失败容器日志：

```bash
docker logs <container_id>
```

---

## License

See `xpgfuzz/LICENSE`.

