"""
Fairway Intel — GitHub Pages Publisher
Pushes updated index.html to kevinchurch101-jpg/Golf-analysis- via GitHub API.
Uses GH_TOKEN_PUSH secret. NOTE: Never use GITHUB_ prefix — GitHub reserves it.
"""

import base64
import json
import logging
from datetime import datetime
from typing import Optional, Tuple

import requests

from config import GH_TOKEN, GITHUB_REPO, GITHUB_BRANCH, OUTPUT_FILE

log = logging.getLogger(__name__)

GITHUB_API  = "https://api.github.com"
LIVE_URL    = f"https://kevinchurch101-jpg.github.io/Golf-analysis-/"


def _headers() -> dict:
    return {
        "Authorization": f"token {GH_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
    }


def get_current_file_sha(path: str = OUTPUT_FILE) -> Optional[str]:
    """
    Get the current SHA of a file in the repo.
    Required by GitHub API for updates — must include SHA to overwrite existing file.
    Returns SHA string or None if file doesn't exist yet.
    """
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH}, timeout=15)

    if r.status_code == 200:
        sha = r.json().get("sha")
        log.info(f"[GitHub] Current SHA for {path}: {sha[:8]}…")
        return sha
    elif r.status_code == 404:
        log.info(f"[GitHub] {path} does not exist yet — will create.")
        return None
    else:
        log.error(f"[GitHub] Failed to get SHA for {path}: HTTP {r.status_code} — {r.text[:200]}")
        return None


def push_html(
    html_content: str,
    commit_message: Optional[str] = None,
    path: str = OUTPUT_FILE,
) -> Tuple[bool, str]:
    """
    Push HTML content to GitHub Pages.
    Returns (success: bool, message: str).

    Uses GitHub Contents API:
    PUT /repos/{owner}/{repo}/contents/{path}
    Requires base64-encoded content + current file SHA.
    """
    if not GH_TOKEN:
        return False, "GH_TOKEN_PUSH not configured"
    if not html_content:
        return False, "Empty HTML content — nothing to push"

    # Build commit message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    message = commit_message or f"Fairway Intel update — {timestamp}"

    # Encode content
    encoded = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")

    # Get existing SHA (needed to update, not needed for create)
    sha = get_current_file_sha(path)

    # Build payload
    payload: dict = {
        "message": message,
        "content": encoded,
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"

    try:
        r = requests.put(url, headers=_headers(), json=payload, timeout=30)

        if r.status_code in (200, 201):
            action = "updated" if sha else "created"
            log.info(f"[GitHub] Successfully {action} {path}. Live at {LIVE_URL}")
            return True, f"Successfully {action}. Live at {LIVE_URL}"

        elif r.status_code == 401:
            return False, "GitHub auth failed — check GH_TOKEN_PUSH secret"
        elif r.status_code == 403:
            return False, "GitHub permission denied — token may lack repo scope"
        elif r.status_code == 409:
            # SHA conflict — try fetching fresh SHA and retry once
            log.warning("[GitHub] SHA conflict — fetching fresh SHA and retrying…")
            fresh_sha = get_current_file_sha(path)
            if fresh_sha and fresh_sha != sha:
                payload["sha"] = fresh_sha
                r2 = requests.put(url, headers=_headers(), json=payload, timeout=30)
                if r2.status_code in (200, 201):
                    return True, f"Retry succeeded. Live at {LIVE_URL}"
            return False, f"SHA conflict could not be resolved: {r.text[:200]}"
        else:
            log.error(f"[GitHub] Push failed: HTTP {r.status_code} — {r.text[:300]}")
            return False, f"Push failed: HTTP {r.status_code}"

    except requests.Timeout:
        return False, "GitHub push timed out"
    except requests.RequestException as e:
        return False, f"Network error: {e}"


def push_state_file(state: dict, path: str = "state/weekly_state.json") -> Tuple[bool, str]:
    """
    Also push the weekly_state.json to the repo so it persists between runs.
    This is the memory of the system — incremental updates accumulate here.
    """
    if not GH_TOKEN:
        return False, "GH_TOKEN_PUSH not configured"

    content  = json.dumps(state, indent=2, ensure_ascii=False)
    encoded  = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    sha      = get_current_file_sha(path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M ET")

    payload: dict = {
        "message": f"State update — {timestamp}",
        "content": encoded,
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"

    try:
        r = requests.put(url, headers=_headers(), json=payload, timeout=30)
        if r.status_code in (200, 201):
            log.info(f"[GitHub] State file pushed to {path}")
            return True, "State file saved"
        else:
            log.error(f"[GitHub] State push failed: HTTP {r.status_code}")
            return False, f"State push failed: HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, f"State push error: {e}"


def fetch_state_file(path: str = "state/weekly_state.json") -> Optional[dict]:
    """
    Fetch weekly_state.json from repo at the start of each run.
    This is how the system picks up where it left off — incremental not full rewrite.
    """
    if not GH_TOKEN:
        log.warning("[GitHub] No token — cannot fetch state file.")
        return None

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    r   = requests.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH}, timeout=15)

    if r.status_code == 200:
        try:
            data    = r.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            state   = json.loads(content)
            log.info(f"[GitHub] Loaded state from {path}")
            return state
        except Exception as e:
            log.error(f"[GitHub] Failed to parse state file: {e}")
            return None
    elif r.status_code == 404:
        log.info(f"[GitHub] No state file at {path} — starting fresh.")
        return None
    else:
        log.error(f"[GitHub] Failed to fetch state: HTTP {r.status_code}")
        return None


def test_connection() -> Tuple[bool, str]:
    """Test GitHub API connection and token validity."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}"
    try:
        r = requests.get(url, headers=_headers(), timeout=10)
        if r.status_code == 200:
            repo = r.json()
            return True, f"Connected: {repo.get('full_name')} ({repo.get('default_branch')} branch)"
        elif r.status_code == 401:
            return False, "Auth failed — token invalid or expired"
        elif r.status_code == 404:
            return False, f"Repo not found: {GITHUB_REPO}"
        else:
            return False, f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, f"Connection error: {e}"
