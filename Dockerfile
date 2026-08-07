# Hugging Face Spaces — Docker space
FROM python:3.11-slim
WORKDIR /app
COPY app.py .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"
EXPOSE 7860
CMD ["python", "app.py"]
