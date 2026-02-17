# HTTP Lighttpd1 种子生成分析

## 1. 现有种子分析

### 1.1 当前已有的HTTP方法
- GET: `http_requests_get_hello.raw`
- DELETE: `http_requests_delete_hello.raw`
- OPTIONS: `http_requests_options_hello.raw`

### 1.2 现有种子的特点
- 所有请求都使用HTTP/1.1
- 所有请求都有Host头: `127.0.0.1:8080`
- 基本头部：User-Agent, Accept
- 请求路径：`/hello.txt`
- 无请求体（body）

## 2. 协议实现分析

### 2.1 配置信息
- 服务器绑定：127.0.0.1:8080
- 文档根目录：/tmp
- MIME类型：.txt -> text/plain, .html -> text/html

### 2.2 lighttpd1支持的HTTP方法（基于文档）
根据`Static-Content-Serving.md`和`HTTP-Request-Processing.md`：
- **mod_staticfile**支持：GET, HEAD, POST
- 标准HTTP方法：GET, POST, PUT, DELETE, HEAD, OPTIONS, PATCH, TRACE, CONNECT

### 2.3 缺失的HTTP方法
当前种子缺少以下方法：
1. **POST** - 带请求体的请求，用于提交数据
2. **PUT** - 用于上传/更新资源
3. **HEAD** - 仅获取响应头
4. **PATCH** - 部分更新资源
5. **TRACE** - 用于调试（回显请求）
6. **CONNECT** - 用于代理隧道

### 2.4 需要覆盖的协议逻辑分支

#### 2.4.1 请求头相关
- Content-Type: text/plain, application/json, application/x-www-form-urlencoded, multipart/form-data
- Content-Length: 不同长度的请求体
- Connection: keep-alive, close
- Accept: 不同MIME类型
- User-Agent: 不同客户端标识
- Referer: 来源页面
- If-Modified-Since: 条件请求
- If-None-Match: ETag条件请求
- Range: 范围请求

#### 2.4.2 请求体相关
- 无请求体（GET, HEAD, DELETE, OPTIONS）
- 有请求体（POST, PUT, PATCH）
- 不同Content-Length
- 不同Content-Type

#### 2.4.3 路径相关
- 简单路径：/hello.txt
- 长路径：测试路径处理
- 查询字符串：?key=value
- URL编码：%20等

#### 2.4.4 多请求序列
- 单个请求
- 多个请求（测试keep-alive连接）

## 3. 生成策略

### 3.1 新增方法类型
优先生成以下缺失的方法：
1. **POST** - 最常用，需要覆盖
2. **PUT** - 上传功能，需要覆盖
3. **HEAD** - 仅头请求，不同逻辑分支
4. **PATCH** - 部分更新，需要覆盖
5. **TRACE** - 调试功能，测试特殊逻辑

注意：CONNECT方法在简单配置下可能不支持，先不生成。

### 3.2 覆盖策略
1. 每个方法至少生成2-3个变体
2. 包含不同的Content-Type
3. 包含不同的请求头组合
4. 包含带请求体和不带请求体的变体
5. 包含多请求序列测试keep-alive

### 3.3 确保请求能通过服务器
- 使用有效的Host头：127.0.0.1:8080
- 使用合理的路径（文档根目录为/tmp）
- 对于PUT/POST，使用合理的Content-Length
- 对于POST/PUT，提供实际的请求体

## 4. 种子文件命名规则
- 格式：`http_requests_{method}_{description}.raw`
- 示例：`http_requests_post_form.raw`, `http_requests_put_file.raw`

