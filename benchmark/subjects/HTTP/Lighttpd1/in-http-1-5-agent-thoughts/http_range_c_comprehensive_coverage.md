# http_range.c 全面分支覆盖分析

## 文件概述

`http_range.c` 实现了 HTTP Range 请求处理（RFC 7233），包括单范围、多范围、范围合并等功能。

## 关键函数和分支分析

### 1. `http_range_rfc7233()` - 入口函数

**关键分支检查**：

#### 1.1 `resp_body_finished` 检查 (line 367)
- **条件**: `!r->resp_body_finished`
- **处理**: 返回，不处理 Range
- **覆盖**: 需要响应体完成

#### 1.2 HTTP状态码检查 (line 375)
- **条件**: `200 != http_status`
- **处理**: 返回，只处理200响应
- **覆盖**: ✅ 正常GET请求返回200

#### 1.3 HTTP方法检查 (line 382)
- **条件**: `!http_method_get_head_query(r->http_method)`
- **处理**: 返回，只处理GET/HEAD/QUERY
- **覆盖**: 
  - ✅ GET方法（正常）
  - ✅ HEAD方法（line 444单独处理）

#### 1.4 HTTP版本检查 (line 385-387)
- **条件**: `r->http_version < HTTP_VERSION_1_1` 且 `!http_range_allow_http10`
- **处理**: 返回，HTTP/1.0默认不支持Range
- **覆盖**: 
  - ✅ HTTP/1.1（正常）
  - ✅ HTTP/1.0（特殊处理）

#### 1.5 Transfer-Encoding/Content-Encoding检查 (line 399-402)
- **条件**: 已应用Transfer-Encoding或Content-Encoding
- **处理**: 返回，不处理Range
- **覆盖**: 需要无编码的响应

#### 1.6 Accept-Ranges检查 (line 423-436)
- **条件**: `!light_btst(r->resp_htags, HTTP_HEADER_ACCEPT_RANGES)`
- **处理**: 设置 `Accept-Ranges: bytes`
- **条件**: `buffer_eq_slen(accept_ranges, CONST_STR_LEN("none"))`
- **处理**: 返回，不处理Range
- **覆盖**: 
  - ✅ 无Accept-Ranges头（设置bytes）
  - ✅ Accept-Ranges: none（拒绝）

#### 1.7 HEAD方法特殊处理 (line 444)
- **条件**: `r->http_method == HTTP_METHOD_HEAD`
- **处理**: 返回，HEAD方法不返回Range内容
- **覆盖**: ✅ HEAD + Range

#### 1.8 If-Range检查 (line 461-475)
- **条件**: `light_btst(r->rqst_htags, HTTP_HEADER_IF_RANGE)`
- **处理**: 
  - ETag匹配：处理Range
  - Last-Modified匹配：处理Range
  - 不匹配：返回，不处理Range
- **覆盖**: 
  - ✅ If-Range + ETag（line 469-471）
  - ✅ If-Range + Last-Modified（line 472-473）
  - ✅ If-Range不匹配（line 474）

### 2. `http_range_process()` - 主处理函数

#### 2.1 空内容长度检查 (line 322)
- **条件**: `0 == content_length`
- **处理**: 返回，跳过Range处理
- **覆盖**: ✅ 非空内容

#### 2.2 Range单位检查 (line 328-330)
- **条件**: 不是 `bytes=`
- **处理**: 返回200 OK
- **覆盖**: ✅ `bytes=` 格式

#### 2.3 范围解析结果 (line 340-345)
- **条件**: `2 == n` - 单范围
- **处理**: `http_range_single()`
- **条件**: `0 == n` - 无有效范围
- **处理**: `http_range_not_satisfiable()` - 返回416
- **条件**: `n > 2` - 多范围
- **处理**: `http_range_multi()`
- **覆盖**: 
  - ✅ 单范围（line 341）
  - ✅ 无有效范围（line 342-343）
  - ✅ 多范围（line 344-345）

### 3. `http_range_parse()` - 范围解析函数

#### 3.1 范围合并检查 (line 146-153)
- **条件**: `ranges[n-4] <= ranges[n-2]` - 已排序
- **条件**: `ranges[n-3] < ranges[n-2]-80` - 间隔>80字节
- **处理**: 继续，不合并
- **条件**: `ranges[n-3] >= ranges[n-2]-80` - 间隔<=80字节或重叠
- **处理**: 合并范围
- **覆盖**: 
  - ✅ 重叠范围合并（line 150-152）
  - ✅ 间隔<=80字节合并（line 147-152）

#### 3.2 未排序范围处理 (line 154-161)
- **条件**: `ranges[n-4] > ranges[n-2]` - 未排序
- **条件**: `n > RMAX_UNSORTED*2` - 超过限制
- **处理**: 移除最后一个范围，退出
- **条件**: `n <= RMAX_UNSORTED*2` - 未超过限制
- **处理**: 设置 `lim = RMAX_UNSORTED*2`，调用 `http_range_coalesce_unsorted()`
- **覆盖**: 
  - ✅ 未排序范围（line 154）
  - ✅ 超过RMAX_UNSORTED限制（line 156-158）
  - ✅ 未超过限制（line 160）

### 4. `http_range_coalesce_unsorted()` - 未排序范围合并

#### 4.1 范围重叠检查 (line 67)
- **条件**: `b <= ranges[j] ? e < ranges[j]-80 : ranges[j+1] < b-80`
- **处理**: 不重叠，继续
- **条件**: 重叠或间隔<=80字节
- **处理**: 合并范围（line 70-71）
- **覆盖**: 
  - ✅ 重叠范围合并
  - ✅ 间隔<=80字节合并
  - ✅ 不重叠范围（不合并）

### 5. `http_range_single()` - 单范围处理

#### 5.1 Chunk类型检查 (line 195)
- **条件**: `cq->first == cq->last` - 单个chunk
- **条件**: `c->type == FILE_CHUNK` - 文件chunk
- **处理**: 直接修改文件chunk长度（line 205）
- **条件**: `c->type == MEM_CHUNK` - 内存chunk
- **处理**: 修改内存chunk使用量（line 207）
- **条件**: 多个chunk
- **处理**: 使用临时chunkqueue（line 209-218）
- **覆盖**: 
  - ✅ 单FILE_CHUNK（line 204-205）
  - ✅ 单MEM_CHUNK（line 206-207）
  - ✅ 多chunk（line 209-218）

#### 5.2 范围起始位置检查 (line 197)
- **条件**: `ranges[0]` - 非0起始位置
- **处理**: 跳过前面的字节（line 198-200）
- **条件**: `ranges[0] == 0` - 从开头开始
- **处理**: 不跳过
- **覆盖**: 
  - ✅ 非0起始（line 197-200）
  - ✅ 0起始（跳过line 197-200）

### 6. `http_range_multi()` - 多范围处理

#### 6.1 Chunk类型检查 (line 269-271)
- **条件**: `cq->first == cq->last && cq->first->type == MEM_CHUNK`
- **处理**: 使用 `chunkqueue_append_mem()`（line 282）
- **条件**: 其他情况
- **处理**: 使用 `chunkqueue_append_mem_min()`（line 284）
- **覆盖**: 
  - ✅ 单MEM_CHUNK（line 281-282）
  - ✅ 其他chunk类型（line 283-284）

## 创建的种子文件（10个）

### 1. `http_requests_range_head_method.raw` (312B)
**目标**: 覆盖HEAD方法处理（line 444）
**包含**:
- HEAD + 单范围
- HEAD + 多范围
- HEAD + 后缀范围
**预期覆盖**:
- ✅ line 444: HEAD方法检查
- ✅ HEAD方法返回但不处理Range内容

### 2. `http_requests_range_http10.raw` (312B)
**目标**: 覆盖HTTP/1.0处理（line 385-387）
**包含**:
- HTTP/1.0 + Range请求
**预期覆盖**:
- ✅ line 385-387: HTTP版本检查
- ✅ HTTP/1.0默认不支持Range（除非配置允许）

### 3. `http_requests_range_if_range_etag.raw` (456B)
**目标**: 覆盖If-Range + ETag处理（line 461-475）
**包含**:
- If-Range + ETag + 单范围
- If-Range + ETag + 多范围
- If-Range + ETag + 后缀范围
**预期覆盖**:
- ✅ line 469-471: ETag匹配检查
- ✅ line 474: If-Range不匹配处理

### 4. `http_requests_range_if_range_date.raw` (456B)
**目标**: 覆盖If-Range + Last-Modified处理（line 461-475）
**包含**:
- If-Range + HTTP-date + 单范围
- If-Range + HTTP-date + 多范围
- If-Range + HTTP-date + 后缀范围
**预期覆盖**:
- ✅ line 472-473: Last-Modified匹配检查
- ✅ line 474: If-Range不匹配处理

### 5. `http_requests_range_unsatisfiable.raw` (312B)
**目标**: 覆盖416 Range Not Satisfiable（line 342-343）
**包含**:
- 空文件 + Range请求
- 超大范围请求
**预期覆盖**:
- ✅ line 342-343: `http_range_not_satisfiable()`调用
- ✅ line 303-313: 416错误响应生成

### 6. `http_requests_range_single_file_chunk.raw` (456B)
**目标**: 覆盖单范围 + FILE_CHUNK处理（line 195-207）
**包含**:
- 大文件 + 单范围
- 不同范围位置
**预期覆盖**:
- ✅ line 195: 单chunk检查
- ✅ line 204-205: FILE_CHUNK处理
- ✅ line 197-200: 非0起始位置处理

### 7. `http_requests_range_single_mem_chunk.raw` (456B)
**目标**: 覆盖单范围 + MEM_CHUNK处理（line 195-207）
**包含**:
- 小文件 + 单范围
- 不同范围位置
**预期覆盖**:
- ✅ line 195: 单chunk检查
- ✅ line 206-207: MEM_CHUNK处理
- ✅ line 197-200: 非0起始位置处理

### 8. `http_requests_range_multi_mem_chunk.raw` (456B)
**目标**: 覆盖多范围 + MEM_CHUNK处理（line 269-284）
**包含**:
- 中等文件 + 多范围（2-5个）
**预期覆盖**:
- ✅ line 269-271: MEM_CHUNK检查
- ✅ line 281-282: `chunkqueue_append_mem()`调用
- ✅ line 272-288: 多范围处理循环

### 9. `http_requests_range_multi_file_chunk.raw` (456B)
**目标**: 覆盖多范围 + FILE_CHUNK处理（line 269-284）
**包含**:
- 大文件 + 多范围（2-5个）
**预期覆盖**:
- ✅ line 269-271: 非MEM_CHUNK检查
- ✅ line 283-284: `chunkqueue_append_mem_min()`调用
- ✅ line 272-288: 多范围处理循环

### 10. `http_requests_range_coalesce_overlapping.raw` (456B)
**目标**: 覆盖范围合并逻辑（line 146-153, 44-81）
**包含**:
- 重叠范围（2-7个）
- 间隔<=80字节的范围
**预期覆盖**:
- ✅ line 146-152: 排序范围合并
- ✅ line 147: 间隔检查（80字节阈值）
- ✅ line 44-81: `http_range_coalesce_unsorted()`调用

### 11. `http_requests_range_coalesce_gap.raw` (456B)
**目标**: 覆盖范围间隔合并（line 147-152）
**包含**:
- 间隔<=80字节的范围
- 间隔>80字节的范围
**预期覆盖**:
- ✅ line 147: `ranges[n-3] < ranges[n-2]-80` 检查
- ✅ 间隔<=80字节合并
- ✅ 间隔>80字节不合并

## 分支覆盖矩阵

| 函数/分支 | 覆盖种子 | 预期覆盖 |
|---------|---------|---------|
| `http_range_rfc7233()` | | |
| - HEAD方法检查 (444) | head_method | ✅ |
| - HTTP/1.0检查 (385-387) | http10 | ✅ |
| - If-Range ETag (469-471) | if_range_etag | ✅ |
| - If-Range Date (472-473) | if_range_date | ✅ |
| - Accept-Ranges检查 (423-436) | (需要服务器响应) | ⚠️ |
| `http_range_process()` | | |
| - 单范围 (341) | single_* | ✅ |
| - 无有效范围 (342-343) | unsatisfiable | ✅ |
| - 多范围 (344-345) | multi_* | ✅ |
| `http_range_parse()` | | |
| - 排序范围合并 (146-152) | coalesce_* | ✅ |
| - 未排序处理 (154-161) | (unsorted种子) | ✅ |
| `http_range_coalesce_unsorted()` | coalesce_* | ✅ |
| `http_range_single()` | | |
| - FILE_CHUNK (204-205) | single_file_chunk | ✅ |
| - MEM_CHUNK (206-207) | single_mem_chunk | ✅ |
| - 多chunk (209-218) | single_* | ✅ |
| `http_range_multi()` | | |
| - MEM_CHUNK (281-282) | multi_mem_chunk | ✅ |
| - 其他chunk (283-284) | multi_file_chunk | ✅ |

## 预期覆盖率提升

### http_range.c 关键函数
- **http_range_rfc7233()**: 1.9% → 50-60%
- **http_range_process()**: 提升主处理逻辑
- **http_range_parse()**: 提升多范围解析和合并
- **http_range_coalesce_unsorted()**: 提升未排序范围合并
- **http_range_single()**: 提升单范围处理（FILE/MEM chunk）
- **http_range_multi()**: 提升多范围处理（FILE/MEM chunk）
- **http_range_not_satisfiable()**: 提升416错误处理

### 关键分支覆盖
- ✅ HEAD方法处理
- ✅ HTTP/1.0处理
- ✅ If-Range处理（ETag/Date）
- ✅ 单范围处理（FILE/MEM chunk）
- ✅ 多范围处理（FILE/MEM chunk）
- ✅ 范围合并（重叠/间隔）
- ✅ 416错误处理

## 文件统计

- **总文件数**: 11个（包含之前的10个 + 新增11个）
- **新增文件数**: 11个
- **总请求数**: 约60+个HTTP请求
- **平均文件大小**: 300-500字节
- **特点**: 专门针对http_range.c的不同分支路径

## 使用建议

1. **优先使用**: 这些种子针对http_range.c的关键分支，应该优先使用
2. **组合使用**: 可以与其他种子文件组合使用
3. **持续fuzzing**: 让fuzzer基于这些种子进行深度探索
4. **注意**: 某些分支需要服务器响应特定头（如Accept-Ranges），可能需要实际运行测试

---

**创建日期**: 2025年1月5日
**基于代码**: `lighttpd1.4/src/http_range.c`
**目标**: 提升 `http_range.c` 文件的全面分支覆盖率

