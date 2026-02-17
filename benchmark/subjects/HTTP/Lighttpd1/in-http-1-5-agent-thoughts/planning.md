# 种子生成规划

## 种子文件列表

### 1. POST请求（6个文件）
- `http_requests_post_text.raw` - POST text/plain
- `http_requests_post_form.raw` - POST application/x-www-form-urlencoded
- `http_requests_post_json.raw` - POST application/json
- `http_requests_post_empty.raw` - POST无请求体
- `http_requests_post_multipart.raw` - POST multipart/form-data
- `http_requests_post_sequence.raw` - POST后跟GET的序列

### 2. PUT请求（4个文件）
- `http_requests_put_text.raw` - PUT text/plain文件
- `http_requests_put_html.raw` - PUT text/html文件
- `http_requests_put_small.raw` - PUT小文件
- `http_requests_put_sequence.raw` - PUT后验证的序列

### 3. HEAD请求（3个文件）
- `http_requests_head_simple.raw` - HEAD简单请求
- `http_requests_head_with_headers.raw` - HEAD带多个头
- `http_requests_head_sequence.raw` - HEAD后跟GET

### 4. PATCH请求（3个文件）
- `http_requests_patch_text.raw` - PATCH text/plain
- `http_requests_patch_json.raw` - PATCH application/json
- `http_requests_patch_sequence.raw` - PATCH后跟GET

### 5. TRACE请求（2个文件）
- `http_requests_trace_simple.raw` - TRACE简单请求
- `http_requests_trace_with_headers.raw` - TRACE带多个头

### 6. 混合请求序列（3个文件）
- `http_requests_mixed_sequence.raw` - 多种方法的序列
- `http_requests_keepalive.raw` - 测试keep-alive连接
- `http_requests_comprehensive.raw` - 覆盖各种头和方法

总计：21个种子文件

