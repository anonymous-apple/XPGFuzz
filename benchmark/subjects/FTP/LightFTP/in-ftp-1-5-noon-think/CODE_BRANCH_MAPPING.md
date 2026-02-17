# 代码分支到种子文件的映射

本文档详细记录了每个新创建的种子文件对应的源代码分支。

## 1. worker_thread_start 函数分支

### 分支: busy状态检查 (274行)
```c
if (__sync_val_compare_and_swap(&context->busy, 0, 1) != 0)
{
     sendstring(context, error450);
     return;
}
```
**覆盖种子**:
- `ftp_requests_71_concurrent_operations.raw`: 连续LIST操作
- `ftp_requests_88_pasv_while_busy.raw`: LIST进行时调用PASV
- `ftp_requests_89_retr_while_busy.raw`: RETR进行时再次RETR
- `ftp_requests_90_stor_while_busy.raw`: STOR进行时再次STOR

## 2. list_thread 函数分支

### 分支: create_datasocket失败 (548行)
```c
client_socket = create_datasocket(context);
while (client_socket != INVALID_SOCKET)
```
**覆盖种子**:
- `ftp_requests_92_port_then_pasv.raw`: 错误的连接模式切换
- `ftp_requests_93_epsv_then_pasv.raw`: 错误的连接模式切换

### 分支: TLS初始化失败 (551-552行)
```c
if (context->tls_session != NULL)
    if (!ftp_init_tls_session(&TLS_datasession, client_socket, 0))
        break;
```
**覆盖种子**:
- `ftp_requests_78_list_tls.raw`: TLS模式下的LIST

### 分支: open失败 (555-556行)
```c
fd = open(tctx->th_file_name, O_DIRECTORY | O_RDONLY | g_cfg.file_open_flags);
if (fd == -1)
    break;
```
**覆盖种子**:
- `ftp_requests_62_list_nonexistent.raw`: 不存在的路径
- `ftp_requests_67_mlsd_nonexistent.raw`: 不存在的路径

### 分支: fdopendir失败 (559-562行)
```c
pdir = fdopendir(fd);
if (pdir == NULL) {
    close(fd);
    break;
}
```
**覆盖种子**: 难以直接触发，需要系统状态

### 分支: worker_thread_abort (569-570行)
```c
if ( (ret == 0) || (context->worker_thread_abort != 0 ))
    break;
```
**覆盖种子**:
- `ftp_requests_75_mlsd_with_abor.raw`: MLSD后ABOR

### 分支: 错误处理 (585-588行)
```c
if ((context->worker_thread_abort == 0) && (ret != 0))
    sendstring(context, success226);
else
    sendstring(context, error426);
```
**覆盖种子**:
- `ftp_requests_75_mlsd_with_abor.raw`: ABOR触发error426
- `ftp_requests_86_list_file.raw`: LIST文件触发错误

### 分支: 路径不是目录 (620-621行, ftpLIST)
```c
if ( !S_ISDIR(filestats.st_mode) )
    break;
```
**覆盖种子**:
- `ftp_requests_86_list_file.raw`: LIST文件路径

## 3. retr_thread 函数分支

### 分支: create_datasocket失败 (708-709行)
**覆盖种子**:
- `ftp_requests_92_port_then_pasv.raw`: 错误的连接设置

### 分支: TLS初始化失败 (713-714行)
**覆盖种子**:
- `ftp_requests_76_retr_tls.raw`: TLS模式下的RETR

### 分支: open失败 (725-726行)
**覆盖种子**:
- `ftp_requests_63_retr_nonexistent.raw`: 不存在的文件

### 分支: lseek失败 (728-730行)
```c
offset = lseek(file_fd, context->rest_point, SEEK_SET);
if (offset != context->rest_point)
    break;
```
**覆盖种子**:
- `ftp_requests_79_rest_large_offset.raw`: 超大偏移值

### 分支: worker_thread_abort (733行)
```c
while ( context->worker_thread_abort == 0 ) {
```
**覆盖种子**:
- `ftp_requests_72_retr_with_abor.raw`: RETR后ABOR

### 分支: read失败 (738-742行)
```c
if (sz < 0)
{
    sent_ok = 0;
    break;
}
```
**覆盖种子**: 难以直接触发，需要文件系统错误

### 分支: send失败 (748-752行)
```c
if (send_auto(client_socket, TLS_datasession, buffer, sz) == sz)
{
    sz_total += sz;
}
else
{
    sent_ok = 0;
    break;
}
```
**覆盖种子**: 难以直接触发，需要网络错误

### 分支: 错误处理 (787-790行)
```c
if ((context->worker_thread_abort == 0) && (sent_ok != 0))
    sendstring(context, success226);
else
    sendstring(context, error426);
```
**覆盖种子**:
- `ftp_requests_72_retr_with_abor.raw`: ABOR触发error426
- `ftp_requests_83_retr_directory.raw`: RETR目录触发错误

### 分支: 路径不是普通文件 (818-819行, ftpRETR)
```c
if ( !S_ISREG(filestats.st_mode) )
    break;
```
**覆盖种子**:
- `ftp_requests_83_retr_directory.raw`: RETR目录

## 4. stor_thread 函数分支

### 分支: create_datasocket失败 (1141-1142行)
**覆盖种子**:
- `ftp_requests_92_port_then_pasv.raw`: 错误的连接设置

### 分支: TLS初始化失败 (1146-1147行)
**覆盖种子**:
- `ftp_requests_77_stor_tls.raw`: TLS模式下的STOR

### 分支: open失败 (1162-1163行)
**覆盖种子**:
- `ftp_requests_84_stor_directory.raw`: STOR目录路径

### 分支: write失败 (1173-1174行)
```c
wsz = write(file_fd, buffer, (size_t)sz);
if (wsz != sz)
    break;
```
**覆盖种子**: 难以直接触发，需要磁盘满或权限错误

### 分支: worker_thread_abort (1167行)
**覆盖种子**:
- `ftp_requests_73_stor_with_abor.raw`: STOR后ABOR
- `ftp_requests_74_appe_with_abor.raw`: APPE后ABOR

### 分支: 路径不是普通文件 (1248-1249行, ftpSTOR)
**覆盖种子**:
- `ftp_requests_84_stor_directory.raw`: STOR目录

## 5. parseCHMOD 函数分支

### 分支: 非八进制数字 (1284-1289行)
```c
while (isoctaldigit(*params))
{
    flags <<= 3;
    flags += ((unsigned int)*params) - (unsigned int)'0';
    ++params;
}
```
**覆盖种子**:
- `ftp_requests_80_site_chmod_invalid.raw`: 包含8, 9, 999等无效值

### 分支: 无空格分隔 (1291-1292行)
```c
if (*params != ' ')
    return 0;
```
**覆盖种子**:
- `ftp_requests_81_site_chmod_no_space.raw`: 权限值和文件名之间无空格

### 分支: chmod失败 (1298行)
```c
return (chmod(context->file_name, flags) == 0);
```
**覆盖种子**:
- `ftp_requests_82_site_chmod_nonexistent.raw`: 不存在的文件

### 分支: 各种权限值 (1284-1298行)
**覆盖种子**:
- `ftp_requests_94_site_chmod_various.raw`: 000, 111, 222, ..., 777

## 6. ftpAPPE 函数分支

### 分支: 文件不存在或不是普通文件 (1348-1352行)
```c
while (stat(context->file_name, &filestats) == 0)
{
    if ( !S_ISREG(filestats.st_mode) )
        break;
```
**覆盖种子**:
- `ftp_requests_85_appe_directory.raw`: APPE目录
- `ftp_requests_99_appe_nonexistent.raw`: APPE不存在的文件

## 7. ftpMLSD 函数分支

### 分支: 路径不是目录 (1542行)
```c
if ( !S_ISDIR(filestats.st_mode) )
    break;
```
**覆盖种子**:
- `ftp_requests_87_mlsd_file.raw`: MLSD文件路径

## 8. 特殊场景分支

### 空目录处理
**覆盖种子**:
- `ftp_requests_95_list_empty_dir.raw`: LIST空目录
- `ftp_requests_96_mlsd_empty_dir.raw`: MLSD空目录

### 符号链接处理
**覆盖种子**:
- `ftp_requests_97_retr_symlink.raw`: RETR符号链接

### 权限检查
**覆盖种子**:
- `ftp_requests_98_stor_existing_readonly.raw`: readonly用户STOR已存在文件

### REST命令
**覆盖种子**:
- `ftp_requests_79_rest_large_offset.raw`: 超大偏移值
- `ftp_requests_91_retr_after_rest.raw`: 多次REST

## 总结

- **可直接覆盖的分支**: 约30个关键分支
- **需要系统状态的分支**: 约10个（socket, bind, listen, pthread_create等）
- **需要文件系统错误的分支**: 约5个（read, write失败等）
- **需要网络错误的分支**: 约2个（send失败等）

通过新创建的30个种子文件，预期可以覆盖大部分可直接触发的分支，显著提升代码覆盖率。

