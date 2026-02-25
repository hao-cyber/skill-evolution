"""Shared Supabase client for Skill Evolution scripts."""

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

_TIMEOUT = 30  # seconds


def _ssl_context():
    """Create SSL context with best-effort CA bundle resolution.

    Handles macOS where Python's default OpenSSL often can't find system CAs.
    Falls back to certifi if installed, then to unverified context as last resort.
    """
    # 1. Try system default — works on most Linux and properly configured macOS
    ctx = ssl.create_default_context()
    if ctx.get_ca_certs():
        return ctx
    # 2. Try certifi bundle (common fix for macOS: pip install certifi)
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    # 3. Last resort: skip verification (still TLS-encrypted, no cert check).
    #    Print a warning so users know to install certifi for proper security.
    print("WARNING: SSL CA certificates not found; connections will skip certificate verification. "
          "Run 'pip install certifi' to fix.", file=sys.stderr)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# Lazily initialised — created once on first use
_CTX = None


def _get_ssl_context():
    global _CTX
    if _CTX is None:
        _CTX = _ssl_context()
    return _CTX

# Public registry defaults — users can override via env vars or .env
_DEFAULT_URL = "https://ptwosnmrcfwmfnluufww.supabase.co"
_DEFAULT_ANON_KEY = "sb_publishable_BNikqoeKRZEp2FSqAOJu4A_pJ0UBzby"


def _get_credentials(require_service_key=False):
    """Get Supabase URL and key. Falls back to public registry for anon operations."""
    url = os.environ.get("SUPABASE_URL", "")
    if require_service_key:
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (admin operation)", file=sys.stderr)
            sys.exit(1)
    else:
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url:
            url = _DEFAULT_URL
        if not key:
            key = _DEFAULT_ANON_KEY
    return url, key


def supabase_get(path, service_key=False):
    """Make a Supabase REST API GET request."""
    url, key = _get_credentials(require_service_key=service_key)

    full_url = f"{url}/rest/v1/{path}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR: Supabase GET failed (status={e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, OSError) as e:
        print(f"ERROR: Supabase GET network error: {e}", file=sys.stderr)
        sys.exit(1)


def supabase_rpc(func_name, params, service_key=False, exit_on_error=True):
    """Call a Supabase RPC function.

    Args:
        func_name: RPC function name
        params: dict of parameters
        service_key: use service_role key instead of anon key
        exit_on_error: sys.exit(1) on HTTP error. If False, returns None.
    """
    url, key = _get_credentials(require_service_key=service_key)

    full_url = f"{url}/rest/v1/rpc/{func_name}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    body = json.dumps(params).encode()
    req = urllib.request.Request(full_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=_TIMEOUT) as resp:
            text = resp.read().decode()
            return json.loads(text) if text.strip() else None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"ERROR: Supabase RPC {func_name} failed (status={e.code}): {err_body}", file=sys.stderr)
        if exit_on_error:
            sys.exit(1)
        return None
    except (urllib.error.URLError, OSError) as e:
        print(f"ERROR: Supabase RPC {func_name} network error: {e}", file=sys.stderr)
        if exit_on_error:
            sys.exit(1)
        return None
