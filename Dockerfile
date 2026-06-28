FROM python:3.10-slim AS builder

WORKDIR /install

COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --prefix=/install/deps -r requirements.txt

FROM python:3.10-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install/deps /usr/local

COPY documents/ documents/
COPY rag_chatbot.py .
COPY app.py .
COPY build_index.py .

RUN python build_index.py

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
