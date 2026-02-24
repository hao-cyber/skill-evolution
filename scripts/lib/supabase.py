"""Shared Supabase client for Skill Evolution scripts."""

import json
import os
import sys
import urllib.error
import urllib.request

_TIMEOUT = 30  # seconds


def _get_credentials(require_service_key=False):
    """Get Supabase URL and key. Exits on missing required credentials."""
    url = os.environ.get("SUPABASE_URL", "")
    if require_service_key:
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (admin operation)", file=sys.stderr)
            sys.exit(1)
    else:
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set", file=sys.stderr)
            sys.exit(1)
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
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
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
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
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
