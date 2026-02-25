"""Skill Evolution shared library — auto-loads .env on import."""

import os
from pathlib import Path


def _load_dotenv():
    """Minimal .env loader: walk up from cwd to find .env, parse KEY=VALUE lines."""
    for d in [Path.cwd(), *Path.cwd().parents]:
        env_file = d / ".env"
        if env_file.is_file():
            try:
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    # Don't overwrite existing env vars (explicit env takes priority)
                    if key and key not in os.environ:
                        os.environ[key] = value
            except OSError:
                pass
            return


_load_dotenv()
