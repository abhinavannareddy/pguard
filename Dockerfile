# PGuard engine. Multi-stage; runs as non-root.
# Live sensing reads `netsh`, so it needs a Windows host. Inside a Linux container PGuard
# reports a feasibility blocker for `probe`; `pguard demo` runs the pipeline on synthetic data.
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
RUN useradd --system --uid 10001 --create-home pguard
COPY --from=build /install /usr/local
ENV PYTHONUNBUFFERED=1
USER 10001
WORKDIR /home/pguard
ENTRYPOINT ["pguard"]
CMD ["demo"]
