"""SSO authentication for Kemnaker Monev API."""

import requests
import re
from urllib.parse import urlparse, parse_qs

from app.api.client import TIMEOUT
from app.config import settings

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)



def _extract_csrf(html: str) -> str:
    """Extract CSRF token from the SSO login page.

    Args:
        html: Login page HTML.

    Returns:
        CSRF token value.

    Raises:
        Exception: If token is not found.
    """
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    if not match:
        raise Exception("CSRF token tidak ditemukan")
    return match.group(1)


def get_access_token(username: str | None = None, password: str | None = None) -> str:
    """Login to Kemnaker SSO and obtain an access token.

    Args:
        username: Optional SIAPkerja username (defaults to settings.siapkerja_username).
        password: Optional SIAPkerja password (defaults to settings.siapkerja_password).

    Returns:
        Access token for the Monev API.

    Raises:
        Exception: If login or token retrieval fails.
    """
    user = (username or settings.siapkerja_username or "").strip()
    pwd = (password or settings.siapkerja_password or "").strip()
    if not user or not pwd:
        raise Exception("Email/username dan password SIAPkerja wajib diisi.")

    s = requests.Session()
    s.headers.update({
        "User-Agent": BROWSER_USER_AGENT,
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    })

    r = s.get(
        f"{settings.api_base}/auth/login",
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://monev.maganghub.kemnaker.go.id/",
        },
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise Exception(f"Gagal membuka halaman login (HTTP {r.status_code})")
    sso_url = r.text.strip().strip('"')
    state = parse_qs(urlparse(sso_url).query).get("state", [None])[0]

    r2 = s.get(sso_url, timeout=TIMEOUT)
    if not r2.ok:
        raise Exception(f"Gagal membuka halaman SSO (HTTP {r2.status_code})")
    csrf = _extract_csrf(r2.text)

    r3 = s.post(
        f"{settings.auth_base}/auth/login",
        json={"username": user, "password": pwd},
        headers={
            "X-CSRF-TOKEN": csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": settings.auth_base,
            "Referer": sso_url,
        },
        timeout=TIMEOUT,
    )
    if r3.status_code != 200:
        raise Exception(r3.json().get("message", "Login gagal"))

    r3_data = r3.json().get("data", {})
    redirect_uri = r3_data.get("redirect_uri")
    if not redirect_uri:
        raise Exception("Redirect URI tidak ditemukan pada respons login.")
    r4 = s.get(redirect_uri, allow_redirects=True, timeout=TIMEOUT)
    code_list = parse_qs(urlparse(r4.url).query).get("code")
    if not code_list:
        raise Exception("Kode otorisasi tidak ditemukan pada redirect.")
    code = code_list[0]

    r5 = s.get(
        f"{settings.api_base}/auth/login/callback",
        params={"code": code, "state": state},
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        timeout=TIMEOUT,
    )
    if not r5.ok:
        raise Exception(f"Callback login gagal (HTTP {r5.status_code})")
    data = r5.json()
    token = data.get("access_token") or data.get("data", {}).get("access_token")
    if not token:
        raise Exception("Gagal mendapatkan access token")
    return token
