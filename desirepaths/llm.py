"""One pinned LLM and one pinned embedding model for every agent, via NVIDIA's OpenAI-compatible API.

Every call is metered (calls, input/output tokens, latency) and recorded in an
append-only JSONL cache keyed by the exact request. A cache hit replays the
usage and latency that were measured when the call was made live, so
`make eval` can regenerate the results table without new API spend while still
reporting measured numbers. `DP_CACHE=off` forces live calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
# Requested model was google/gemma-4-31b-it; on 2026-11-16 it timed out (>45-200 s per call) on NVIDIA's API, so the
# measured runs pin the fastest model that solved the graph-agent probe (see results/model_probe.md).
MODEL = os.environ.get("DP_MODEL", "poolside/laguna-xs-2.1")
EMBED_MODEL = os.environ.get("DP_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")  # the only NVIDIA embedder serving this key
TEMPERATURE = 0.0
MAX_TOKENS = 400
ATTEMPTS = 20  # rate limits (429) and timeouts on the shared free tier: back off up to ~15 min
ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "results" / "cache"


def load_dotenv() -> None:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()


@dataclass
class Meter:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cached: int = 0
    log: list[dict] = field(default_factory=list)

    def snapshot(self) -> dict:
        return dict(llm_calls=self.calls, input_tokens=self.input_tokens, output_tokens=self.output_tokens,
                    llm_latency_s=round(self.latency_s, 3))


class LLM:
    def __init__(self, concurrency: int = 6):
        from openai import AsyncOpenAI

        key = os.environ.get("NVIDIA_API_KEY")
        self.client = AsyncOpenAI(base_url=BASE_URL, api_key=key or "missing", max_retries=0, timeout=120)
        self.has_key = bool(key)
        self.sem = asyncio.Semaphore(concurrency)
        self.use_cache = os.environ.get("DP_CACHE", "on") != "off"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.cache_path = CACHE_DIR / "llm.jsonl"
        self.cache: dict[str, dict] = {}
        if self.cache_path.exists():
            for line in self.cache_path.open():
                try:
                    r = json.loads(line)
                    self.cache[r["key"]] = r
                except ValueError:
                    pass
        self._lock = asyncio.Lock()

    async def chat(self, messages: list[dict], meter: Meter, max_tokens: int = MAX_TOKENS, tag: str = "") -> str:
        req = dict(model=MODEL, messages=messages, temperature=TEMPERATURE, max_tokens=max_tokens)
        key = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()
        hit = self.cache.get(key) if self.use_cache else None
        if hit is None:
            if not self.has_key:
                raise RuntimeError("NVIDIA_API_KEY is not set (put it in .env or export it)")
            hit = await self._live(req, key)
        else:
            meter.cached += 1
        meter.calls += 1
        meter.input_tokens += hit["in"]
        meter.output_tokens += hit["out"]
        meter.latency_s += hit["latency"]
        meter.log.append({"tag": tag, "in": hit["in"], "out": hit["out"]})
        return hit["text"]

    async def _live(self, req: dict, key: str) -> dict:
        delay = 2.0
        for attempt in range(ATTEMPTS):
            try:
                async with self.sem:
                    t0 = time.perf_counter()
                    r = await self.client.chat.completions.create(**req)
                    lat = time.perf_counter() - t0
                text = r.choices[0].message.content or ""
                u = r.usage
                rec = {"key": key, "text": text, "in": u.prompt_tokens if u else 0, "out": u.completion_tokens if u else 0,
                       "latency": round(lat, 3), "model": req["model"], "ts": time.time()}
                async with self._lock:
                    self.cache[key] = rec
                    with self.cache_path.open("a") as f:
                        f.write(json.dumps(rec) + "\n")
                return rec
            except Exception as e:  # rate limits and transient errors: back off and retry
                status = getattr(e, "status_code", None)
                if status in (400, 401, 403, 404) or attempt == ATTEMPTS - 1:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
        raise RuntimeError("unreachable")


class Embedder:
    """Cached passage/query embeddings (same model throughout)."""

    def __init__(self):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(base_url=BASE_URL, api_key=os.environ.get("NVIDIA_API_KEY") or "missing", timeout=120)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.qpath = CACHE_DIR / "emb_queries.json"
        self.qcache: dict[str, list[float]] = json.loads(self.qpath.read_text()) if self.qpath.exists() else {}
        self.calls = 0

    async def _embed(self, texts: list[str], input_type: str) -> np.ndarray:
        delay = 2.0
        for attempt in range(8):
            try:
                r = await self.client.embeddings.create(
                    model=EMBED_MODEL, input=texts, encoding_format="float",
                    extra_body={"input_type": input_type, "truncate": "END"})
                v = np.array([d.embedding for d in r.data], dtype=np.float32)
                return v / np.linalg.norm(v, axis=1, keepdims=True)
            except Exception as e:
                if getattr(e, "status_code", None) in (400, 401, 403, 404) or attempt == 7:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
        raise RuntimeError("unreachable")

    async def passages(self, name: str, texts: list[str], batch: int = 64) -> np.ndarray:
        path = CACHE_DIR / f"emb_{name}_{hashlib.sha256(chr(0).join(texts).encode()).hexdigest()[:12]}.npy"
        if path.exists():
            return np.load(path).astype(np.float32)
        out = []
        for i in range(0, len(texts), batch):
            out.append(await self._embed(texts[i:i + batch], "passage"))
        m = np.concatenate(out)
        np.save(path, m.astype(np.float16))
        return m

    async def query(self, text: str) -> np.ndarray:
        self.calls += 1
        if text in self.qcache:
            return np.array(self.qcache[text], dtype=np.float32)
        v = (await self._embed([text], "query"))[0]
        self.qcache[text] = [round(float(x), 5) for x in v]
        return v

    def flush(self) -> None:
        self.qpath.write_text(json.dumps(self.qcache))


def parse_json(text: str) -> dict:
    """Extract the first JSON object from a model reply (tolerates code fences and prose)."""
    t = text.strip()
    if "```" in t:
        for part in t.split("```"):
            p = part.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                t = p
                break
    start = t.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            if t[i] == "{":
                depth += 1
            elif t[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except ValueError:
                        break
        start = t.find("{", start + 1)
    return {}
