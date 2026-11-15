#!/bin/bash
# One command for the demo: fresh local HydraDB node + dashboard on http://127.0.0.1:8000.
# The store only holds synthetic, regenerable data; starting fresh keeps HydraDB fast (namespaces accumulate).
set -e
cd "$(dirname "$0")/.."
pkill -f "uvicorn dashboard.app" 2>/dev/null || true
pkill -f "target/release/graph-node" 2>/dev/null || true
sleep 1
rm -rf .hydradb/store .hydradb/cache
mkdir -p .hydradb/store .hydradb/cache
echo "starting HydraDB node (fresh store)..."
nohup scripts/hydradb_node.sh > .hydradb/node.log 2>&1 &
until curl -s -o /dev/null http://127.0.0.1:9090/readyz; do sleep 1; done
echo "HydraDB ready (Bolt 127.0.0.1:7687)"
echo "starting dashboard (loads the graph into HydraDB, ~20 s) -> http://127.0.0.1:8000"
PYTHONPATH=. exec .venv/bin/python -m uvicorn dashboard.app:app --port 8000
