#!/bin/bash

# 清理脚本说明：
# 只删除容器，不删除镜像
# 安全措施：
# 1. 只清理基于特定镜像的容器（不会误删其他项目的容器）
# 2. 先显示将要删除的容器，给用户确认机会
# 3. 不会删除正在运行的容器（除非明确指定）
# 4. 不会删除有数据卷的容器（除非明确指定）

# 协议名称列表（基础名称，用于匹配）
subjects=(lightftp bftpd proftpd pure-ftpd exim live555 kamailio forked-daapd lighttpd1)

# 安全选项
FORCE_STOP=${FORCE_STOP:-0}  # 是否强制停止正在运行的容器（默认：否）
SKIP_CONFIRM=${SKIP_CONFIRM:-0}  # 是否跳过确认（默认：否，需要确认）

echo "Docker容器清理脚本（保留镜像）"
echo "=================================="
echo "安全说明："
echo "  - 只清理基于项目镜像的容器"
echo "  - 不会删除其他项目的容器"
echo "  - 不会删除镜像"
echo "  - 默认不会强制停止正在运行的容器"
echo ""

# 1. 清理基于旧格式镜像的容器（直接使用协议名称）
echo "1. 查找基于旧格式镜像的容器（如: lightftp, bftpd 等）..."
total_containers=0
containers_to_remove=()

for subject in ${subjects[@]}; do
    # 查找基于该镜像的容器
    container_ids=$(docker ps -a -q --filter ancestor=${subject}:latest 2>/dev/null)
    if [ -n "$container_ids" ]; then
        for cid in $container_ids; do
            container_name=$(docker ps -a --filter id=$cid --format "{{.Names}}" 2>/dev/null)
            container_status=$(docker ps -a --filter id=$cid --format "{{.Status}}" 2>/dev/null)
            containers_to_remove+=("$cid|$container_name|$container_status|${subject}:latest")
            total_containers=$((total_containers + 1))
        done
    fi
done

# 2. 清理基于新格式镜像的容器（xpg-月份-日-{协议}）
echo ""
echo "2. 查找基于新格式镜像的容器（xpg-月份-日-{协议}）..."

# 如果提供了日期参数，只清理指定日期的镜像的容器
if [ -n "$1" ]; then
    DATE_PATTERN="xpg-${1}-"
    echo "  只查找日期为 ${1} 的镜像的容器 (格式: 月份-日, 如 12-20)..."
    image_list=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^${DATE_PATTERN}")
else
    # 清理所有xpg-开头的镜像的容器
    echo "  查找所有基于 xpg-* 格式镜像的容器..."
    image_list=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^xpg-")
fi

if [ -n "$image_list" ]; then
    # 使用临时文件避免子shell问题
    temp_file=$(mktemp)
    echo "$image_list" | while read image; do
        if [ -n "$image" ]; then
            # 查找基于该镜像的容器
            container_ids=$(docker ps -a -q --filter ancestor=${image} 2>/dev/null)
            if [ -n "$container_ids" ]; then
                for cid in $container_ids; do
                    container_name=$(docker ps -a --filter id=$cid --format "{{.Names}}" 2>/dev/null)
                    container_status=$(docker ps -a --filter id=$cid --format "{{.Status}}" 2>/dev/null)
                    echo "$cid|$container_name|$container_status|${image}" >> "$temp_file"
                done
            fi
        fi
    done
    
    # 读取临时文件内容到数组
    if [ -f "$temp_file" ] && [ -s "$temp_file" ]; then
        while IFS= read -r line; do
            containers_to_remove+=("$line")
            total_containers=$((total_containers + 1))
        done < "$temp_file"
        rm -f "$temp_file"
    fi
else
    echo "  没有找到匹配的镜像"
fi

# 显示将要删除的容器列表
echo ""
echo "=================================="
echo "找到 $total_containers 个容器："
echo "=================================="

if [ ${#containers_to_remove[@]} -eq 0 ]; then
    echo "没有找到需要清理的容器"
    exit 0
fi

# 显示容器列表
running_count=0
stopped_count=0
for container_info in "${containers_to_remove[@]}"; do
    IFS='|' read -r cid name status image <<< "$container_info"
    if echo "$status" | grep -q "Up"; then
        echo "  [运行中] $name ($cid) <- $image"
        running_count=$((running_count + 1))
    else
        echo "  [已停止] $name ($cid) <- $image"
        stopped_count=$((stopped_count + 1))
    fi
done

echo ""
echo "统计："
echo "  - 运行中的容器: $running_count 个"
echo "  - 已停止的容器: $stopped_count 个"
echo "  - 总计: $total_containers 个"
echo ""

# 安全检查：如果有正在运行的容器
if [ $running_count -gt 0 ] && [ "$FORCE_STOP" != "1" ]; then
    echo "⚠️  警告：发现 $running_count 个正在运行的容器！"
    echo "   默认不会强制停止正在运行的容器（可能导致数据丢失）"
    echo ""
    echo "   如果要强制停止，请设置环境变量："
    echo "   FORCE_STOP=1 ./clean.sh"
    echo ""
    echo "   或者只清理已停止的容器，运行中的容器将被跳过"
    echo ""
fi

# 确认删除
if [ "$SKIP_CONFIRM" != "1" ]; then
    echo "是否继续删除这些容器？(y/N)"
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "已取消"
        exit 0
    fi
fi

# 执行删除
echo ""
echo "开始清理容器..."
removed_count=0
skipped_count=0

for container_info in "${containers_to_remove[@]}"; do
    IFS='|' read -r cid name status image <<< "$container_info"
    
    if echo "$status" | grep -q "Up"; then
        # 正在运行的容器
        if [ "$FORCE_STOP" = "1" ]; then
            echo "  停止并删除: $name ($cid)..."
            docker stop $cid 2>/dev/null
            docker rm $cid 2>/dev/null && removed_count=$((removed_count + 1)) || skipped_count=$((skipped_count + 1))
        else
            echo "  跳过运行中的容器: $name ($cid)"
            skipped_count=$((skipped_count + 1))
        fi
    else
        # 已停止的容器
        echo "  删除: $name ($cid)..."
        docker rm $cid 2>/dev/null && removed_count=$((removed_count + 1)) || skipped_count=$((skipped_count + 1))
    fi
done

echo ""
echo "=================================="
echo "清理完成！"
echo "  - 已删除: $removed_count 个容器"
echo "  - 已跳过: $skipped_count 个容器"
echo "  - 镜像已保留"
echo ""
echo "使用说明："
echo "  ./clean.sh                    # 清理所有相关容器（需要确认）"
echo "  ./clean.sh 12-20              # 只清理指定日期（12-20）的容器"
echo "  SKIP_CONFIRM=1 ./clean.sh     # 跳过确认，直接删除"
echo "  FORCE_STOP=1 ./clean.sh       # 强制停止并删除运行中的容器"
