## XPGFuzz Artifact

XPGFuzz 是一个面向有状态网络协议的 fuzzing 系统，在 AFLNet 风格流程上融合了两类 LLM 能力：

- **种子丰富（seed enrichment）**：种子丰富智能体根据协议文档检索结果补全请求序列中的缺失消息类型。
- **结构感知变异与自适应调度**：结合模板/约束信息进行变异，并在探索与利用之间自适应切换。

[油管分享视频](https://www.youtube.com/watch?v=itvrstXCgIc)，由notebooklm制作。

为了方便研究人员更好地体验，本项目用 Dify 做了一个在线的[协议种子丰富智能体](https://udify.app/chat/M8RJNTTQfaHwWesh)，复刻论文的种子丰富智能体的思路，以方便大家研究和交流。

---

## 快速开始（TL;DR）

如果你只跑 baseline（`aflnet`、`chatafl`），可直接关注 Docker 实验工具链。
如果你要跑 `xpgfuzz` 或 `aflnet+s1`，需要先构建 KB 并运行种子丰富智能体。

```bash
# 0) 配置 LLM/Embedding（xpgfuzz / aflnet+s1 必需）
cp .env.example .env
# 编辑 .env，至少设置 XPGFUZZ_LLM_API_KEY

# 1) 构建协议知识库（Chroma）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 xpgfuzz/protocol_seeds/build_vector_db.py --reset \
  --deepwikis-dir xpgfuzz/protocol_seeds/deepwikis \
  --persist-dir xpgfuzz/protocol_seeds/chroma_db_protocols \
  --collection protocols_wiki

# 2) 对一个 seed 做 enrichment（示例）
python3 xpgfuzz/protocol_seeds/seed_enricher_agent.py \
  --protocol-family SMTP \
  --implementation Exim \
  --input path/to/seed.raw \
  --output path/to/enriched.raw \
  --topk 2 --k-missing 2 --temperature 0.5

# 3) 构建实验镜像
./setup_all.sh

# 4) 运行实验并分析
./run.sh 1 5 lighttpd1 xpgfuzz
./analyze.sh lighttpd1 240
```

---

## 配置（LLM / Embedding）

项目不包含任何硬编码密钥，使用环境变量配置：

必需：
- `XPGFUZZ_LLM_API_KEY`

常用可选：
- `XPGFUZZ_LLM_BASE_URL`（OpenAI-compatible，通常以 `/v1` 结尾）
- `XPGFUZZ_LLM_MODEL`
- `XPGFUZZ_EMBEDDING_MODEL`
- `XPGFUZZ_EMBEDDING_BASE_URL`

KB 持久化（Chroma）：
- `XPGFUZZ_CHROMA_DIR`
- `XPGFUZZ_CHROMA_COLLECTION`

完整模板见 `.env.example`。

---

## 目录结构

```text
XPGFuzz
├── xpgfuzz/                               # C 核心 fuzzer
│   ├── afl-fuzz.c
│   ├── chat-llm.c
│   ├── chat-llm.h
│   └── protocol_seeds/                    # Python：KB + 种子丰富
│       ├── deepwikis/
│       ├── kb_clean.py
│       ├── semantic_chunker.py
│       ├── build_vector_db.py
│       ├── seed_enricher_agent.py
│       ├── env_config.py
│       └── chroma_db_protocols/           # 生成的向量库目录
├── benchmark/                             # 独立实验与后处理工具链
├── aflnet/
├── chatafl/
├── aflnet+s1/                             # 仅种子丰富消融
├── setup_all.sh
├── setup_*.sh
├── run.sh
├── analyze.sh
├── clean.sh
├── requirements.txt
└── .env.example
```

---

## 项目特色与模块概览

### 特色

- **端到端闭环**：协议文档 → KB → seed enrichment → fuzzing → 分析。
- **种子丰富智能体（核心）**：`seed_enricher_agent.py` 基于 RAG 插入缺失消息类型，输出可直接 fuzz 的序列。
- **结构感知变异与调度**：减少随机破坏协议语义的无效变异，提高有效状态探索。
- **benchmark 独立**：`benchmark/` 用于实验复现与结果后处理，不属于核心 fuzzing 逻辑本体。
- **消融清晰**：`aflnet+s1` 为仅种子丰富；`xpgfuzz` 可视为 `aflnet+s1+s2`。

### 模块

- **`xpgfuzz/`**：C 侧核心执行与反馈驱动 fuzzing。
- **`xpgfuzz/protocol_seeds/`**：KB 构建与 enrichment。
- **`benchmark/`**：独立的执行/回放/绘图汇总工具链。

### 输入与输出

- **输入文档**：`xpgfuzz/protocol_seeds/deepwikis/`
- **KB 输出**：`xpgfuzz/protocol_seeds/chroma_db_protocols/`
- **enrichment**：
  - 输入：`--input path/to/seed.raw`
  - 输出：`--output path/to/enriched.raw`
- **分析输出**：仓库根目录 `res_<subject>_<timestamp>/`

---

## 使用指南（中文）

### 0) 选择 fuzzer 变体

- `aflnet`、`chatafl`：baseline（不依赖 KB/种子丰富）。
- `aflnet+s1`：仅种子丰富（需要先构建 KB + 跑 enrichment）。
- `xpgfuzz`：完整方案，可视为 `aflnet+s1+s2`（需要先构建 KB + 跑 enrichment）。

### 1) 依赖环境

- Linux (Ubuntu/Debian) + Docker + Python 3

```bash
./deps.sh
```

### 2) 构建镜像

```bash
./setup_all.sh
```

### 3) 运行实验

```bash
./run.sh <NUM_CONTAINERS> <TIMEOUT_MIN> <SUBJECTS> <FUZZERS>
```

示例：

```bash
./run.sh 1 5 lighttpd1 xpgfuzz
```

### 4) 结果分析

```bash
./analyze.sh <subjects> <time_in_minutes>
```

### 5) 清理

```bash
./clean.sh
FORCE_STOP=1 ./clean.sh
```

---

## License

See `xpgfuzz/LICENSE`.
