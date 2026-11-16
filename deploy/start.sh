#!/bin/bash
# Start a local HydraDB node inside the container, wait until it is ready, then serve the dashboard.
set -e
D=/tmp/hydradb
mkdir -p "$D/store" "$D/cache"
TOKEN="${HYDRADB_TOKEN:-local-development-token-32-bytes}"
printf '%s\n' "$TOKEN" > "$D/auth-token"

export CLOUD_PROVIDER=local LOCAL_PATH="$D/store" GRAPH_NAMESPACE=default GRAPH_ID=default
export GRAPH_CELL_ID=cell-0 GRAPH_CELLS=cell-0 GRAPH_NODE_ID=node-0
export GRAPH_BOLT_ADDR=127.0.0.1:7687 GRAPH_HTTP_ADDR=127.0.0.1:8443 GRAPH_ADMIN_ADDR=127.0.0.1:9090
export GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687
export GRAPH_DATA_CACHE_DIR="$D/cache" GRAPH_AUTH_TOKEN_FILE="$D/auth-token"
export GRAPH_ALLOW_PLAINTEXT=true GRAPH_USAGE_REPORT_ENABLED=false RUST_MIN_STACK=33554432

graph-node > "$D/node.log" 2>&1 &
for i in $(seq 1 120); do
  curl -s -o /dev/null http://127.0.0.1:9090/readyz && break
  sleep 1
done
curl -s -o /dev/null http://127.0.0.1:9090/readyz || { echo "HydraDB did not start"; tail -50 "$D/node.log"; exit 1; }
echo "HydraDB ready on bolt://127.0.0.1:7687"

export HYDRADB_URI=bolt://127.0.0.1:7687 HYDRADB_TOKEN="$TOKEN"
cd /app
exec /opt/venv/bin/python -m uvicorn dashboard.app:app --host 0.0.0.0 --port "${PORT:-7860}"
