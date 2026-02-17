#!/bin/bash  

# Generate image name: xpg-月份-日-{协议}
MONTH=$(date +%-m)
DAY=$(date +%-d)
IMAGE_NAME="xpg-${MONTH}-${DAY}-forked-daapd"

DIR="./benchmark/subjects/DAAP/forked-daapd"  
  
if [ ! -d "$DIR" ]; then  
    echo "错误: forked-daapd目录不存在"  
    exit 1  
fi  
  
  
rm -r $DIR/aflnet 2>&1 >/dev/null  
cp -r aflnet $DIR/aflnet  
  
rm -r $DIR/chatafl 2>&1 >/dev/null  
cp -r chatafl $DIR/chatafl  

rm -r $DIR/xpgfuzz 2>&1 >/dev/null  
cp -r xpgfuzz $DIR/xpgfuzz

rm -r $DIR/aflnet+s1 2>&1 >/dev/null  
cp -r aflnet+s1 $DIR/aflnet+s1
  

echo "构建forked-daapd Docker镜像..."  
cd $DIR  
docker build . -t $IMAGE_NAME --build-arg MAKE_OPT $NO_CACHE  
  
echo "forked-daapd Docker镜像构建完成！"  
  
# 验证镜像  
if docker images | grep -q "$IMAGE_NAME"; then  
    echo "✓ forked-daapd镜像已成功创建: $IMAGE_NAME"  
    docker images | grep "$IMAGE_NAME"  
else  
    echo "✗ forked-daapd镜像创建失败"  
    exit 1  
fi
