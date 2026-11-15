#!/bin/bash
# Start a single local HydraDB v0.4.0 node (plaintext, dev) backed by ./.hydradb. Bolt 7687, HTTP 8443, admin 9090.
# Build once: git clone --branch v0.4.0 https://github.com/hydra-db/hydradb ~/hydradb && cd ~/hydradb &&
#   cargo build --locked --release --features server-runtime --bin graph-node
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${HYDRADB_BIN:-$HOME/hydradb/target/release/graph-node}"
mkdir -p "$ROOT/.hydradb/store" "$ROOT/.hydradb/cache"
[ -f "$ROOT/.hydradb/auth-token" ] || printf '%s\n' 'local-development-token-32-bytes' > "$ROOT/.hydradb/auth-token"
export CLOUD_PROVIDER=local LOCAL_PATH="$ROOT/.hydradb/store" GRAPH_NAMESPACE=default GRAPH_ID=default
export GRAPH_CELL_ID=cell-0 GRAPH_CELLS=cell-0 GRAPH_NODE_ID=node-0
export GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687
export GRAPH_DATA_CACHE_DIR="$ROOT/.hydradb/cache" GRAPH_AUTH_TOKEN_FILE="$ROOT/.hydradb/auth-token"
export GRAPH_ALLOW_PLAINTEXT=true RUST_MIN_STACK=33554432 GRAPH_USAGE_REPORT_ENABLED=false
exec "$BIN"
