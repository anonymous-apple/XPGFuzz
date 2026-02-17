# Live555 RTSP Coverage Analysis: XPGfuzz vs AFLNet

## 问题概述

XPGfuzz 在 Live555 RTSP 协议上的覆盖率显著低于 AFLNet：
- **总体行覆盖率**: 从 22.9% 降至 17.8% (下降 5.1%)
- **总体分支覆盖率**: 从 13.9% 降至 10.8% (下降 3.1%)

## 核心问题分析

### 1. PATH 约束变异过于激进

**问题根源**：
- RTSP URL 路径使用 `<<PATH>>` 约束，但当前的 PATH 变异策略生成的是通用路径攻击模式：
  - `../../../etc/passwd`
  - `/tmp/`
  - `C:\`
  - `..%2f..%2fetc%2fpasswd`
  - 等等...

**Live555 的路由机制**：
- Live555 服务器通过**特定的媒体流名称**来路由请求到不同的处理器：
  - `mp3AudioTest` → MP3 音频处理器
  - `ac3AudioTest` → AC3 音频处理器  
  - `mpeg1or2AudioVideoTest` → MPEG1/2 音视频处理器
  - `matroskaFileTest` → Matroska 文件处理器
  - `wavAudioTest` → WAV 音频处理器
  - `webmFileTest` → WebM 文件处理器

**影响**：
- 当 PATH 被变异为无效路径（如 `/tmp/`）时，服务器无法匹配到任何媒体会话
- 请求在早期被拒绝，无法到达对应的媒体处理代码
- 导致大量 MP3/AC3/MPEG 相关代码的覆盖率为 0%

### 2. 受影响的文件分析

以下文件覆盖率降至 0%，说明对应的代码路径未被触发：

#### MP3 相关 (完全未覆盖)
- `MP3ADU.cpp`: 78.1% → 0.0%
- `MP3ADUdescriptor.cpp`: 68.8% → 0.0%
- `MP3ADUdescriptor.hh`: 100.0% → 0.0%
- `MP3AudioFileServerMediaSubsession.cpp`: 59.7% → 6.7%
- `MP3FileSource.cpp`: 71.8% → 0.0%
- `MP3Internals.cpp`: 38.9% → 0.0%
- `MP3Internals.hh`: 100.0% → 0.0%
- `MP3StreamState.cpp`: 63.8% → 0.0%
- `MP3StreamState.hh`: 50.0% → 0.0%
- `MP3Transcoder.cpp`: 100.0% → 0.0%

#### MPEG 相关 (大幅下降)
- `MPEG1or2AudioStreamFramer.cpp`: 90.0% → 0.0%
- `MPEG1or2VideoRTPSink.cpp`: 84.1% → 0.0%
- `MPEG1or2VideoStreamFramer.cpp`: 78.2% → 0.0%
- `MPEGVideoStreamParser.cpp`: 100.0% → 0.0%
- `MPEGVideoStreamParser.hh`: 64.5% → 0.0%
- `MPEG1or2DemuxedServerMediaSubsession.cpp`: 77.8% → 9.1%
- `MPEG1or2FileServerDemux.cpp`: 93.0% → 71.8%

#### 其他
- `AudioInputDevice.cpp`: 50.0% → 0.0%
- `BitVector.cpp`: 57.3% → 0.0%

### 3. 种子文件分析

从 `in-rtsp-x-old` 目录的种子文件可以看出：
- 种子文件包含正确的媒体流路径：`rtsp://127.0.0.1:8554/mp3AudioTest`
- 但变异过程中，这些有效路径被替换为无效路径
- AFLNet 可能通过字典机制保留了这些有效路径

## 解决方案建议

### 方案 1: 增强 PATH 变异策略（推荐）

修改 `chat-llm.c` 中的 `CONSTRAINT_PATH` 处理逻辑，添加 RTSP 特定的有效路径：

```c
case CONSTRAINT_PATH:
{
    // RTSP 特定的有效媒体流路径
    const char *rtsp_valid_paths[] = {
        "rtsp://127.0.0.1:8554/mp3AudioTest",
        "rtsp://127.0.0.1:8554/ac3AudioTest", 
        "rtsp://127.0.0.1:8554/mpeg1or2AudioVideoTest",
        "rtsp://127.0.0.1:8554/matroskaFileTest",
        "rtsp://127.0.0.1:8554/wavAudioTest",
        "rtsp://127.0.0.1:8554/webmFileTest",
        "/mp3AudioTest",
        "/ac3AudioTest",
        "/mpeg1or2AudioVideoTest",
        "/matroskaFileTest",
        "/wavAudioTest",
        "/webmFileTest",
        "/mp3AudioTest/track1",
        "/ac3AudioTest/track1",
        "/mpeg1or2AudioVideoTest/track1",
        "/mpeg1or2AudioVideoTest/track2",
        "/matroskaFileTest/track1",
        "/matroskaFileTest/track2",
    };
    
    // 混合策略：50% 使用有效路径，50% 使用攻击路径
    if (random() % 2 == 0) {
        // 使用有效 RTSP 路径
        const char *valid_path = rtsp_valid_paths[random() % (sizeof(rtsp_valid_paths)/sizeof(rtsp_valid_paths[0]))];
        int path_len = strlen(valid_path);
        memcpy(buf + offset, valid_path, path_len < available_len ? path_len : available_len);
    } else {
        // 使用原有的攻击路径策略
        // ... 原有代码 ...
    }
}
```

### 方案 2: 协议感知的 PATH 变异

根据协议类型动态调整 PATH 变异策略：

```c
// 在变异函数中检测协议类型
if (is_rtsp_protocol) {
    // RTSP: 优先保留/变异有效媒体流名称
    mutate_rtsp_path_with_valid_streams(buf, offset, available_len);
} else {
    // 其他协议: 使用通用路径攻击策略
    mutate_path_generic(buf, offset, available_len);
}
```

### 方案 3: 从种子中提取有效路径

在变异前分析种子文件，提取所有出现的有效路径，并将其加入变异池：

```c
// 解析种子文件，提取 RTSP URL 路径
char **extract_valid_rtsp_paths(char *seed_file) {
    // 解析种子，提取所有 rtsp://... 路径
    // 返回路径数组
}

// 在变异时使用提取的路径
char **valid_paths = extract_valid_rtsp_paths(current_seed);
if (valid_paths && random() % 3 == 0) {
    // 30% 概率使用种子中的有效路径
    use_extracted_path(valid_paths);
}
```

### 方案 4: 改进 LLM 生成的语法模板

在生成语法模板时，为 RTSP 协议提供更具体的 PATH 约束：

```python
# 在 prompt 中添加 RTSP 特定的路径示例
"For RTSP protocol, PATH should include valid media stream names like:
- rtsp://127.0.0.1:8554/mp3AudioTest
- rtsp://127.0.0.1:8554/ac3AudioTest
- rtsp://127.0.0.1:8554/mpeg1or2AudioVideoTest
Use <<PATH>> constraint but ensure mutations preserve valid stream names."
```

## 实施优先级

1. **高优先级**: 方案 1 - 直接在 PATH 变异中添加有效 RTSP 路径
2. **中优先级**: 方案 3 - 从种子中动态提取有效路径
3. **低优先级**: 方案 2 和 4 - 需要更大的架构改动

## 预期效果

实施方案 1 后，预期可以：
- 恢复 MP3 相关代码的覆盖率（从 0% 提升到 50-70%）
- 恢复 MPEG 相关代码的覆盖率（从 0% 提升到 60-80%）
- 总体行覆盖率从 17.8% 提升到 20-22%
- 总体分支覆盖率从 10.8% 提升到 12-14%

## 验证方法

1. 实施修改后重新运行 fuzzing 实验
2. 对比覆盖率报告，检查 MP3/AC3/MPEG 相关文件的覆盖率是否恢复
3. 分析生成的测试用例，确认是否包含有效的媒体流路径
4. 与 AFLNet 的覆盖率进行对比，评估改进效果

