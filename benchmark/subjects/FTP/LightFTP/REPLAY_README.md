# LightFTP Bug Replay 使用说明

## 概述

本脚本用于重放LightFTP协议的bug并收集日志进行分析。

## 前置条件

1. **确保Docker镜像已构建**
   ```bash
   cd benchmark/subjects/FTP/LightFTP
   docker build -f Dockerfile_replay -t xpg-$(date +%-m)-$(date +%-d)-lightftp-replay .
   ```
   或者使用指定的日期：
   ```bash
   docker build -f Dockerfile_replay -t xpg-12-5-lightftp-replay .
   ```

2. **确保in-ftp-bugs目录存在且包含bug文件**
   - bug文件应该位于 `benchmark/subjects/FTP/LightFTP/in-ftp-bugs/` 目录下
   - 这些文件通常是fuzzer生成的测试用例（如 `id:000000,sig:06,src:000248,op:havoc_exploit,rep:32`）

## 运行方法

### 方法1: 使用便捷脚本（推荐）

在项目根目录运行：

```bash
./run_replay.sh NUM_CONTAINERS TIMEOUT TARGET FUZZER [IMAGE_DATE]
```

**参数说明：**
- `NUM_CONTAINERS`: 容器数量（bug重放通常只需要1个）
- `TIMEOUT`: 超时时间（分钟），默认60分钟
  - **超时时间计算依据**：
    - 每个bug的处理时间约为10-15秒（包括server启动、重放、日志收集等）
    - 计算公式：`TIMEOUT = (bug数量 × 15秒) / 60 + 缓冲时间`
    - 例如：314个bug × 15秒 ≈ 78.5分钟，建议设置为90-120分钟
    - 如果bug数量很多，建议设置更长的超时时间
- `TARGET`: 目标协议，使用 `lightftp`
- `FUZZER`: fuzzer名称，如 `xpgfuzz`, `aflnet`, `chatafl` 等
- `IMAGE_DATE`: （可选）镜像日期，格式为 `MM-DD`，如 `12-5`

**示例：**

```bash
# 使用当前日期的镜像，重放lightftp的bug（使用xpgfuzz）
# 默认60分钟，适合约200-300个bug
./run_replay.sh 1 60 lightftp xpgfuzz

# 如果bug数量较多（如300+），建议增加超时时间
./run_replay.sh 1 120 lightftp xpgfuzz

# 使用指定日期的镜像
IMAGE_DATE=12-5 ./run_replay.sh 1 90 lightftp xpgfuzz

# 重放所有fuzzer的bug
./run_replay.sh 1 120 lightftp all
```

### 方法2: 直接调用profuzzbench_replay_common.sh

```bash
cd benchmark
PATH=$PATH:$PWD/scripts/execution

profuzzbench_replay_common.sh \
  xpg-12-5-lightftp-replay \    # Docker镜像名称
  1 \                     # 运行次数
  results-lightftp-replay \  # 结果保存目录
  xpgfuzz \               # fuzzer名称
  out-lightftp-xpgfuzz-replay \  # 输出目录名称
  "" \                    # OPTIONS（bug重放不需要）
  3600 \                   # TIMEOUT（秒）
  1 \                      # SKIPCOUNT
  ""                       # DELETE（可选，完成后删除容器）
```

### 方法3: 使用profuzzbench_replay_all.sh

```bash
cd benchmark
export NUM_CONTAINERS=1
export TIMEOUT=3600
export SKIPCOUNT=1
export PFBENCH=$PWD

scripts/execution/profuzzbench_replay_all.sh lightftp xpgfuzz
```

## 工作流程

1. **创建容器**: 使用Dockerfile_replay构建的镜像创建容器
2. **复制bug文件**: in-ftp-bugs目录已在镜像构建时复制到容器中
3. **运行重放**: 容器内执行run_replay.sh，调用collect_log.sh重放所有bug
4. **收集日志**: 每个bug的日志保存到logs/目录
5. **打包结果**: 所有结果打包为tar.gz文件
6. **提取结果**: 从容器中提取结果到主机

## 输出结果

结果会保存在 `benchmark/results-lightftp-replay/` 目录下：

```
results-lightftp-replay/
├── out-lightftp-xpgfuzz-replay_1.tar.gz
└── ...
```

解压后包含：

```
out-lightftp-xpgfuzz-replay/
├── bug_replay_logs.csv          # 摘要CSV文件
└── logs/                         # 每个bug的日志文件
    ├── id:000000,sig:06,src:000248,op:havoc_exploit,rep:32.log
    ├── id:000001,sig:06,src:000295+001038,op:havoc_exploit,rep:16.log
    └── ...
```

### bug_replay_logs.csv 格式

```csv
BugFile,Status,LogFile,Timestamp
id:000000,sig:06,src:000248,op:havoc_exploit,rep:32,1,logs/id:000000,sig:06,src:000248,op:havoc_exploit,rep:32.log,1703123456
```

- **BugFile**: bug文件名
- **Status**: 状态（1=检测到崩溃，0=正常）
- **LogFile**: 日志文件路径
- **Timestamp**: 时间戳

## 查看结果

```bash
# 解压结果
cd benchmark/results-lightftp-replay
tar -xzf out-lightftp-xpgfuzz-replay_1.tar.gz

# 查看摘要
cat out-lightftp-xpgfuzz-replay/bug_replay_logs.csv

# 查看特定bug的日志
cat out-lightftp-xpgfuzz-replay/logs/id:000000,sig:06,src:000248,op:havoc_exploit,rep:32.log
```

## 注意事项

1. **Docker镜像名称**: 必须与构建时的镜像名称匹配（格式：`xpg-{月}-{日}-lightftp-replay`）
2. **bug文件格式**: 确保in-ftp-bugs目录中的文件是fuzzer生成的结构化格式（使用aflnet-replay重放）
3. **超时设置**: 
   - 每个bug处理时间约10-15秒（包括server启动10秒、重放、日志收集等）
   - 建议超时时间 = (bug数量 × 15秒) / 60 + 20-30分钟缓冲
   - 例如：314个bug建议设置90-120分钟
   - 如果超时时间不足，容器会被强制终止，可能导致部分bug未处理
4. **容器清理**: 如果设置了DELETE参数，容器会在完成后自动删除

## 故障排查

1. **容器创建失败**: 检查Docker镜像是否存在
   ```bash
   docker images | grep lightftp
   ```

2. **找不到bug文件**: 检查in-ftp-bugs目录是否在Dockerfile中正确复制

3. **replayer工具找不到**: 检查fuzzer工具是否在PATH中，或修改collect_log.sh中的路径

4. **查看容器日志**: 
   ```bash
   docker logs <container_id>
   ```

