FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway 会通过 PORT 环境变量传入端口
EXPOSE 8000

CMD ["python", "mcp_server.py"]
