# Waynis AI — Docker (Render / HF Spaces / kudo)
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" aiofiles
EXPOSE 7860
CMD ["python", "app.py"]
