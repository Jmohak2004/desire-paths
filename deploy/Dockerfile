# Desire Paths: self-hosted HydraDB (open-source engine, built from source) + the dashboard, in one container.
# Build context: this repo, with hydra-db/hydradb (v0.4.0) checked out at ./hydradb (the image workflow does this).

# ---- HydraDB toolchain, as in hydra-db/hydradb's own Dockerfile
FROM ubuntu:24.04 AS chef
ARG RUST_VERSION=1.99.0
ENV DEBIAN_FRONTEND=noninteractive CARGO_HOME=/usr/local/cargo RUSTUP_HOME=/usr/local/rustup \
    RUSTUP_TOOLCHAIN=${RUST_VERSION} PATH=/usr/local/cargo/bin:${PATH}
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang cmake curl libclang-dev \
      libcypher-parser-dev libffi-dev libgraphblas-dev pkg-config && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
      sh -s -- -y --profile minimal --default-toolchain "${RUST_VERSION}" && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /workspace

# LAGraph has no Ubuntu package; HydraDB's script builds it statically.
FROM chef AS lagraph
COPY hydradb/scripts/install_lagraph.sh /tmp/install_lagraph.sh
RUN bash /tmp/install_lagraph.sh /opt/lagraph

# Only the graph-node server, with the features this project runs on.
FROM chef AS builder
COPY --from=lagraph /opt/lagraph /opt/lagraph
ENV LAGRAPH_LIB_DIR=/opt/lagraph/lib CARGO_PROFILE_RELEASE_DEBUG=0
COPY hydradb/ .
RUN cargo build --locked --release --features server-runtime --bin graph-node && \
    strip --strip-debug target/release/graph-node

# ---- Runtime: HydraDB node + Python dashboard
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 RUST_MIN_STACK=33554432
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl libcypher-parser-dev libgraphblas-dev python3 python3-venv && \
    rm -rf /var/lib/apt/lists/*
COPY --from=builder /workspace/target/release/graph-node /usr/local/bin/graph-node
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir \
      "selfgraph==0.2.1" "kuzu==0.11.3" openai numpy fastapi uvicorn
WORKDIR /app
COPY bench ./bench
COPY desirepaths ./desirepaths
COPY dashboard ./dashboard
COPY results/*.json results/*.md ./results/
COPY results/cache/llm.jsonl ./results/cache/llm.jsonl
COPY deploy/start.sh /usr/local/bin/start.sh
# Hugging Face Spaces runs the container as uid 1000
RUN useradd -m -u 1000 user 2>/dev/null || true; chmod +x /usr/local/bin/start.sh && \
    mkdir -p /app/results/graphs && chown -R 1000:1000 /app
USER 1000
ENV PORT=7860
EXPOSE 7860
CMD ["/usr/local/bin/start.sh"]
