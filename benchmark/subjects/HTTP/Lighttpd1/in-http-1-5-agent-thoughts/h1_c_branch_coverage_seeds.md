# h1.c 分支覆盖种子总结

## 概述

基于 `h1.c` (HTTP/1.x协议层) 的代码分析，创建了10个种子文件，专门针对关键逻辑分支，提升代码覆盖率。

## 关键逻辑分支分析

### 1. h1_send_headers() 分支 (line 152-261)
- **keep-alive处理** (line 156-168): 根据请求数和请求体长度决定keep-alive
- **Connection头设置** (line 170-187): Upgrade, close, keep-alive
- **304状态码处理** (line 189-193): 移除Content-Encoding
- **Date头添加** (line 227-239): HTTP/1.1必须Date头
- **Server头添加** (line 241-243): 可选Server头
- **小响应优化** (line 255-260): <16KB的完整响应优化

### 2. h1_recv_headers() 分支 (line 368-509)
- **keep-alive请求处理** (line 379-393): 多请求连接的空白行处理
- **管道请求处理** (line 375, 384): 管道请求检测
- **空白行丢弃** (line 425-435): POST后的空白行处理
- **HTTP/2连接前言检测** (line 489-494): "PRI * HTTP/2.0"检测
- **Upgrade头检查** (line 503-506): Upgrade到HTTP/2

### 3. h1_check_upgrade() 分支 (line 312-364)
- **Upgrade: h2c处理**: HTTP/2 cleartext升级
- **HTTP2-Settings检查**: 必须包含HTTP2-Settings
- **Connection头处理**: 移除Upgrade和HTTP2-Settings token

### 4. h1_check_expect_100() 分支 (line 514-539)
- **Expect: 100-continue处理**: 发送100 Continue响应
- **条件检查**: HTTP/1.0不支持，需要没有请求体数据

### 5. h1_chunked() 分支 (line 672-820)
- **chunked传输编码解析**: 解析chunk大小
- **trailer处理**: 处理chunked trailer
- **chunk大小检查**: 防止溢出
- **chunk扩展**: 处理chunk扩展参数

### 6. h1_reqbody_read() 分支 (line 839-923)
- **Content-Length读取**: 固定长度请求体
- **chunked读取**: 分块传输编码
- **未知长度读取**: 无Content-Length的读取
- **流式请求体**: 流式处理大请求体

## 创建的种子文件

### 1. `http_requests_expect_100_continue.raw`
**目标分支**: h1_check_expect_100() (line 514-539)
**覆盖逻辑**:
- `Expect: 100-continue` 头
- Content-Length请求体
- Transfer-Encoding: chunked请求体
- 触发100 Continue响应

**预期提升**: `h1_send_100_continue()` 和 `h1_check_expect_100()` 覆盖率

### 2. `http_requests_chunked_trailers.raw`
**目标分支**: h1_chunked_trailers() (line 607-668)
**覆盖逻辑**:
- chunked传输编码
- Trailer头声明
- trailer数据解析
- trailer合并到请求头

**预期提升**: `h1_chunked_trailers()` 覆盖率

### 3. `http_requests_chunked_variants.raw`
**目标分支**: h1_chunked() (line 672-820)
**覆盖逻辑**:
- 空chunk (0)
- 正常chunk
- chunk扩展参数
- 不同chunk大小

**预期提升**: `h1_chunked()` 中各种chunk解析分支

### 4. `http_requests_keepalive_sequence.raw`
**目标分支**: h1_recv_headers() keep-alive处理 (line 379-393)
**覆盖逻辑**:
- 多个keep-alive请求
- 请求间空白行处理
- keep-alive连接复用

**预期提升**: keep-alive请求处理逻辑

### 5. `http_requests_upgrade_h2c.raw`
**目标分支**: h1_check_upgrade() (line 312-364)
**覆盖逻辑**:
- `Upgrade: h2c` with HTTP2-Settings
- `Upgrade: websocket`
- `Upgrade: h2c` without HTTP2-Settings (应该被忽略)

**预期提升**: `h1_check_upgrade()` 覆盖率

### 6. `http_requests_304_not_modified.raw`
**目标分支**: h1_send_headers() 304处理 (line 189-193)
**覆盖逻辑**:
- 304 Not Modified响应
- If-None-Match条件请求
- If-Modified-Since条件请求
- Content-Encoding头移除

**预期提升**: 304状态码特殊处理逻辑

### 7. `http_requests_connection_close_sequence.raw`
**目标分支**: h1_send_headers() Connection处理 (line 176-187)
**覆盖逻辑**:
- `Connection: close` 设置
- HTTP/1.0默认close
- POST with close

**预期提升**: Connection头处理分支

### 8. `http_requests_large_body.raw`
**目标分支**: h1_reqbody_read() 大请求体处理 (line 886-899)
**覆盖逻辑**:
- >64KB请求体 (触发tempfile)
- 不同大小的请求体
- 流式处理路径

**预期提升**: 大请求体处理逻辑

### 9. `http_requests_pipelined.raw`
**目标分支**: h1_recv_headers() 管道请求 (line 375, 384)
**覆盖逻辑**:
- 管道请求序列
- 多个GET请求
- POST请求在管道中
- 管道请求检测

**预期提升**: 管道请求处理逻辑

### 10. `http_requests_http10_keepalive.raw`
**目标分支**: h1_send_headers() HTTP/1.0 keep-alive (line 183-187)
**覆盖逻辑**:
- HTTP/1.0 with keep-alive
- HTTP/1.0 without Host
- HTTP/1.0 Connection头设置

**预期提升**: HTTP/1.0 keep-alive处理

### 11. `http_requests_chunked_extensions.raw`
**目标分支**: h1_chunked() chunk扩展 (line 702-706)
**覆盖逻辑**:
- chunk扩展参数
- 不同扩展格式
- chunk扩展解析

**预期提升**: chunk扩展处理逻辑

## 预期覆盖率提升

### h1.c 关键函数
- **h1_send_headers()**: 22.0% → 35-40%
- **h1_recv_headers()**: 提升keep-alive和管道处理
- **h1_check_upgrade()**: 提升Upgrade处理
- **h1_check_expect_100()**: 提升Expect处理
- **h1_chunked()**: 提升chunked解析
- **h1_reqbody_read()**: 提升请求体读取

### 关键分支覆盖
- ✅ Expect: 100-continue处理
- ✅ chunked传输编码
- ✅ chunked trailer处理
- ✅ keep-alive请求序列
- ✅ Upgrade: h2c处理
- ✅ 304 Not Modified处理
- ✅ Connection头处理
- ✅ 大请求体处理
- ✅ 管道请求处理
- ✅ HTTP/1.0 keep-alive
- ✅ chunk扩展参数

## 文件统计

- **总文件数**: 11个
- **总请求数**: 约40+个HTTP请求
- **平均文件大小**: 200-400字节
- **特点**: 针对HTTP/1.x协议层特性

## 使用建议

1. **优先使用**: 这些种子针对h1.c的关键分支，应该优先使用
2. **组合使用**: 可以与其他种子文件组合使用
3. **持续fuzzing**: 让fuzzer基于这些种子进行深度探索

---

**创建日期**: 2025年1月5日
**基于代码**: `lighttpd1.4/src/h1.c`
**目标**: 提升h1.c的分支覆盖率

