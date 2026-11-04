"""HTTP client for MagangHub Monev API."""

import requests

TIMEOUT = 30
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)



class ApiError(Exception):
    """API error with HTTP status code."""

    def __init__(self, status_code: int, message: str):
        """Initialize with a status code and message.

        Args:
            status_code: HTTP status code.
            message: Error message.
        """
        self.status_code = status_code
        super().__init__(f"API {status_code}: {message}")


class ApiClient:
    """HTTP client with Bearer token authentication."""

    def __init__(self, token: str):
        """Initialize client with an access token.

        Args:
            token: Bearer access token.
        """
        from app.config import settings
        self.base_url = settings.api_base
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Origin": "https://monev.maganghub.kemnaker.go.id",
            "Referer": "https://monev.maganghub.kemnaker.go.id/",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def get(self, path: str, params: dict | None = None) -> dict:
        """Send a GET request.

        Args:
            path: Endpoint path.
            params: Query parameters.

        Returns:
            JSON response body.
        """
        r = self.session.get(f"{self.base_url}{path}", params=params, timeout=TIMEOUT)
        return self._handle(r)

    def post(self, path: str, data: dict) -> dict:
        """Send a POST request.

        Args:
            path: Endpoint path.
            data: JSON payload.

        Returns:
            JSON response body.
        """
        r = self.session.post(f"{self.base_url}{path}", json=data, timeout=TIMEOUT)
        return self._handle(r)

    def _handle(self, r: requests.Response) -> dict:
        """Process an HTTP response.

        Args:
            r: Response from requests.

        Returns:
            JSON body.

        Raises:
            Exception: If status code is not 2xx.
        """
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text}

        if not r.ok:
            raise ApiError(r.status_code, body.get("message", r.text[:200]))

        return body
