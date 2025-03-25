FROM python:3.10-slim

WORKDIR /app

# 复制依赖文件
COPY ./api/requirements.txt .
# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY ./api /app

# 创建入口点脚本
RUN echo '#!/bin/sh\n\
set -e\n\
exec gunicorn --bind 0.0.0.0:${API_PORT:-5000} --workers 4 "app:app"' > entrypoint.sh \
    && chmod +x entrypoint.sh

EXPOSE ${API_PORT:-5000}

ENTRYPOINT ["./entrypoint.sh"]
