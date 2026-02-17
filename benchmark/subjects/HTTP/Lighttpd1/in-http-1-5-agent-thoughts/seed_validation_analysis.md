# 种子有效性分析

## 问题发现

### 1. 配置限制
当前 `lighttpd.conf` 配置：
```
server.document-root = "/tmp"
server.bind = "127.0.0.1"
server.port = 8080
mimetype.assign = (".txt" => "text/plain", ".html" => "text/html" )
```

**关键问题**: 配置中没有启用 `mod_auth` 模块，没有配置：
- `auth.backend`
- `auth.require`

### 2. 代码执行路径分析

`mod_auth_digest_get` 函数只在以下条件下被调用：
1. 服务器配置了 `auth.require` 指向某个路径
2. 请求的路径匹配配置的 `auth.require` 路径
3. `auth.backend` 配置了支持 digest 的后端
4. 请求包含 `Authorization: Digest ...` 头

**结论**: 在当前配置下，即使发送 Digest 认证请求，也不会触发 `mod_auth_digest_get` 函数。

### 3. 请求格式有效性

虽然请求格式本身是有效的 HTTP 格式，但是：
- 如果没有配置认证，服务器会忽略 Authorization 头
- 不会触发任何认证相关的代码路径
- 不会覆盖 `mod_auth_digest_get` 函数

## 解决方案

有两种选择：

### 方案1: 生成能触发代码的种子（需要配置支持）
- 需要配置认证模块
- 需要配置用户凭证
- 需要生成有效的 nonce

### 方案2: 生成基本的、可被服务器处理的请求
- 生成符合 HTTP 标准的请求
- 即使不触发认证逻辑，至少能被正确解析
- 避免格式错误导致服务器拒绝

## 建议

由于当前配置不支持认证，建议：
1. 生成一些基本的、格式正确的 HTTP 请求（用于测试其他功能）
2. 或者说明需要配置认证模块才能测试 Digest 认证功能
3. 如果要测试 Digest 认证，需要先配置服务器

