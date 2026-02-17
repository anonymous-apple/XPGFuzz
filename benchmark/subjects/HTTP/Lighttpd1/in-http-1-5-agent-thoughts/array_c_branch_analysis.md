# array.c 分支分析

## 关键函数和分支

### 1. array_get_index (行259-281) - 二分查找
- 分支：`cmp < 0` (upper = probe)
- 分支：`cmp > 0` (lower = probe + 1)  
- 分支：`cmp == 0` (找到，返回probe)
- 分支：未找到 (返回 -lower-1)

### 2. array_insert_data_at_pos (行348-368) - 插入元素
- 分支：`a->used < a->size` (重用槽位，检查prev != NULL)
- 分支：`a->used >= a->size` (需要array_extend)
- 分支：`ndx != 0` (需要memmove)
- 分支：`ndx == 0` (直接插入)

### 3. array_match_key_prefix_klen (行513-522) - 前缀匹配
- 遍历所有元素，检查 `klen <= slen && 0 == memcmp`

### 4. array_match_value_suffix (行610-622) - 后缀匹配（用于mimetype）
- 遍历所有元素，检查 `vlen <= blen && 0 == memcmp(end - vlen, value->ptr, vlen)`

### 5. array_extend (行113-120) - 数组扩展
- 检查 `a->size <= INT32_MAX-n`
- realloc data和sorted数组

### 6. array_get_unused_element (行318-345) - 元素重用
- 分支：`a->used < a->size && a->data[a->used] != NULL && type匹配` (重用)
- 分支：否则返回NULL (需要创建新元素)

### 7. array_insert_unique (行462-472) - 唯一插入
- 分支：找到已存在元素 (insert_dup或free)
- 分支：未找到 (正常插入)

## 触发方式

1. **mimetype匹配** - 请求不同扩展名的文件（.txt, .html, .jpg, .pdf等）
2. **多个HTTP头部** - 发送多个相同或不同的头部
3. **URL路径匹配** - 虽然当前配置没有路径配置，但可以测试
4. **Accept头部** - 多个Accept值可能触发数组处理

## 覆盖策略

生成种子来：
1. 测试不同扩展名（触发array_match_value_suffix）
2. 测试多个头部（触发数组插入和查找）
3. 测试Accept头部多个值（触发数组处理）
4. 测试边界情况（触发数组扩展）
5. 测试重复头部（触发array_insert_unique）

