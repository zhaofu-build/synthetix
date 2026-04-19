FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg nodejs npm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 构建前端
COPY synthetix-vue/ ./synthetix-vue/
RUN cd synthetix-vue && npm install && npm run build

# 复制后端代码
COPY . .

# 数据库和素材目录
VOLUME ["/app/src/db", "/app/static"]

EXPOSE 9527

CMD ["python", "main.py"]
