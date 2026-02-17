#!/bin/bash

# 脚本：执行所有setup文件
# 用途：批量执行项目中的所有setup脚本，用于构建Docker镜像

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "开始执行所有setup脚本"
echo "=========================================="
echo ""

# 查找所有setup*.sh文件并排序，排除setup_all.sh本身
SETUP_FILES=$(find . -maxdepth 1 -name "setup_*.sh" -type f ! -name "setup_all.sh" | sort)

if [ -z "$SETUP_FILES" ]; then
    echo "错误: 未找到任何setup文件"
    exit 1
fi

# 统计信息
TOTAL=0
SUCCESS=0
FAILED=0
FAILED_FILES=()

# 执行每个setup文件
for setup_file in $SETUP_FILES; do
    TOTAL=$((TOTAL + 1))
    filename=$(basename "$setup_file")
    
    echo "----------------------------------------"
    echo "[$TOTAL] 正在执行: $filename"
    echo "----------------------------------------"
    echo ""
    
    # 检查文件是否可执行
    if [ ! -x "$setup_file" ]; then
        echo "  设置执行权限: $filename"
        chmod +x "$setup_file"
    fi
    
    # 执行setup文件，实时显示所有输出
    # 直接执行脚本，输出会实时显示（不缓冲）
    bash "$setup_file"
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        SUCCESS=$((SUCCESS + 1))
        echo ""
        echo "  ✓ $filename 执行成功"
    else
        FAILED=$((FAILED + 1))
        FAILED_FILES+=("$filename")
        echo ""
        echo "  ✗ $filename 执行失败 (退出码: $EXIT_CODE)"
    fi
    
    echo ""
    echo "----------------------------------------"
    echo ""
done

# 输出总结
echo "=========================================="
echo "执行完成"
echo "=========================================="
echo "总计: $TOTAL 个setup文件"
echo "成功: $SUCCESS 个"
echo "失败: $FAILED 个"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "失败的setup文件:"
    for file in "${FAILED_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
else
    echo ""
    echo "所有setup文件执行成功！"
    exit 0
fi
