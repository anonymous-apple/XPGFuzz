# http_range_parse_next() 函数分支覆盖分析

## 函数概述

`http_range_parse_next()` 函数解析 Range 头的单个范围规范，格式为 `bytes=start-end` 或 `bytes=-suffix`。

## 函数逻辑分支分析

### 主要分支路径

#### 1. 正数范围 (`n >= 0`, line 94)

**分支1.1**: `n != LLONG_MAX && n < len && s != e` (line 95)
- **条件**: 有效的起始位置
- **处理**: `ranges[0] = n` (line 96)
- **空白处理**: `while (*e == ' ' || *e == '\t') ++e` (line 97)

**分支1.1.1**: `*e == '-'` (line 98)
- **条件**: 有结束位置
- **处理**: 解析结束位置 `n = strtoll((s = e+1), &e, 10)` (line 99)

**分支1.1.1.1**: `s == e || (n == 0 && e[-1] != '0')` (line 100)
- **条件**: 无结束位置或无效结束位置
- **处理**: `ranges[1] = len-1` (line 101) - 到文件末尾

**分支1.1.1.2**: `ranges[0] <= n && n != LLONG_MAX` (line 102)
- **条件**: 有效结束位置
- **处理**: `ranges[1] = n < len ? n : len-1` (line 103)
  - **子分支**: `n < len` → 使用n
  - **子分支**: `n >= len` → 使用len-1

**分支1.2**: else (line 105)
- **条件**: 无效起始位置
- **处理**: `ranges[1] = -1` (invalid)

#### 2. 负数范围 (`n != LLONG_MIN`, line 107)

**分支2.1**: `len > -n` (line 108)
- **条件**: 后缀长度小于文件长度
- **处理**: `ranges[0] = len + n` (从文件末尾向前计算)

**分支2.2**: `len <= -n` (line 108)
- **条件**: 后缀长度大于等于文件长度
- **处理**: `ranges[0] = 0` (从文件开头开始)

**处理**: `ranges[1] = len-1` (line 109) - 总是到文件末尾

#### 3. 尾部空白处理 (line 111)
- **处理**: `while (*e == ' ' || *e == '\t') ++e` - 跳过尾部空白

#### 4. 返回值 (line 112)
- **返回**: `e` - 下一个字符位置（',' 或 '\0' 或无效字符）

## 创建的种子文件

### 1. `http_requests_range_comprehensive.raw`
**目标**: 覆盖所有主要分支
**包含**:
- `bytes=0-100` - 正常范围
- `bytes=100-200` - 正常范围
- `bytes=100-` - 无结束位置
- `bytes=-100` - 后缀范围
- `bytes=0-0` - 单字节范围
- `bytes=0-999999` - 超过文件长度
- `bytes=-1` - 单字节后缀
- `bytes= 0 - 100` - 带空白
- `bytes=0-100,200-300` - 多个范围
- `bytes=0-50,100-150,200-250` - 三个范围

**预期覆盖**:
- ✅ 正数范围 (line 94-105)
- ✅ 无结束位置 (line 100-101)
- ✅ 后缀范围 (line 107-110)
- ✅ 空白处理 (line 97, 111)
- ✅ 超过文件长度 (line 103)

### 2. `http_requests_range_edge_cases.raw`
**目标**: 边界情况
**包含**:
- `bytes=0-0` - 第一个字节
- `bytes=1-1` - 第二个字节
- `bytes=0-` - 从开头到末尾
- `bytes=1-` - 从第二个字节到末尾
- `bytes=-0` - 后缀0字节（特殊）
- `bytes=-1` - 最后一个字节
- `bytes=-999999` - 超大后缀
- `bytes=999999-9999999` - 超大范围
- `bytes=0-9999999` - 超大结束位置

**预期覆盖**:
- ✅ 边界值处理
- ✅ 超大值处理
- ✅ 后缀0的特殊情况 (line 100)

### 3. `http_requests_range_multiple.raw`
**目标**: 多个范围组合
**包含**:
- 2个范围
- 3个范围
- 重叠范围
- 相邻范围
- 5个范围
- 8个范围
- 9个范围

**预期覆盖**:
- ✅ `http_range_parse()` 的多范围处理
- ✅ 范围合并逻辑

### 4. `http_requests_range_whitespace.raw`
**目标**: 空白字符处理
**包含**:
- 起始空白: `bytes= 0-100`
- 中间空白: `bytes=0 -100`, `bytes=0- 100`
- 尾部空白: `bytes=0-100 `
- 多个空白: `bytes= 0 - 100 `
- Tab字符: `bytes=	0	-	100`
- 无结束位置空白: `bytes= 100 - `
- 后缀空白: `bytes= - 100`
- 范围间空白: `bytes=0-100, 200-300`

**预期覆盖**:
- ✅ line 97: 起始空白处理
- ✅ line 111: 尾部空白处理
- ✅ 各种空白位置组合

### 5. `http_requests_range_suffix_variants.raw`
**目标**: 后缀范围变体
**包含**:
- `bytes=-100` - 正常后缀
- `bytes=-1` - 单字节后缀
- `bytes=-10` - 小后缀
- `bytes=-999999` - 超大后缀
- `bytes=-0` - 后缀0（特殊）
- `bytes=-50,100-200` - 后缀+正常范围
- `bytes=0-100,-50` - 正常范围+后缀
- `bytes=-100,-50` - 多个后缀

**预期覆盖**:
- ✅ line 107-110: 后缀范围处理
- ✅ `len > -n` vs `len <= -n` 分支
- ✅ 后缀与其他范围组合

### 6. `http_requests_range_no_end.raw`
**目标**: 无结束位置的范围
**包含**:
- `bytes=0-` - 从开头
- `bytes=100-` - 从中间
- `bytes=50-` - 从中间
- `bytes=999999-` - 超大起始
- `bytes=0-,100-200` - 无结束+正常
- `bytes=100-,200-300` - 多个无结束
- `bytes=0-,50-,100-` - 多个无结束

**预期覆盖**:
- ✅ line 100-101: 无结束位置处理
- ✅ `s == e` 分支
- ✅ `n == 0 && e[-1] != '0'` 分支

### 7. `http_requests_range_boundary.raw`
**目标**: 边界值测试
**包含**:
- `bytes=0-0` - 第一个字节
- `bytes=1-1` - 第二个字节
- `bytes=0-1` - 前两个字节
- `bytes=1-2` - 第二和第三个字节
- `bytes=0-999999` - 超大结束位置
- `bytes=999999-9999999` - 超大范围
- `bytes=100-0` - 无效范围（结束<起始）
- `bytes=200-100` - 无效范围

**预期覆盖**:
- ✅ line 102: `ranges[0] <= n` 检查
- ✅ line 103: `n < len` vs `n >= len` 分支
- ✅ 无效范围处理

### 8. `http_requests_range_overlapping.raw`
**目标**: 重叠范围
**包含**:
- `bytes=0-100,50-150` - 部分重叠
- `bytes=0-100,100-200` - 相邻
- `bytes=0-100,90-190` - 重叠
- `bytes=0-50,25-75,50-100` - 三个重叠
- `bytes=0-100,80-120,100-200` - 多个重叠
- `bytes=0-100,0-200` - 包含关系
- `bytes=0-200,0-100` - 包含关系（反向）

**预期覆盖**:
- ✅ `http_range_coalesce_unsorted()` 调用
- ✅ 范围合并逻辑

### 9. `http_requests_range_unsorted.raw`
**目标**: 未排序范围
**包含**:
- `bytes=200-300,0-100` - 反向排序
- `bytes=300-400,100-200,0-100` - 三个未排序
- 更多未排序组合

**预期覆盖**:
- ✅ line 154-161: 未排序范围处理
- ✅ `RMAX_UNSORTED` 限制
- ✅ `http_range_coalesce_unsorted()` 调用

### 10. `http_requests_range_mixed.raw`
**目标**: 混合类型范围
**包含**:
- `bytes=0-100,-50` - 正常+后缀
- `bytes=-100,200-300` - 后缀+正常
- `bytes=0-,100-200,-50` - 无结束+正常+后缀
- 更多混合组合

**预期覆盖**:
- ✅ 所有范围类型的组合
- ✅ 复杂场景处理

## 分支覆盖矩阵

| 分支条件 | 覆盖种子 | 预期覆盖 |
|---------|---------|---------|
| `n >= 0` | comprehensive, edge_cases | ✅ |
| `n != LLONG_MAX && n < len && s != e` | comprehensive, edge_cases | ✅ |
| `*e == '-'` | comprehensive, no_end | ✅ |
| `s == e` | no_end | ✅ |
| `n == 0 && e[-1] != '0'` | edge_cases (-0) | ✅ |
| `ranges[0] <= n && n != LLONG_MAX` | comprehensive, boundary | ✅ |
| `n < len` | comprehensive | ✅ |
| `n >= len` | edge_cases, boundary | ✅ |
| `n != LLONG_MIN` | suffix_variants | ✅ |
| `len > -n` | suffix_variants | ✅ |
| `len <= -n` | suffix_variants (-999999) | ✅ |
| 空白处理 | whitespace | ✅ |
| 多个范围 | multiple, overlapping, unsorted | ✅ |

## 预期覆盖率提升

### http_range.c 关键函数
- **http_range_parse_next()**: 1.9% → 60-70%
- **http_range_parse()**: 提升多范围处理
- **http_range_coalesce_unsorted()**: 提升范围合并
- **http_range_single()**: 提升单范围处理
- **http_range_multi()**: 提升多范围处理

### 关键分支覆盖
- ✅ 正数范围解析
- ✅ 负数范围解析（后缀）
- ✅ 无结束位置处理
- ✅ 空白字符处理
- ✅ 边界值处理
- ✅ 超过文件长度处理
- ✅ 多个范围处理
- ✅ 重叠范围合并
- ✅ 未排序范围处理

## 文件统计

- **总文件数**: 10个
- **总请求数**: 约80+个HTTP请求
- **平均文件大小**: 300-500字节
- **特点**: 专门针对Range请求解析

## 使用建议

1. **优先使用**: 这些种子针对http_range.c的关键分支，应该优先使用
2. **组合使用**: 可以与其他种子文件组合使用
3. **持续fuzzing**: 让fuzzer基于这些种子进行深度探索

---

**创建日期**: 2025年1月5日
**基于代码**: `lighttpd1.4/src/http_range.c` (line 84-113)
**目标**: 提升 `http_range_parse_next()` 函数的分支覆盖率

