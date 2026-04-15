"""
updater.py — Passive auto-update checker via GitHub Releases API.

Checks https://api.github.com/repos/{owner}/{repo}/releases/latest
with a 3-second timeout. On failure, silently returns no update.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Current version — updated at build time by CI
__version__ = "2.2.1"

DEFAULT_REPO = "Imbad0202/data-anonymizer"
TIMEOUT_SECONDS = 3


def check_for_update(
    current_version: Optional[str] = None,
    repo: str = DEFAULT_REPO,
    timeout: int = TIMEOUT_SECONDS,
) -> Tuple[bool, str, str]:
    """Check GitHub Releases for a newer version.

    Parameters
    ----------
    current_version : str or None
        Current app version (e.g. "2.0.0"). Defaults to __version__.
    repo : str
        GitHub repo in "owner/repo" format.
    timeout : int
        HTTP timeout in seconds.

    Returns
    -------
    (has_update, latest_version, download_url)
        has_update is False on any error (silent failure).
    """
    if current_version is None:
        current_version = __version__

    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "")
        latest = tag.lstrip("v")
        html_url = data.get("html_url", "")

        if _is_newer(latest, current_version):
            return True, latest, html_url

        return False, latest, html_url

    except Exception as e:
        logger.debug("Update check failed (expected on restricted networks): %s", e)
        return False, "", ""


def _is_newer(latest: str, current: str) -> bool:
    """Compare semver-like version strings. Returns True if latest > current."""
    try:
        latest_parts = [int(x) for x in latest.split(".")]
        current_parts = [int(x) for x in current.split(".")]
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False
