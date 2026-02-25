"""Shared embedding computation for Skill Evolution scripts.

Supports multiple providers with auto-detection. The first provider
with a configured API key is used. All providers output 1024-dim vectors
to match the pgvector column in the registry.

Provider priority (checked in order):
1. DASHSCOPE_API_KEY  → DashScope text-embedding-v3
2. SILICONFLOW_API_KEY → SiliconFlow BAAI/bge-m3 (free model)
3. OPENAI_API_KEY     → OpenAI text-embedding-3-small (via any compatible API)

Set EMBEDDING_BASE_URL to override the endpoint for provider 3 (e.g. for
local Ollama or other OpenAI-compatible servers).
"""

import json
import os
import sys
import urllib.request

# Each provider: (env_key, base_url, model, payload_builder)
# All must produce 1024-dim embeddings.
_PROVIDERS = [
    {
        "env_key": "DASHSCOPE_API_KEY",
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
        "payload": lambda text: {
            "model": "text-embedding-v3",
            "input": text,
            "dimension": 1024,
        },
    },
    {
        "env_key": "SILICONFLOW_API_KEY",
        "url": "https://api.siliconflow.cn/v1/embeddings",
        "payload": lambda text: {
            "model": "BAAI/bge-m3",
            "input": text,
        },
    },
    {
        "env_key": "OPENAI_API_KEY",
        "url_env": "EMBEDDING_BASE_URL",
        "url": "https://api.openai.com/v1/embeddings",
        "payload": lambda text: {
            "model": "text-embedding-3-small",
            "input": text,
            "dimensions": 1024,
        },
    },
]


def _detect_provider():
    """Return (api_key, url, payload_fn) for the first available provider, or None."""
    for p in _PROVIDERS:
        api_key = os.environ.get(p["env_key"], "")
        if not api_key:
            continue
        url = os.environ.get(p.get("url_env", ""), "") or p["url"]
        return api_key, url, p["payload"]
    return None


def compute_embedding(text):
    """Compute 1024-dim embedding via the first available provider.

    Returns list[float] or None if no provider is configured or the call fails.
    """
    provider = _detect_provider()
    if not provider:
        return None

    api_key, url, build_payload = provider
    text = text[:8000]
    payload = build_payload(text)

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data["data"][0]["embedding"]
    except Exception as e:
        print(f"WARNING: embedding failed: {e}", file=sys.stderr)
        return None
