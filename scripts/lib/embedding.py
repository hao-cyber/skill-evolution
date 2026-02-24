"""Shared embedding computation for Skill Evolution scripts."""

import json
import os
import sys
import urllib.request


def compute_embedding(text):
    """Compute embedding via DashScope text-embedding-v3. Returns list[float] or None."""
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        return None
    text = text[:8000]
    payload = {
        "model": "text-embedding-v3",
        "input": text,
        "dimension": 1024,
    }
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
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
