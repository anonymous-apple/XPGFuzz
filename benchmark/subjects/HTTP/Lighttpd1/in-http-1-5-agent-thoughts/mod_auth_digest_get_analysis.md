# mod_auth_digest_get 函数分支分析

## 函数位置
`mod_auth.c` 第1125-1195行

## 函数签名
```c
static handler_t
mod_auth_digest_get (request_st * const r, void *p_d, 
                     const struct http_auth_require_t * const require, 
                     const struct http_auth_backend_t * const backend, 
                     http_auth_info_t * const ai)
```

## 分支条件分析

### 分支1: userhash处理 (行1138-1144)
```c
if (ai->userhash && ulen <= sizeof(userbuf))
```
- 条件1: `ai->userhash` 为true（启用userhash）
- 条件2: `ulen <= sizeof(userbuf)` （用户名长度在范围内）

### 分支2: 缓存树存在 (行1146)
```c
if (sptree)
```
- 条件: 认证缓存配置存在

### 分支3: 缓存命中检查 (行1149-1154)
```c
if (ae && ae->require == require
    && ae->dalgo == ai->dalgo
    && ae->dlen == ai->dlen
    && ae->klen == ulen
    && 0 == memcmp(ae->k, user, ulen)
    && (ae->k == ae->username || ai->userhash))
```
- 条件1: `ae` 存在（缓存条目存在）
- 条件2-6: 多个匹配条件（require、算法、长度、用户名匹配）
- 条件7: key匹配（用户名匹配或使用userhash）

### 分支4: userhash key处理 (行1156)
```c
if (ae->k != ae->username)
```
- 条件: userhash作为key的情况（而非用户名）

### 分支5: 用户名长度检查 (行1157)
```c
if (__builtin_expect( (ae->ulen <= sizeof(ai->userbuf)), 1))
```
- 条件: 用户名长度在缓冲区范围内

### 分支6: 缓存未命中 (行1167)
```c
if (NULL == ae)
```
- 条件: 缓存中没有找到匹配项

### 分支7: userhash预处理 (行1168)
```c
if (ai->userhash && ulen <= sizeof(ai->userbuf))
```
- 条件: userhash启用且长度有效

### 分支8: 返回码处理 (行1174-1185)
```c
switch (rc) {
    case HANDLER_GO_ON: break;
    case HANDLER_WAIT_FOR_EVENT: return HANDLER_WAIT_FOR_EVENT;
    case HANDLER_FINISHED: return HANDLER_FINISHED;
    case HANDLER_ERROR:
    default: return mod_auth_send_401_unauthorized_digest(...);
}
```
- 4个分支：GO_ON, WAIT_FOR_EVENT, FINISHED, ERROR/default

### 分支9: 缓存新结果 (行1187)
```c
if (sptree && NULL == ae)
```
- 条件1: 缓存树存在
- 条件2: 之前缓存未命中

## 覆盖策略

要覆盖这些分支，需要生成包含Digest认证头的HTTP请求。注意：

1. **当前配置未启用认证**：lighttpd.conf中没有auth配置
2. **但仍然可以发送Authorization头**：服务器会处理这些头，即使配置未启用也可能进入部分代码路径
3. **Digest认证格式**：`Authorization: Digest username="...", realm="...", nonce="...", uri="...", response="...", ...`

## 需要覆盖的场景

1. 无Authorization头（触发401，进入digest处理）
2. 有Digest Authorization头，userhash=false
3. 有Digest Authorization头，userhash=true
4. 缓存命中的情况（需要同一用户多次请求）
5. 缓存未命中的情况
6. 不同的算法（MD5, SHA-256等）
7. 不同长度的用户名
8. 无效的认证信息
9. 使用username*扩展值的情况

