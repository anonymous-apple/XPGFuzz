# array.c 分支覆盖分析

## 文件概述

`array.c` 实现了动态数组数据结构，主要用于存储HTTP headers。包含二分查找、插入、替换、匹配等功能。

## 关键函数和分支分析

### 1. `array_get_index()` / `array_get_index_ext()` - 二分查找

**关键分支**：
- **line 230/264**: `lower != upper` - 循环条件
- **line 237/272**: `cmp < 0` - key < [probe]，设置 `upper = probe`
- **line 239/274**: `cmp > 0` - key > [probe]，设置 `lower = probe + 1`
- **line 241/276**: `cmp == 0` - 找到，返回位置
- **line 245/280**: 未找到，返回 `-(int)lower - 1`
- **line 234**: `ext|x` - ext参数处理

**覆盖种子**: `array_binary_search`, `array_sorted_insert`

### 2. `array_caseless_compare()` - 大小写不敏感比较

**关键分支**：
- **line 192**: `ca == cb` - 直接相等，continue
- **line 195**: `light_isupper(ca)` - 大写转小写
- **line 196**: `light_isupper(cb)` - 大写转小写
- **line 198**: `ca == cb` - 转小写后相等，continue
- **line 199**: 返回差值

**覆盖种子**: `array_case_insensitive`

### 3. `array_insert_data_at_pos()` - 插入数据

**关键分支**：
- **line 349**: `a->used < a->size` - 有空间
  - **line 351**: `prev != NULL` - 需要释放旧数据
- **line 354**: `else` - 需要扩展数组
  - **line 355**: `array_extend(a, 16)` - 扩展16个元素
- **line 364**: `ndx` - 需要memmove
  - **line 365**: `memmove()` - 移动元素

**覆盖种子**: `array_extend`, `array_sorted_insert`

### 4. `array_get_unused_element()` - 获取未使用元素

**关键分支**：
- **line 323**: `a->used < a->size` - 有未使用元素
- **line 324**: `NULL != du && du->type == t` - 类型匹配，可重用
- **line 325**: 设置 `a->data[a->used] = NULL`
- **line 328**: 返回NULL，需要新建

**覆盖种子**: `array_duplicate_insert` (触发重用)

### 5. `array_insert_string_at_pos()` - 插入字符串

**关键分支**：
- **line 382**: `array_get_unused_element()` - 尝试重用
- **line 383**: `NULL == ds` - 需要新建
  - **line 383**: `array_data_string_init()` - 创建新元素

**覆盖种子**: `array_duplicate_insert`, `array_replace`

### 6. `array_extract_element_klen()` - 提取元素

**关键分支**：
- **line 297**: `ipos < 0` - 未找到，返回NULL
- **line 302**: `last_ndx != (uint32_t)ipos` - 需要memmove
  - **line 304**: `memmove()` - 移动元素
- **line 307**: `entry != a->data[last_ndx]` - 需要查找
  - **line 311**: `while (entry != a->data[ndx])` - 查找位置
  - **line 312**: 交换元素

**覆盖种子**: `array_replace`

### 7. `array_replace()` - 替换元素

**关键分支**：
- **line 446**: `NULL == oldp` - 新插入
- **line 446**: `NULL != oldp` - 替换
  - **line 451**: `for (uint32_t i = 0; i < a->used; ++i)` - 查找旧元素
  - **line 452**: `a->data[i] == old` - 找到，替换
  - **line 459**: `old->fn->free(old)` - 释放旧元素

**覆盖种子**: `array_replace`

### 8. `array_insert_unique()` - 唯一插入

**关键分支**：
- **line 465**: `NULL != old` - 已存在
  - **line 466**: `entry->fn->insert_dup` - 有insert_dup函数
    - **line 468**: `entry->fn->insert_dup(*old, entry)` - 合并值
  - **line 470**: `entry->fn->free(entry)` - 释放新元素
- **line 465**: `NULL == old` - 不存在，插入

**覆盖种子**: `array_duplicate_insert`

### 9. `array_match_key_prefix_klen()` - 前缀匹配

**关键分支**：
- **line 515**: `for (uint32_t i = 0; i < a->used; ++i)` - 遍历
- **line 518**: `klen <= slen && 0 == memcmp()` - 前缀匹配

**覆盖种子**: `array_prefix_match`

### 10. `array_match_key_suffix_klen()` - 后缀匹配

**关键分支**：
- **line 585**: `for (uint32_t i = 0; i < a->used; ++i)` - 遍历
- **line 588**: `klen <= blen && 0 == memcmp(end - klen, key->ptr, klen)` - 后缀匹配

**覆盖种子**: `array_suffix_match`

### 11. `array_match_path_or_ext()` - 路径/扩展名匹配

**关键分支**：
- **line 644**: `for (uint32_t i = 0; i < a->used; ++i)` - 遍历
- **line 649**: `*(key->ptr) == '/'` - 路径匹配（从开头）
- **line 649**: `else` - 扩展名匹配（从结尾）

**覆盖种子**: (在配置中使用，不在HTTP请求中)

### 12. `array_keycmp()` - 键比较

**关键分支**：
- **line 206**: `alen < blen` - 返回-1
- **line 206**: `alen > blen` - 返回1
- **line 206**: `alen == blen` - 调用 `array_caseless_compare()`

**覆盖种子**: `array_key_lengths`, `array_sorted_insert`

## 创建的种子文件（10个）

### 1. `http_requests_array_binary_search.raw` (456B)
**目标**: 覆盖二分查找的不同路径
**包含**:
- 多个header，触发二分查找
- 不同查找位置（开头、中间、结尾）
**预期覆盖**:
- ✅ `array_get_index()` - 二分查找
- ✅ line 272-277: cmp < 0, cmp > 0, cmp == 0
- ✅ line 230: lower != upper 循环

### 2. `http_requests_array_case_insensitive.raw` (456B)
**目标**: 覆盖大小写不敏感比较
**包含**:
- 相同header的不同大小写变体
**预期覆盖**:
- ✅ `array_caseless_compare()` - 大小写不敏感比较
- ✅ line 192: ca == cb (直接相等)
- ✅ line 195-196: 大写转小写
- ✅ line 198: 转小写后相等

### 3. `http_requests_array_duplicate_insert.raw` (456B)
**目标**: 覆盖重复header插入
**包含**:
- 多个相同名称的header
**预期覆盖**:
- ✅ `array_insert_unique()` - 唯一插入
- ✅ line 465: old != NULL (已存在)
- ✅ line 466: insert_dup函数调用
- ✅ `array_get_unused_element()` - 元素重用

### 4. `http_requests_array_replace.raw` (456B)
**目标**: 覆盖元素替换
**包含**:
- 相同header的不同值（触发替换）
**预期覆盖**:
- ✅ `array_replace()` - 替换元素
- ✅ line 446: oldp != NULL (替换)
- ✅ line 451-456: 查找和替换旧元素
- ✅ line 459: 释放旧元素

### 5. `http_requests_array_sorted_insert.raw` (456B)
**目标**: 覆盖排序插入
**包含**:
- 不同顺序的header（触发排序插入）
**预期覆盖**:
- ✅ `array_insert_data_at_pos()` - 插入到指定位置
- ✅ line 364: ndx != 0 (需要memmove)
- ✅ line 365: memmove()调用

### 6. `http_requests_array_extend.raw` (456B)
**目标**: 覆盖数组扩展
**包含**:
- 大量header（超过初始容量）
**预期覆盖**:
- ✅ `array_extend()` - 数组扩展
- ✅ line 354: a->used >= a->size (需要扩展)
- ✅ line 355: array_extend(a, 16)

### 7. `http_requests_array_key_lengths.raw` (456B)
**目标**: 覆盖不同长度的key
**包含**:
- 短key（TE, Age）
- 中等key（Host, Accept-Ranges）
- 长key（Strict-Transport-Security）
**预期覆盖**:
- ✅ `array_keycmp()` - 键长度比较
- ✅ line 206: alen < blen, alen > blen, alen == blen

### 8. `http_requests_array_prefix_match.raw` (456B)
**目标**: 覆盖前缀匹配
**包含**:
- 相同前缀的header（X-Forwarded-*, Accept-*, Content-*, If-*）
**预期覆盖**:
- ✅ `array_match_key_prefix_klen()` - 前缀匹配
- ✅ line 518: klen <= slen && memcmp()匹配

### 9. `http_requests_array_suffix_match.raw` (456B)
**目标**: 覆盖后缀匹配
**包含**:
- 相同后缀的header（*-Options, *-ID, *-For）
**预期覆盖**:
- ✅ `array_match_key_suffix_klen()` - 后缀匹配
- ✅ line 588: klen <= blen && memcmp()匹配

### 10. `http_requests_array_empty_blank.raw` (456B)
**目标**: 覆盖空值和空白值
**包含**:
- 空header值
- 空白header值（空格、制表符）
**预期覆盖**:
- ✅ buffer处理
- ✅ 空值检查

### 11. `http_requests_array_mixed_operations.raw` (456B)
**目标**: 覆盖混合操作
**包含**:
- 多种header组合
- 复杂场景
**预期覆盖**:
- ✅ 所有函数的组合使用
- ✅ 复杂场景处理

## 分支覆盖矩阵

| 函数/分支 | 覆盖种子 | 预期覆盖 |
|---------|---------|---------|
| `array_get_index()` | | |
| - cmp < 0 (272) | binary_search, sorted_insert | ✅ |
| - cmp > 0 (274) | binary_search, sorted_insert | ✅ |
| - cmp == 0 (276) | binary_search | ✅ |
| `array_caseless_compare()` | | |
| - ca == cb (192) | case_insensitive | ✅ |
| - light_isupper() (195-196) | case_insensitive | ✅ |
| `array_insert_data_at_pos()` | | |
| - used < size (349) | sorted_insert | ✅ |
| - prev != NULL (351) | duplicate_insert | ✅ |
| - else (354) | extend | ✅ |
| - ndx != 0 (364) | sorted_insert | ✅ |
| `array_get_unused_element()` | | |
| - used < size (323) | duplicate_insert | ✅ |
| - du != NULL && type == t (324) | duplicate_insert | ✅ |
| `array_replace()` | | |
| - oldp != NULL (446) | replace | ✅ |
| - 查找旧元素 (451-456) | replace | ✅ |
| `array_insert_unique()` | | |
| - old != NULL (465) | duplicate_insert | ✅ |
| - insert_dup (466) | duplicate_insert | ✅ |
| `array_match_key_prefix_klen()` | prefix_match | ✅ |
| `array_match_key_suffix_klen()` | suffix_match | ✅ |

## 预期覆盖率提升

### array.c 关键函数
- **array_get_index()**: 提升二分查找覆盖率
- **array_caseless_compare()**: 提升大小写不敏感比较
- **array_insert_data_at_pos()**: 提升插入操作（扩展、memmove）
- **array_get_unused_element()**: 提升元素重用
- **array_replace()**: 提升元素替换
- **array_insert_unique()**: 提升唯一插入
- **array_match_*()**: 提升匹配函数

### 关键分支覆盖
- ✅ 二分查找的所有路径（<, >, ==）
- ✅ 大小写不敏感比较
- ✅ 数组扩展
- ✅ 元素重用 vs 新建
- ✅ 元素替换
- ✅ 排序插入（memmove）
- ✅ 前缀/后缀匹配

## 文件统计

- **总文件数**: 11个
- **总请求数**: 约50+个HTTP请求
- **平均文件大小**: 400-500字节
- **特点**: 专门针对array.c的不同分支路径

## 使用建议

1. **优先使用**: 这些种子针对array.c的关键分支，应该优先使用
2. **组合使用**: 可以与其他种子文件组合使用
3. **持续fuzzing**: 让fuzzer基于这些种子进行深度探索
4. **注意**: array.c主要用于HTTP header存储，这些请求会触发各种array操作

---

**创建日期**: 2025年1月5日
**基于代码**: `lighttpd1.4/src/array.c`
**目标**: 提升 `array.c` 文件的分支覆盖率

