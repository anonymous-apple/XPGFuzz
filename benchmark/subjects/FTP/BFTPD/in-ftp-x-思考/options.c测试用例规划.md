# options.c 测试用例规划

## 目标

尽可能通过 FTP 命令覆盖 `options.c` 中可以触发的代码路径。

## 测试用例设计原则

1. **目录操作优先**: 通过 `CWD` 命令触发目录相关的选项查询
2. **选项查询**: 通过各种命令触发配置选项的查询
3. **路径遍历**: 测试不同深度的目录路径
4. **组合测试**: 组合多个命令以触发不同的选项查询路径

## 测试用例列表

### 用例1: 基础目录操作（seed_options_basic.raw）
**目的**: 触发基本的选项查询和目录操作
```
USER ubuntu
PASS ubuntu
PWD
CWD /
PWD
CWD /home/ubuntu/ftpshare
PWD
LIST
QUIT
```

### 用例2: 深层目录遍历（seed_options_deep.raw）
**目的**: 测试深层目录路径，可能触发目录选项查询
```
USER ubuntu
PASS ubuntu
CWD /home/ubuntu/ftpshare
PWD
CWD data
PWD
CWD subdir1
PWD
CWD subdir2
PWD
LIST
CWD ../..
PWD
QUIT
```

### 用例3: 多路径切换（seed_options_multipath.raw）
**目的**: 在不同路径间切换，触发多次选项查询
```
USER ubuntu
PASS ubuntu
CWD /home/ubuntu/ftpshare/data
PWD
LIST
CWD /home/ubuntu/ftpshare
PWD
LIST
CWD /
PWD
CWD /home/ubuntu/ftpshare/data
PWD
QUIT
```

### 用例4: 选项相关命令序列（seed_options_commands.raw）
**目的**: 触发各种配置选项的使用
```
USER ubuntu
PASS ubuntu
SYST
FEAT
NOOP
HELP
STAT
PWD
TYPE A
TYPE I
QUIT
```

### 用例5: 复杂目录操作（seed_options_complex.raw）
**目的**: 复杂的目录操作序列
```
USER ubuntu
PASS ubuntu
MKD test_dir1
CWD test_dir1
PWD
MKD test_dir2
CWD test_dir2
PWD
LIST
CWD ..
RMD test_dir2
CWD ..
RMD test_dir1
PWD
QUIT
```

### 用例6: 相对路径操作（seed_options_relative.raw）
**目的**: 测试相对路径处理
```
USER ubuntu
PASS ubuntu
CWD /home/ubuntu/ftpshare/data
PWD
CWD .
PWD
CWD ..
PWD
CWD ../data
PWD
QUIT
```

### 用例7: 绝对路径操作（seed_options_absolute.raw）
**目的**: 测试绝对路径处理
```
USER ubuntu
PASS ubuntu
CWD /home/ubuntu/ftpshare
PWD
CWD /home/ubuntu/ftpshare/data
PWD
CWD /home/ubuntu/ftpshare
PWD
CWD /
PWD
CWD /home/ubuntu/ftpshare/data
PWD
QUIT
```

### 用例8: 选项查询密集型（seed_options_query.raw）
**目的**: 频繁查询选项
```
USER ubuntu
PASS ubuntu
SYST
FEAT
HELP
STAT
PWD
SYST
PWD
STAT
QUIT
```

### 用例9: 长路径测试（seed_options_longpath.raw）
**目的**: 测试长路径处理
```
USER ubuntu
PASS ubuntu
CWD /home/ubuntu/ftpshare/data/subdir1/subdir2
PWD
LIST
CWD /home/ubuntu/ftpshare
PWD
QUIT
```

### 用例10: 路径边界测试（seed_options_boundary.raw）
**目的**: 测试路径边界情况
```
USER ubuntu
PASS ubuntu
CWD /
PWD
CWD /home
PWD
CWD /home/ubuntu
PWD
CWD /home/ubuntu/ftpshare
PWD
LIST
QUIT
```

## 预期效果

### 可以覆盖的代码路径

1. ✅ `config_getoption()` 的更多调用路径
2. ✅ `getoption_global()` 的调用
3. ✅ `getoption_user()` 的调用（如果配置了用户）
4. ⚠️ `getoption_directories()` （需要配置文件中有 directory 块）
5. ⚠️ `getoption_group()` （需要配置文件中有 group 块）

### 无法通过 FTP 命令覆盖的代码路径

1. ❌ `config_read_line()` 中的单个引号处理
2. ❌ `create_options()` 中的 directory 块解析
3. ❌ `expand_groups()` 函数
4. ❌ `config_init()` 中的 group 块解析
5. ❌ `Reread_Config_File()` 函数
6. ❌ 各种错误处理分支

## 执行建议

1. **使用现有配置文件**: 先使用 `basic.conf` 测试，确保基本功能覆盖
2. **创建增强配置文件**: 如果可能，创建包含 directory 和 group 块的配置文件
3. **组合测试**: 运行多个测试用例的组合，以增加覆盖

## 注意事项

1. **配置文件依赖**: 许多未覆盖的代码路径依赖于配置文件内容
2. **信号触发**: `Reread_Config_File()` 需要 SIGHUP 信号，无法通过 FTP 命令触发
3. **错误处理**: 内存分配失败等错误处理分支难以在正常测试中触发
