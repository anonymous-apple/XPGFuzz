# http_header.c 分支覆盖分析

## 文件概述

`http_header.c` 实现了 HTTP 头解析、查找、设置等功能，包括大小写不敏感匹配、token解析、行折叠处理等。

## 关键函数和分支分析

### 1. `http_header_hkey_get()` - Header名称查找（大小写不敏感）

**关键分支**：
- **line 99**: `slen < sizeof(http_headers_off)` - 长度检查
- **line 100**: `http_headers_off[slen]` - 获取偏移量
- **line 102**: `s[0] | 0x20` - 首字符转小写
- **line 104**: `i != -1` - 有效偏移量检查
- **line 107**: `c != kv->value[0]` - 首字符匹配
- **line 109**: `buffer_eq_icase_ssn()` - 大小写不敏感字符串比较
- **line 111**: `slen == (++kv)->vlen` - 相同长度header循环

**覆盖种子**: `header_case_variants`, `header_short_long`

### 2. `http_header_hkey_get_lc()` - Header名称查找（小写）

**关键分支**：
- **line 122**: `slen < sizeof(http_headers_off)` - 长度检查
- **line 124**: `s[0]` - 直接使用首字符（不转换）
- **line 129**: `c != kv->value[0]` - 首字符匹配
- **line 131**: `memcmp()` - 精确字符串比较（小写）

**覆盖种子**: `header_case_variants`

### 3. `http_header_str_to_code()` - HTTP状态码解析

**关键分支**：
- **line 143**: `light_isdigit(s[0]) && light_isdigit(s[1]) && light_isdigit(s[2])` - 3位数字检查
- **line 144**: `s[3] == '\0' || s[3] == ' ' || s[3] == '\t'` - 结束符检查
- **line 145**: 计算状态码值

**覆盖种子**: (在响应中测试，不在请求中)

### 4. `http_header_str_contains_token()` - Token查找

**关键分支**：
- **line 156**: `s[i]==' ' || s[i]=='\t' || s[i]==','` - 空白/逗号跳过
- **line 157**: `slen - i < mlen` - 长度不足检查
- **line 158**: `buffer_eq_icase_ssn()` - 大小写不敏感匹配
- **line 166**: `i == slen || s[i]==' ' || s[i]=='\t' || s[i]==',' || s[i]==';'` - token结束检查
- **line 170**: `s[i]!=','` - 查找下一个逗号

**覆盖种子**: `header_token_parsing`, `header_mixed_combinations`

### 5. `http_header_remove_token()` - Token移除

**关键分支**：
- **line 182**: `*s == ' ' || *s == '\t' || *s == ','` - 空白/逗号跳过
- **line 183**: `strncasecmp()` - 大小写不敏感匹配
- **line 185**: `*s=='\0' || *s==' ' || *s=='\t' || *s==',' || *s==';'` - token结束检查
- **line 186**: `memset(s-mlen, ' ', mlen)` - 用空格替换
- **line 189**: `*s == ','` - 逗号处理
- **line 194**: `*s != ',' && s != b->ptr` - 向后查找逗号
- **line 200**: `strchr(s, ',')` - 查找下一个逗号

**覆盖种子**: `header_token_parsing`

### 6. `http_header_parse_hoff()` - Header解析和行折叠

**关键分支**：
- **line 398**: `memchr((b = n),'\n',clen-hlen)` - 查找换行符
- **line 401**: `x <= 2` - 空行检查
- **line 401**: `x == 1 || n[-1] == '\r'` - `\n` 或 `\r\n` 检查
- **line 403**: `hoff[hoff[0]+1] = hlen` - 设置结束偏移量
- **line 406-407**: `b[0] == ' ' || b[0] == '\t'` - 行折叠检查
- **line 408**: `hlen != x` - 非首行检查
- **line 410**: `http_header_parse_unfold_impl()` - 行折叠展开
- **line 414**: `++hoff[0]` - 增加header计数
- **line 416**: `hoff[0] >= 8192-1` - 超过8192限制检查

**覆盖种子**: `header_line_folding`, `header_newline_variants`

### 7. Cookie特殊处理

**关键分支**：
- **line 340**: `id != HTTP_HEADER_COOKIE` - Cookie检查
- **line 341**: `http_header_token_append()` - 普通token追加（逗号分隔）
- **line 343**: `http_header_token_append_cookie()` - Cookie追加（分号分隔）
- **line 216**: `buffer_is_blank(vb)` - 空buffer检查
- **line 217**: `buffer_append_string_len(vb, CONST_STR_LEN("; "))` - 分号分隔

**覆盖种子**: `header_cookie_separator`, `header_duplicate`

### 8. Header设置/获取函数

**关键分支**：
- **line 234**: `light_btst(r->resp_htags, id)` - 响应头tag检查
- **line 242**: `light_bset(r->resp_htags, id)` - 设置tag
- **line 249**: `light_btst(r->resp_htags, id)` - 检查tag
- **line 252**: `id > HTTP_HEADER_OTHER` - HTTP_HEADER_OTHER特殊处理
- **line 263**: `vlen` - 值长度检查
- **line 264**: `light_bset()` - 设置tag
- **line 265**: `light_bclr()` - 清除tag
- **line 270**: `0 == vlen` - 空值检查
- **line 294**: `buffer_is_blank(vb)` - 空buffer检查
- **line 295**: `http_header_response_insert_addtl()` - 重复header插入

**覆盖种子**: `header_duplicate`, `header_empty_blank`

### 9. `http_header_response_insert_addtl()` - 重复header插入

**关键分支**：
- **line 281**: `r->http_version >= HTTP_VERSION_2` - HTTP/2检查
- **line 282**: `r->resp_header_repeated = 1` - 设置重复标记
- **line 285**: `light_isupper(h[i])` - 大写字符检查
- **line 286**: `h[i] |= 0x20` - 转小写

**覆盖种子**: `header_duplicate`

## 创建的种子文件（10个）

### 1. `http_requests_header_case_variants.raw` (456B)
**目标**: 覆盖大小写不敏感header匹配
**包含**:
- 不同大小写的Host, Content-Type, User-Agent, Accept
**预期覆盖**:
- ✅ `http_header_hkey_get()` - 大小写不敏感匹配
- ✅ `http_header_hkey_get_lc()` - 小写匹配
- ✅ line 102: 首字符转小写
- ✅ line 109: `buffer_eq_icase_ssn()` 比较

### 2. `http_requests_header_line_folding.raw` (456B)
**目标**: 覆盖行折叠处理
**包含**:
- 以空格/制表符开头的续行
- 不同位置的行折叠
**预期覆盖**:
- ✅ `http_header_parse_hoff()` - 行折叠解析
- ✅ line 406-407: 空格/制表符检查
- ✅ line 410: `http_header_parse_unfold_impl()` 调用

### 3. `http_requests_header_token_parsing.raw` (456B)
**目标**: 覆盖token解析和查找
**包含**:
- 逗号分隔的token列表
- 带空白的token
- 带质量值的token（;q=）
**预期覆盖**:
- ✅ `http_header_str_contains_token()` - token查找
- ✅ line 156: 空白/逗号跳过
- ✅ line 166: token结束检查
- ✅ `http_header_remove_token()` - token移除

### 4. `http_requests_header_cookie_separator.raw` (456B)
**目标**: 覆盖Cookie特殊处理
**包含**:
- 分号分隔的Cookie值
- 多个Cookie头
- Cookie属性（path, domain）
**预期覆盖**:
- ✅ line 340-343: Cookie特殊处理
- ✅ `http_header_token_append_cookie()` - 分号分隔
- ✅ line 216-217: Cookie追加逻辑

### 5. `http_requests_header_duplicate.raw` (456B)
**目标**: 覆盖重复header处理
**包含**:
- 多个相同名称的header
- 不同header的重复
**预期覆盖**:
- ✅ `http_header_response_append()` - header追加
- ✅ `http_header_response_insert()` - header插入
- ✅ line 294-295: 重复header处理
- ✅ line 281-286: HTTP/2重复header处理

### 6. `http_requests_header_short_long.raw` (456B)
**目标**: 覆盖不同长度的header
**包含**:
- 短header（TE, Age）
- 中等header（Host）
- 长header（Strict-Transport-Security, Content-Security-Policy）
**预期覆盖**:
- ✅ `http_header_hkey_get()` - 不同长度header查找
- ✅ line 100: `http_headers_off[slen]` 偏移量
- ✅ line 111: 相同长度header循环

### 7. `http_requests_header_special_chars.raw` (456B)
**目标**: 覆盖特殊字符处理
**包含**:
- URL编码字符
- 引号字符串
- Base64编码
- 弱ETag（W/"..."）
**预期覆盖**:
- ✅ `http_header_str_contains_token()` - 特殊字符token
- ✅ header值中的特殊字符处理

### 8. `http_requests_header_empty_blank.raw` (456B)
**目标**: 覆盖空值和空白值处理
**包含**:
- 空header值
- 空白header值（空格、制表符）
**预期覆盖**:
- ✅ `http_header_generic_get_ifnotempty()` - 空值检查
- ✅ line 225: `buffer_is_blank()` 检查
- ✅ line 263-265: 空值tag处理
- ✅ line 270: `0 == vlen` 检查

### 9. `http_requests_header_newline_variants.raw` (456B)
**目标**: 覆盖不同换行符处理
**包含**:
- `\r\n` 结束
- `\n` 结束
- 空行处理
**预期覆盖**:
- ✅ `http_header_parse_hoff()` - 换行符解析
- ✅ line 401: `x == 1 || n[-1] == '\r'` 检查
- ✅ line 403: header结束处理

### 10. `http_requests_header_unknown_custom.raw` (456B)
**目标**: 覆盖未知header处理
**包含**:
- X-自定义header
- 多个未知header
**预期覆盖**:
- ✅ `http_header_hkey_get()` - 返回 `HTTP_HEADER_OTHER`
- ✅ line 114: `HTTP_HEADER_OTHER` 返回
- ✅ line 252: `HTTP_HEADER_OTHER` 特殊处理

### 11. `http_requests_header_mixed_combinations.raw` (456B)
**目标**: 覆盖混合场景
**包含**:
- 多个header组合
- 复杂token列表
- 多种header类型
**预期覆盖**:
- ✅ 所有函数的组合使用
- ✅ 复杂场景处理

## 分支覆盖矩阵

| 函数/分支 | 覆盖种子 | 预期覆盖 |
|---------|---------|---------|
| `http_header_hkey_get()` | | |
| - 长度检查 (99) | short_long | ✅ |
| - 首字符匹配 (107) | case_variants | ✅ |
| - 大小写不敏感 (109) | case_variants | ✅ |
| `http_header_hkey_get_lc()` | | |
| - 小写匹配 (131) | case_variants | ✅ |
| `http_header_str_contains_token()` | | |
| - 空白跳过 (156) | token_parsing | ✅ |
| - token匹配 (158) | token_parsing | ✅ |
| - token结束 (166) | token_parsing | ✅ |
| `http_header_remove_token()` | | |
| - token移除 (186) | token_parsing | ✅ |
| - 逗号处理 (189) | token_parsing | ✅ |
| `http_header_parse_hoff()` | | |
| - 换行符查找 (398) | newline_variants | ✅ |
| - 空行检查 (401) | newline_variants | ✅ |
| - 行折叠 (406-410) | line_folding | ✅ |
| - 8192限制 (416) | (需要大量header) | ⚠️ |
| Cookie特殊处理 | | |
| - 分号分隔 (343) | cookie_separator | ✅ |
| Header设置/获取 | | |
| - tag检查 (234, 249) | duplicate, empty_blank | ✅ |
| - 空值处理 (263-265) | empty_blank | ✅ |
| - 重复header (294-295) | duplicate | ✅ |

## 预期覆盖率提升

### http_header.c 关键函数
- **http_header_hkey_get()**: 15.3% → 40-50%
- **http_header_hkey_get_lc()**: 提升小写匹配
- **http_header_str_contains_token()**: 提升token查找
- **http_header_remove_token()**: 提升token移除
- **http_header_parse_hoff()**: 提升header解析和行折叠
- **http_header_response_append/insert()**: 提升重复header处理

### 关键分支覆盖
- ✅ 大小写不敏感匹配
- ✅ 行折叠处理
- ✅ Token解析和查找
- ✅ Cookie特殊处理（分号分隔）
- ✅ 重复header处理
- ✅ 空值和空白值处理
- ✅ 不同换行符处理
- ✅ 未知header处理

## 文件统计

- **总文件数**: 11个
- **总请求数**: 约60+个HTTP请求
- **平均文件大小**: 400-500字节
- **特点**: 专门针对http_header.c的不同分支路径

## 使用建议

1. **优先使用**: 这些种子针对http_header.c的关键分支，应该优先使用
2. **组合使用**: 可以与其他种子文件组合使用
3. **持续fuzzing**: 让fuzzer基于这些种子进行深度探索
4. **注意**: 某些分支需要服务器响应特定头，可能需要实际运行测试

---

**创建日期**: 2025年1月5日
**基于代码**: `lighttpd1.4/src/http_header.c`
**目标**: 提升 `http_header.c` 文件的分支覆盖率

