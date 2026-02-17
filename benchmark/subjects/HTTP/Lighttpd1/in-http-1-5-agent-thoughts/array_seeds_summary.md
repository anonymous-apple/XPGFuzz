# array.c 种子生成总结

## 生成的种子文件（5个）

已生成5个用于覆盖 `array.c` 中逻辑分支的种子文件：

1. **http_requests_array_mimetypes.raw** - 多种文件扩展名
   - 覆盖：`array_match_value_suffix` 函数
   - 测试：.txt, .html, .jpg, .pdf, .css等不同扩展名
   - 触发：mimetype配置数组的匹配逻辑

2. **http_requests_array_multiple_headers.raw** - 多个相同头部
   - 覆盖：`array_insert_unique`, `array_get_index` 函数
   - 测试：多个Accept-Language, Accept-Encoding, Cache-Control头部
   - 触发：头部数组的插入和查找逻辑

3. **http_requests_array_accept_variants.raw** - Accept头部变体
   - 覆盖：`array_match_value_prefix`, 数组插入和查找
   - 测试：单个Accept头多个值，多个Accept头，Accept with quality values
   - 触发：Accept头部解析的数组处理

4. **http_requests_array_duplicate_headers.raw** - 重复头部
   - 覆盖：`array_insert_unique`, `array_data_string_insert_dup`
   - 测试：重复的User-Agent, Accept, Cookie头部
   - 触发：重复头部合并逻辑（insert_dup函数）

5. **http_requests_array_extensions_edge.raw** - 扩展名边界情况
   - 覆盖：`array_match_value_suffix`, 大小写处理
   - 测试：大写扩展名(.TXT, .HTML)，小写扩展名，无扩展名，超长扩展名
   - 触发：后缀匹配的不同分支

## 覆盖的分支

### array_get_index (二分查找)
- 种子2, 3, 4 - 多个头部触发查找逻辑
- 分支：cmp < 0, cmp > 0, cmp == 0, 未找到

### array_insert_data_at_pos
- 种子2, 3, 4 - 插入新头部
- 分支：重用槽位 vs 扩展数组，需要memmove vs 直接插入

### array_match_value_suffix (mimetype匹配)
- 种子1, 5 - 文件扩展名匹配
- 分支：不同扩展名长度的匹配

### array_insert_unique
- 种子2, 3, 4 - 重复头部处理
- 分支：已存在（insert_dup或free）vs 新插入

### array_get_unused_element
- 种子2, 3, 4 - 头部重用
- 分支：重用已存在元素 vs 创建新元素

### array_extend
- 种子2, 3, 4 - 数组扩展（如果头部数量超过初始大小）
- 分支：数组大小扩展逻辑

## 设计考虑

1. **mimetype匹配**：通过请求不同扩展名的文件触发 `array_match_value_suffix`
2. **头部数组**：通过多个头部触发数组的插入、查找、合并逻辑
3. **边界情况**：测试大小写、空值、超长值等边界条件
4. **重复处理**：测试相同头部的合并逻辑（insert_dup）

## 预期效果

这些种子应该能够：
- 触发array.c中的主要分支条件
- 测试数组的插入、查找、匹配操作
- 覆盖二分查找的不同路径
- 测试数组扩展和元素重用逻辑
- 测试前缀/后缀匹配的不同场景

