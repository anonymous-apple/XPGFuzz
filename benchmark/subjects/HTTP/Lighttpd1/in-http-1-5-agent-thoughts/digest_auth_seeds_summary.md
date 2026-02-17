# Digest认证种子生成总结

## 生成的种子文件

已生成10个用于覆盖 `mod_auth_digest_get` 函数分支的种子文件：

1. **http_requests_digest_auth_basic.raw** - 无Authorization头（基线测试）
2. **http_requests_digest_auth_md5.raw** - 标准MD5算法Digest认证
3. **http_requests_digest_auth_md5_sess.raw** - MD5-sess算法（会话算法）
4. **http_requests_digest_auth_short_user.raw** - 短用户名（1字符）
5. **http_requests_digest_auth_long_user.raw** - 长用户名（测试缓冲区边界）
6. **http_requests_digest_auth_invalid.raw** - 无效的Digest认证（缺少必要字段）
7. **http_requests_digest_auth_multiple.raw** - 多个相同请求（测试缓存命中）
8. **http_requests_digest_auth_diff_algo.raw** - SHA-256算法（不同算法）
9. **http_requests_digest_auth_userhash.raw** - 启用userhash的认证
10. **http_requests_digest_auth_username_star.raw** - 使用username*扩展值（UTF-8编码）
11. **http_requests_digest_auth_complex.raw** - 复杂场景（包含opaque等额外字段）

## 覆盖的分支

这些种子设计用于覆盖 `mod_auth_digest_get` 函数中的以下分支：

### 分支1: userhash处理
- 种子9 (userhash) - 覆盖 `ai->userhash && ulen <= sizeof(userbuf)` 分支

### 分支2: 缓存处理
- 种子7 (multiple) - 测试缓存命中（相同用户多次请求）
- 其他种子 - 测试缓存未命中场景

### 分支3: 算法类型
- 种子3 (md5_sess) - MD5-sess算法
- 种子8 (diff_algo) - SHA-256算法
- 其他 - MD5标准算法

### 分支4: 用户名长度
- 种子4 (short_user) - 极短用户名
- 种子5 (long_user) - 长用户名（测试边界条件）

### 分支5: 无效认证
- 种子6 (invalid) - 缺少必要字段，测试错误处理路径

### 分支6: username*扩展
- 种子10 (username_star) - UTF-8编码的用户名

### 分支7: 复杂场景
- 种子11 (complex) - 包含opaque等额外字段的复杂请求

## 注意事项

1. **当前配置未启用认证**：lighttpd.conf中没有auth配置，这些请求可能返回401或正常处理
2. **Digest认证格式**：所有Authorization头都遵循RFC 2617 Digest认证格式
3. **nonce值**：使用了示例nonce值，实际使用时需要从服务器401响应中获取
4. **response值**：使用了示例response值，实际值需要根据算法计算

## 使用说明

这些种子可以在以下场景中使用：
- 测试Digest认证处理逻辑
- 覆盖 `mod_auth_digest_get` 函数的各个分支
- 测试缓存机制
- 测试不同算法和参数组合
- 测试边界条件和错误处理

