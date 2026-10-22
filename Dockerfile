# 以官方轻量 Python 镜像为基础
FROM python:3.13-slim

# 容器内工作目录：所有相对路径都基于这里
WORKDIR /app

# 先拷依赖清单并安装——Docker 分层缓存：改代码不会触发重装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷全部代码（受 .dockerignore 约束，排除 venv / 库文件 / 本地库等）
COPY . .

# 暴露端口（uvicorn 监听 8000）
EXPOSE 8000

# 启动顺序：alembic 迁移建表 → 灌示例数据（幂等）→ 起 uvicorn
CMD ["sh", "-c", "alembic upgrade head && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
