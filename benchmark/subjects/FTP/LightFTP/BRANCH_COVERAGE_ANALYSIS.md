# LightFTP 代码分支覆盖分析

## 基于源代码的分支覆盖策略

本目录包含70个种子文件，专门设计用于覆盖LightFTP源代码中的关键分支。

/data16/xhoulong/xhoulong/protocol-fuzzing/benchmark/subjects/FTP/LightFTP/in-ftp-1-4-night

## 关键分支覆盖

### 1. 访问权限级别分支 (ftpPASS, 1006-1019行)
- ✅ **readonly**: `ftp_requests_39_readonly_access.raw`, `ftp_requests_53_readonly_denied.raw`, `ftp_requests_68_comprehensive_readonly.raw`
- ✅ **upload**: `ftp_requests_40_upload_access.raw`, `ftp_requests_41_upload_overwrite_fail.raw`, `ftp_requests_54_upload_denied.raw`, `ftp_requests_69_comprehensive_upload.raw`
- ✅ **admin**: `ftp_requests_42_admin_full_access.raw`, `ftp_requests_70_comprehensive_admin.raw`

### 2. TYPE命令分支 (ftpTYPE, 352-364行)
- ✅ **'A'/'a'**: `ftp_requests_04_type_ascii.raw`, `ftp_requests_36_type_lowercase.raw`
- ✅ **'I'/'i'**: `ftp_requests_05_type_binary.raw`, `ftp_requests_36_type_lowercase.raw`
- ✅ **default (无效类型)**: `ftp_requests_55_type_invalid.raw`
- ✅ **params == NULL**: `ftp_requests_55_type_invalid.raw`

### 3. LIST命令分支 (ftpLIST, 610-614行)
- ✅ **params == NULL**: `ftp_requests_11_list_basic.raw`
- ✅ **params == "-a"**: `ftp_requests_37_list_flags.raw`
- ✅ **params == "-l"**: `ftp_requests_37_list_flags.raw`
- ✅ **params == 路径**: `ftp_requests_12_list_path.raw`, `ftp_requests_37_list_flags.raw`
- ✅ **路径不存在**: `ftp_requests_62_list_nonexistent.raw`
- ✅ **路径不是目录**: 通过LIST非目录路径触发

### 4. PORT命令分支 (ftpPORT, 397-398行)
- ✅ **IP匹配客户端**: `ftp_requests_06_port_mode.raw`, `ftp_requests_38_port_ip_check.raw`
- ✅ **IP不匹配客户端**: 通过错误IP触发error501分支

### 5. CDUP命令分支 (ftpCDUP, 644-647行)
- ✅ **current_dir == "/"**: `ftp_requests_43_cdup_root.raw`
- ✅ **current_dir != "/"**: `ftp_requests_44_cdup_nested.raw`, `ftp_requests_10_directory_ops.raw`

### 6. STOR命令权限分支 (ftpSTOR, 1243-1250行)
- ✅ **文件存在 && access != FULL**: `ftp_requests_41_upload_overwrite_fail.raw`
- ✅ **文件存在 && access == FULL**: `ftp_requests_42_admin_full_access.raw`
- ✅ **文件不存在 && access >= CREATENEW**: `ftp_requests_40_upload_access.raw`

### 7. APPE命令权限分支 (ftpAPPE, 1338行)
- ✅ **access < FULL**: `ftp_requests_54_upload_denied.raw`
- ✅ **access == FULL**: `ftp_requests_42_admin_full_access.raw`, `ftp_requests_70_comprehensive_admin.raw`

### 8. DELE命令权限分支 (ftpDELE, 847行)
- ✅ **access < FULL**: `ftp_requests_53_readonly_denied.raw`, `ftp_requests_54_upload_denied.raw`
- ✅ **access == FULL**: `ftp_requests_42_admin_full_access.raw`

### 9. MKD命令权限分支 (ftpMKD, 1075行)
- ✅ **access < CREATENEW**: `ftp_requests_53_readonly_denied.raw`
- ✅ **access >= CREATENEW**: `ftp_requests_40_upload_access.raw`, `ftp_requests_42_admin_full_access.raw`

### 10. RMD命令权限分支 (ftpRMD, 1096行)
- ✅ **access < FULL**: `ftp_requests_53_readonly_denied.raw`, `ftp_requests_54_upload_denied.raw`
- ✅ **access == FULL**: `ftp_requests_42_admin_full_access.raw`

### 11. REST命令分支 (ftpREST, 1037-1038行)
- ✅ **params == NULL**: 通过无参数触发
- ✅ **各种偏移值**: `ftp_requests_45_rest_various.raw`

### 12. SITE命令分支 (ftpSITE, 1303-1314行)
- ✅ **params == "help"**: `ftp_requests_27_site_help.raw`
- ✅ **params == "chmod ..."**: `ftp_requests_46_site_chmod.raw`
- ✅ **params == NULL**: `ftp_requests_47_site_invalid.raw`
- ✅ **其他参数**: `ftp_requests_47_site_invalid.raw`

### 13. OPTS命令分支 (ftpOPTS, 1411-1412行)
- ✅ **params == "utf8 on"**: `ftp_requests_25_opts_utf8.raw`
- ✅ **其他参数**: `ftp_requests_48_opts_invalid.raw`
- ✅ **params == NULL**: `ftp_requests_48_opts_invalid.raw`

### 14. AUTH命令分支 (ftpAUTH, 1421-1431行)
- ✅ **params == "TLS"**: `ftp_requests_23_auth_tls.raw`
- ✅ **其他参数**: `ftp_requests_59_auth_invalid.raw`
- ✅ **params == NULL**: `ftp_requests_59_auth_invalid.raw`

### 15. PBSZ命令分支 (ftpPBSZ, 1436-1440行)
- ✅ **params == NULL**: 通过无参数触发
- ✅ **tls_session == NULL**: `ftp_requests_60_pbsz_without_auth.raw`
- ✅ **tls_session != NULL**: `ftp_requests_24_pbsz_prot.raw`, `ftp_requests_57_pbsz_variants.raw`

### 16. PROT命令分支 (ftpPROT, 1451-1471行)
- ✅ **params == 'C'**: `ftp_requests_49_prot_clear.raw`
- ✅ **params == 'P'**: `ftp_requests_24_pbsz_prot.raw`, `ftp_requests_50_prot_private.raw`
- ✅ **default**: `ftp_requests_58_prot_invalid.raw`
- ✅ **tls_session == NULL**: `ftp_requests_61_prot_without_auth.raw`
- ✅ **params == NULL**: `ftp_requests_58_prot_invalid.raw`

### 17. RNFR/RNTO分支 (ftpRNFR, ftpRNTO)
- ✅ **RNTO without RNFR**: `ftp_requests_51_rnto_without_rnfr.raw`
- ✅ **正确的RNFR/RNTO序列**: `ftp_requests_19_rename.raw`, `ftp_requests_42_admin_full_access.raw`
- ✅ **RNFR文件不存在**: `ftp_requests_66_rnfr_nonexistent.raw`

### 18. MLSD命令分支 (ftpMLSD, 1535行)
- ✅ **params == NULL**: `ftp_requests_20_mlsd.raw`
- ✅ **params == 路径**: `ftp_requests_21_mlsd_path.raw`, `ftp_requests_52_mlsd_variants.raw`
- ✅ **路径不存在**: `ftp_requests_67_mlsd_nonexistent.raw`

### 19. 未登录状态检查 (多个函数)
- ✅ **所有需要登录的命令在未登录时**: `ftp_requests_56_commands_before_login.raw`

### 20. 文件/目录不存在分支
- ✅ **LIST不存在路径**: `ftp_requests_62_list_nonexistent.raw`
- ✅ **RETR不存在文件**: `ftp_requests_63_retr_nonexistent.raw`
- ✅ **SIZE不存在文件**: `ftp_requests_64_size_nonexistent.raw`
- ✅ **CWD不存在目录**: `ftp_requests_65_cwd_nonexistent.raw`
- ✅ **MLSD不存在路径**: `ftp_requests_67_mlsd_nonexistent.raw`

## 文件组织

### 按功能分类：
1. **认证和权限** (39-42, 53-54, 68-70): 覆盖三种访问级别
2. **命令参数变体** (36-37, 55, 57-59): 覆盖大小写、无效参数等
3. **错误处理** (47-48, 51, 55-56, 58-67): 覆盖各种错误情况
4. **特殊场景** (43-44, 45, 60-61): 覆盖边界条件
5. **综合测试** (68-70): 覆盖完整工作流程

## 预期覆盖的代码路径

这些种子文件设计用于覆盖：
- ✅ 所有访问权限级别的代码路径
- ✅ 所有命令的参数验证分支
- ✅ 所有错误处理路径
- ✅ 文件存在/不存在的分支
- ✅ 目录操作的各种情况
- ✅ TLS/安全相关的所有分支
- ✅ 数据传输模式的所有变体

## 使用建议

1. 使用这些种子文件进行模糊测试
2. 监控代码覆盖率，确保所有关键分支都被执行
3. 根据覆盖率报告补充缺失的分支测试用例
4. 特别关注错误处理路径，这些往往是漏洞的藏身之处

