# request.c 分支覆盖种子总结

## 概述

基于 `request.c` 的代码分析，创建了12个种子文件，专门针对关键逻辑分支，提升代码覆盖率。

## 关键逻辑分支分析

### 1. URI解析分支 (line 975-979, 584-607)
- **绝对URI**: `http://` 或 `https://` 开头的URI
- **相对URI**: 以 `/` 开头的URI
- **特殊URI**: CONNECT方法的URI格式

### 2. HTTP方法特殊处理 (line 1032-1039)
- **CONNECT方法**: 特殊URI处理
- **OPTIONS *方法**: 星号URI的特殊处理

### 3. Host头处理 (line 433-447, 1283-1293)
- **Host头重复检查**: 相同值忽略，不同值报错
- **Host头缺失**: HTTP/1.1必须，HTTP/1.0可选
- **Host头格式**: IPv4, IPv6, 域名

### 4. Content-Length处理 (line 472-490, 1305-1309)
- **POST请求验证**: HTTP/1.1 POST需要Content-Length或Transfer-Encoding
- **Content-Length重复**: 报错
- **Content-Length解析**: 数字解析

### 5. Transfer-Encoding处理 (line 491-516)
- **chunked编码**: 设置reqbody_length为-1
- **版本检查**: HTTP/1.0和HTTP/2不支持
- **与Content-Length冲突**: 严格模式下报错

### 6. Connection头处理 (line 457-471)
- **close**: 设置keep_alive=0
- **keep-alive**: 设置keep_alive=1
- **版本检查**: HTTP/2不支持Connection头

### 7. 条件请求头 (line 450-456, 395-407)
- **If-Modified-Since**: 重复检查
- **If-None-Match**: 重复时只保留第一个
- **If-Match**: 重复检查
- **If-Unmodified-Since**: 重复检查

### 8. GET/HEAD with body (line 1344-1347)
- **GET/HEAD不应该有body**: 除非启用METHOD_GET_BODY选项

### 9. URI字符检查 (line 985-991)
- **严格模式**: 检查控制字符
- **宽松模式**: 只检查NULL字符

### 10. URI规范化 (line 1043-1068)
- **路径简化**: `/../`, `./`, `//`
- **URL解码**: `%20`等编码字符
- **查询字符串提取**: `?`后的部分

## 创建的种子文件

### 1. `http_requests_absolute_uri.raw`
**目标分支**: URI解析 (line 584-607)
**覆盖逻辑**:
- 绝对URI `http://` 格式
- 绝对URI `https://` 格式
- Host头从URI中提取

**预期提升**: `http_request_parse_reqline_uri()` 覆盖率

### 2. `http_requests_options_star.raw`
**目标分支**: OPTIONS * 特殊处理 (line 1033-1035)
**覆盖逻辑**:
- `OPTIONS *` 请求
- HTTP/1.0和HTTP/1.1版本

**预期提升**: `http_request_parse_target()` 中OPTIONS *分支

### 3. `http_requests_post_no_content_length.raw`
**目标分支**: POST请求验证 (line 1305-1309)
**覆盖逻辑**:
- HTTP/1.0 POST without Content-Length (允许)
- HTTP/1.1 POST with Transfer-Encoding (允许)
- HTTP/1.1 POST without Content-Length (应该报411)

**预期提升**: POST验证逻辑覆盖率

### 4. `http_requests_connection_close.raw`
**目标分支**: Connection头处理 (line 457-471)
**覆盖逻辑**:
- `Connection: close` → keep_alive=0
- `Connection: keep-alive` → keep_alive=1
- HTTP/1.0 with keep-alive

**预期提升**: Connection头处理分支覆盖率

### 5. `http_requests_duplicate_headers.raw`
**目标分支**: 重复头检查 (line 378-409)
**覆盖逻辑**:
- Host头重复 (相同值忽略)
- Content-Type重复 (报错)
- If-None-Match重复 (只保留第一个)

**预期提升**: `http_request_parse_duplicate()` 覆盖率

### 6. `http_requests_query_string.raw`
**目标分支**: 查询字符串提取 (line 1079-1091)
**覆盖逻辑**:
- 单个查询参数
- 多个查询参数
- 空值参数
- 只有key没有value

**预期提升**: URI解析中查询字符串处理

### 7. `http_requests_url_encoded.raw`
**目标分支**: URL解码 (line 1099-1100)
**覆盖逻辑**:
- `%20` 空格编码
- `%2F` 斜杠编码
- `%3F` 问号编码
- `%26` 和号编码

**预期提升**: `buffer_urldecode_path()` 调用

### 8. `http_requests_content_length_variants.raw`
**目标分支**: Content-Length处理 (line 472-490, 1313-1343)
**覆盖逻辑**:
- Content-Length: 0
- Content-Length: 非零值
- Content-Length + Transfer-Encoding冲突

**预期提升**: Content-Length解析和冲突处理

### 9. `http_requests_get_with_body.raw`
**目标分支**: GET/HEAD with body检查 (line 1344-1347)
**覆盖逻辑**:
- GET with Content-Length (应该报错，除非启用METHOD_GET_BODY)
- HEAD with Content-Length (应该报错)

**预期提升**: GET/HEAD body验证逻辑

### 10. `http_requests_host_variants.raw`
**目标分支**: Host头处理 (line 105-180, 182-321)
**覆盖逻辑**:
- 域名格式
- 域名+端口
- IPv6地址 `[2001:db8::1]`
- IPv6地址+端口
- HTTP/1.0 without Host (允许)

**预期提升**: `http_request_host_normalize()` 和 `request_check_hostname()` 覆盖率

### 11. `http_requests_path_normalization.raw`
**目标分支**: 路径规范化 (line 1100)
**覆盖逻辑**:
- `/../` 路径回溯
- `./` 当前目录
- `//` 双斜杠
- 路径遍历攻击尝试

**预期提升**: `buffer_path_simplify()` 调用

### 12. `http_requests_conditional_headers.raw`
**目标分支**: 条件请求头 (line 450-456)
**覆盖逻辑**:
- If-Modified-Since
- If-None-Match
- If-Match
- If-Unmodified-Since

**预期提升**: 条件请求头处理覆盖率

## 预期覆盖率提升

### request.c 关键函数
- **http_request_parse_reqline()**: 4.3% → 12-15%
- **http_request_parse_headers()**: 提升重复头检查
- **http_request_parse_target()**: 提升URI解析
- **http_request_parse()**: 提升POST验证、GET/HEAD body检查
- **http_request_host_normalize()**: 提升Host规范化
- **http_request_parse_duplicate()**: 提升重复头处理

### 关键分支覆盖
- ✅ 绝对URI解析
- ✅ OPTIONS * 特殊处理
- ✅ POST Content-Length验证
- ✅ Connection头处理
- ✅ 重复头检查
- ✅ 查询字符串提取
- ✅ URL解码
- ✅ Content-Length变体
- ✅ GET/HEAD body检查
- ✅ Host头变体
- ✅ 路径规范化
- ✅ 条件请求头

## 文件统计

- **总文件数**: 12个
- **总请求数**: 约35+个HTTP请求
- **平均文件大小**: 150-250字节
- **特点**: 短小精悍，针对性强

## 使用建议

1. **优先使用**: 这些种子针对关键分支，应该优先使用
2. **组合使用**: 可以与其他种子文件组合使用
3. **持续fuzzing**: 让fuzzer基于这些种子进行深度探索

---

**创建日期**: 2025年1月5日
**基于代码**: `lighttpd1.4/src/request.c`
**目标**: 提升request.c的分支覆盖率

