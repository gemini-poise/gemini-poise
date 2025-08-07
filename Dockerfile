FROM python:3.12-slim

WORKDIR /app

# 安装构建工具和 uv
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY .env.example /app/.env
COPY . /app

# 使用 uv 安装依赖
RUN uv pip install --system --no-cache-dir -e .

EXPOSE 8000

CMD ["/bin/bash", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]