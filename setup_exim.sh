#!/bin/bash  

# Generate image name: xpg-月份-日-{协议}
MONTH=$(date +%-m)
DAY=$(date +%-d)
IMAGE_NAME="xpg-${MONTH}-${DAY}-exim"

LIVE555_DIR="./benchmark/subjects/SMTP/Exim"  

if [ ! -d "$LIVE555_DIR" ]; then  
    echo "错误: exim目录不存在"  
    exit 1  
fi  


rm -r $LIVE555_DIR/aflnet 2>&1 >/dev/null  
cp -r aflnet $LIVE555_DIR/aflnet  

rm -r $LIVE555_DIR/chatafl 2>&1 >/dev/null  
cp -r chatafl $LIVE555_DIR/chatafl  

rm -r $LIVE555_DIR/xpgfuzz 2>&1 >/dev/null  
cp -r xpgfuzz $LIVE555_DIR/xpgfuzz

rm -r $LIVE555_DIR/aflnet+s1 2>&1 >/dev/null  
cp -r aflnet+s1 $LIVE555_DIR/aflnet+s1  
  

# 构建exim Docker镜像  
echo "构建exim Docker镜像..."  
cd $LIVE555_DIR  
docker build . -t $IMAGE_NAME --build-arg MAKE_OPT $NO_CACHE
  
echo "exim Docker镜像构建完成！"  
  
# 验证镜像  
if docker images | grep -q "$IMAGE_NAME"; then  
    echo "✓ exim镜像已成功创建: $IMAGE_NAME"  
    docker images | grep "$IMAGE_NAME"  
else  
    echo "✗ exim镜像创建失败"  
    exit 1  
fi