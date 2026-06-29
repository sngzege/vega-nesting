FROM rust:1.83 as builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/build_engine.sh .
COPY app/requirements.txt .
RUN bash build_engine.sh

# Stage 2: Python runtime
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libssl3 \
    libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=builder /app/lbf /usr/local/bin/lbf
RUN chmod +x /usr/local/bin/lbf

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
