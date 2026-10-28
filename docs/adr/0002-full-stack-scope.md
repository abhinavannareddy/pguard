# ADR 0002: full-stack scope (supersedes the deferrals in ADR 0001)

Status: accepted (2026-10-28)

## Decision

PGuard is built with the full stack requested: C++20 core with a C ABI, a C driver shim and an
optional CUDA kernel; Python engine, ONNX Runtime and a Rust edge agent; gRPC/Protobuf services
with Go ingestion and a Go event service; PostgreSQL, TimescaleDB, Redis and Open Policy Agent;
Next.js web app plus Flutter, Kotlin and Swift caregiver clients; Docker, Compose, CI,
OpenTelemetry, Prometheus, Grafana, Terraform and Kubernetes.

Hardware stays one router and one always-on laptop. Sensing is RSSI only unless a probe proves
CSI at 10 Hz or more. Radar nodes remain out of scope.

## Verification status vocabulary

Every stack item is marked RAN (built and its tests executed here), CHECKED (compiled or
validated but not exercised for real) or WRITTEN (authored, unverifiable on this laptop). The
README keeps this table up to date and never claims more than was run.

## Known limits on the build laptop

No NVIDIA GPU (CUDA stays WRITTEN), no Apple toolchain (Swift UI cannot build), no Android SDK
or device. Go, Rust, protoc, OPA and Terraform run in containers. Kubernetes manifests are
validated client-side only; the local cluster belongs to another project and is not touched.
