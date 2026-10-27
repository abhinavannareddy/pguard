# PGuard engine (Python + native C++ core). Multi-stage; runs as non-root, read-only root fs friendly.
FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends g++ cmake make && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY cpp ./cpp
RUN cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release && cmake --build cpp/build
COPY pyproject.toml README.md ./
COPY src ./src
COPY models ./models
RUN pip install --no-cache-dir --prefix=/install ".[stack,crypto]"

FROM python:3.12-slim
RUN useradd --system --uid 10001 --create-home pguard
COPY --from=build /install /usr/local
COPY --from=build /src/cpp/build/libpgsignal.so /app/cpp/build/libpgsignal.so
COPY --from=build /src/models /app/models
COPY probe.py /app/probe.py
ENV PGUARD_DB=/data/pguard.db ONNX_MODEL=/app/models/pguard_motion.onnx PYTHONUNBUFFERED=1
VOLUME /data
USER 10001
EXPOSE 8765 50051
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/api/status')" || exit 1
ENTRYPOINT ["pguard"]
CMD ["serve"]
