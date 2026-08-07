FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

EXPOSE 5010

# 默认命令（compose 里 api / scheduler 会覆盖，见 docker-compose.yml）
CMD ["python", "api/proxy_api.py"]