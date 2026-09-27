FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Index is built locally (needs OPENAI_API_KEY) and copied in: run scripts/ingest.py before docker build
EXPOSE 7860
CMD ["python", "bot.py", "--host", "0.0.0.0"]
