# Desire Paths on Hugging Face Spaces: the open-source HydraDB engine (graph-node v0.4.0, built from source by
# github.com/Jmohak2004/desire-paths/.github/workflows/image.yml) plus the dashboard, in one container.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 RUST_MIN_STACK=33554432 PORT=7860
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git libcypher-parser-dev libgraphblas-dev python3 python3-venv && \
    rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://github.com/Jmohak2004/desire-paths/releases/download/hydradb-v0.4.0/graph-node-linux-x86_64.tar.gz \
      | tar xz -C /usr/local/bin && graph-node --help >/dev/null 2>&1 || true
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir \
      "selfgraph==0.2.1" "kuzu==0.11.3" openai numpy fastapi uvicorn
RUN git clone --depth 1 https://github.com/Jmohak2004/desire-paths /src && mkdir -p /app/results/cache /app/results/graphs && \
    cp -r /src/bench /src/desirepaths /src/dashboard /app/ && cp /src/results/*.json /src/results/*.md /app/results/ && \
    cp /src/results/cache/llm.jsonl /app/results/cache/ && cp /src/deploy/start.sh /usr/local/bin/start.sh && \
    chmod +x /usr/local/bin/start.sh && rm -rf /src && chown -R 1000:1000 /app
USER 1000
EXPOSE 7860
CMD ["/usr/local/bin/start.sh"]
