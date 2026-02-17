# MD5 测试覆盖率说明

这些种子文件用于提高 `bftpd/md5.c` 的分支覆盖率。

## 关键分支覆盖点

### 1. md5_process() 函数分支

- **md_buf_len > 0**: 当内部缓冲区有数据时
  - 覆盖文件: `seed_md5_buffer_management.raw`, `seed_md5_all_sizes.raw`
  - 触发条件: 多次调用 md5_process 时，缓冲区有残留数据

- **in_block + len > sizeof(md_buffer)**: 缓冲区溢出检查
  - 覆盖文件: 大文件测试（>1024字节）
  - 触发条件: 内部缓冲区 + 新数据超过缓冲区大小

- **in_block > MD5_BLOCK_SIZE**: 处理完整块
  - 覆盖文件: `seed_md5_block_boundaries.raw`
  - 触发条件: 累积数据超过64字节块大小

- **len > MD5_BLOCK_SIZE**: 处理完整块
  - 覆盖文件: 所有大于64字节的文件
  - 触发条件: 输入数据超过一个块大小

- **len > 0**: 复制剩余字节
  - 覆盖文件: 所有非块大小倍数的文件
  - 触发条件: 有剩余字节需要复制到内部缓冲区

### 2. md5_finish() 函数分支

- **md_total[0] > MAX_MD5_UINT32 - bytes**: 溢出检查
  - 覆盖文件: 超大文件（需要测试 >4GB 的文件，但实际测试中可能难以触发）
  - 触发条件: 文件总大小接近32位整数上限

- **pad <= 0**: 填充计算
  - 覆盖文件: `seed_md5_block_boundaries.raw` (block64.txt, block128.txt)
  - 触发条件: 缓冲区剩余空间不足以放置填充和长度信息

- **pad > 0**: 需要填充
  - 覆盖文件: 所有文件（除了特殊情况）
  - 触发条件: 需要添加填充字节

- **pad > 1**: 填充字节数检查
  - 覆盖文件: 所有需要填充的文件
  - 触发条件: 需要填充多个字节

### 3. md5_sig_to_string() 函数分支

- **str_p + 1 >= max_p**: 边界检查
  - 覆盖文件: 正常情况下不会触发（output_string 有64字节）
  - 触发条件: 输出缓冲区太小

- **str_p < max_p**: 添加空字符
  - 覆盖文件: 所有成功的 MD5 计算
  - 触发条件: 有空间添加字符串结束符

## 种子文件说明

1. **seed_md5_empty.raw**: 测试空文件（0字节）
   - 覆盖: md5_finish 中的填充逻辑

2. **seed_md5_small.raw**: 测试小文件（1-3字节）
   - 覆盖: md5_process 中的 len > 0 分支

3. **seed_md5_block_boundaries.raw**: 测试块边界（63, 64, 65, 127, 128字节）
   - 覆盖: md5_process 和 md5_finish 中的块处理逻辑

4. **seed_md5_large.raw**: 测试大文件（1024, 2048字节）
   - 覆盖: md5_process 中的多次块处理

5. **seed_md5_errors.raw**: 测试错误处理
   - 覆盖: command_md5 中的错误检查分支

6. **seed_md5_comprehensive.raw**: 综合测试所有大小
   - 覆盖: 多个分支的组合

7. **seed_md5_variations.raw**: 测试命令格式变化
   - 覆盖: 命令解析和错误处理

8. **seed_md5_buffer_management.raw**: 测试缓冲区管理
   - 覆盖: md5_process 中的缓冲区管理逻辑

9. **seed_md5_all_sizes.raw**: 测试所有文件大小
   - 覆盖: 最全面的分支覆盖

## 测试文件位置

测试文件位于: `benchmark/subjects/FTP/BFTPD/test_files/`

需要在 FTP 服务器的 ROOTDIR（通常是 `/home/ubuntu/ftpshare`）中创建相同的文件，或者修改种子文件中的路径。

## 使用建议

1. 确保测试文件存在于 FTP 服务器的可访问目录中
2. 运行 xpgfuzz 时，这些种子文件应该能够显著提高 md5.c 的分支覆盖率
3. 重点关注块边界（64字节的倍数）和缓冲区管理相关的分支
