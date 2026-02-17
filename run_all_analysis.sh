#!/bin/bash

# 一键运行所有分析脚本并保存结果
# 使用方法: ./run_all_analysis.sh [benchmark_dir]

# 不设置 set -e，允许单个脚本失败后继续运行

# 获取脚本所在目录（主目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 设置benchmark目录
if [ -n "$1" ]; then
    BENCHMARK_DIR="$1"
else
    BENCHMARK_DIR="$SCRIPT_DIR/benchmark"
fi

# 检查benchmark目录是否存在
if [ ! -d "$BENCHMARK_DIR" ]; then
    echo "错误: benchmark目录不存在: $BENCHMARK_DIR"
    exit 1
fi

# 获取当前时间并创建结果目录
TIMESTAMP=$(date "+%m月-%d_%H-%M-%S")
RESULTS_DIR="$SCRIPT_DIR/实验结果分析-$TIMESTAMP"

echo "=========================================="
echo "运行所有分析脚本"
echo "=========================================="
echo "主目录: $SCRIPT_DIR"
echo "Benchmark目录: $BENCHMARK_DIR"
echo "结果目录: $RESULTS_DIR"
echo "=========================================="
echo ""

# 创建结果目录
mkdir -p "$RESULTS_DIR"
echo "✓ 创建结果目录: $RESULTS_DIR"
echo ""

# 设置分析脚本目录
ANALYSIS_DIR="$BENCHMARK_DIR/scripts/analysis"

# 检查分析脚本目录是否存在
if [ ! -d "$ANALYSIS_DIR" ]; then
    echo "错误: 分析脚本目录不存在: $ANALYSIS_DIR"
    exit 1
fi

# 记录运行前已存在的文件（用于只移动新生成的文件）
echo "记录现有文件..."
EXISTING_FILES=$(mktemp)
find "$BENCHMARK_DIR" -maxdepth 1 -type f \( \
    -name "branch_coverage_all_protocols_*.png" \
    -o -name "branch_coverage_all_protocols_*.pdf" \
    -o -name "branch_coverage_*.png" \
    -o -name "branch_coverage_*.pdf" \
    -o -name "line_coverage_all_protocols_*.png" \
    -o -name "state_coverage_all_protocols_*.png" \
    -o -name "state_transition_coverage_all_protocols_*.png" \
    -o -name "final_metrics_all_protocols_*.csv" \
    -o -name "a12_statistics.csv" \
    -o -name "speedup_statistics.csv" \
\) -printf "%f\n" > "$EXISTING_FILES" 2>/dev/null || true
echo ""

# 运行所有分析脚本
echo "开始运行分析脚本..."
echo ""

# 1. 生成所有覆盖率和状态图表
echo "[1/3] 生成所有度量指标图表（分支、行、状态、迁移）..."
python3 "$ANALYSIS_DIR/plot_metrics_all.py" "$BENCHMARK_DIR" || {
    echo "警告: 图表生成失败"
}
echo ""

# 2. 收集最终指标
echo "[2/3] 收集最终覆盖率指标..."
python3 "$ANALYSIS_DIR/collect_final_metrics_all.py" "$BENCHMARK_DIR" || {
    echo "警告: 最终指标收集失败"
}
echo ""

# 3. 计算统计指标 (A12 & Speed-up)
echo "[3/3] 计算统计指标 (A12 & Speed-up)..."
python3 "$ANALYSIS_DIR/calculate_stats.py" "$BENCHMARK_DIR" || {
    echo "警告: 统计指标计算失败"
}
echo ""

# 移动新生成的文件到结果目录
echo "=========================================="
echo "移动新生成的结果文件到结果目录..."
echo "=========================================="

# 查找并移动新生成的文件（排除运行前已存在的文件）
FILES_MOVED=0

# 移动所有生成的PDF和PNG文件
for pattern in "branch_coverage_all_protocols_*.pdf" \
                "line_coverage_all_protocols_*.pdf" \
                "state_count_all_protocols_*.pdf" \
                "state_transitions_all_protocols_*.pdf" \
                "*.png"; do
    for file in "$BENCHMARK_DIR"/$pattern; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            # 检查文件是否在运行前已存在
            if ! grep -q "^$filename$" "$EXISTING_FILES" 2>/dev/null; then
                mv "$file" "$RESULTS_DIR/" 2>/dev/null && {
                    echo "✓ 移动: $filename"
                    ((FILES_MOVED++))
                }
            fi
        fi
    done
done

# 移动CSV文件（只移动新生成的）
for file in "$BENCHMARK_DIR"/final_metrics_all_protocols_*.csv \
            "$BENCHMARK_DIR"/a12_statistics.csv \
            "$BENCHMARK_DIR"/speedup_statistics.csv; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        # 检查文件是否在运行前已存在
        if ! grep -q "^$filename$" "$EXISTING_FILES" 2>/dev/null; then
            mv "$file" "$RESULTS_DIR/" 2>/dev/null && {
                echo "✓ 移动: $filename"
                ((FILES_MOVED++))
            }
        fi
    fi
done

# 清理临时文件
rm -f "$EXISTING_FILES"

echo ""
echo "=========================================="
echo "分析完成！"
echo "=========================================="
echo "结果目录: $RESULTS_DIR"
echo "移动文件数: $FILES_MOVED"
echo ""
echo "生成的文件："
ls -lh "$RESULTS_DIR" | tail -n +2 | awk '{print "  " $9 " (" $5 ")"}'
echo ""
echo "=========================================="
