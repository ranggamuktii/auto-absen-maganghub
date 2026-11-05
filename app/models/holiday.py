"""Holiday calendar from the MagangHub Monev API."""

from app.auth.sso import get_access_token
from app.api.client import ApiClient

PAGE_LIMIT = 100
MAX_PAGES = 20


class Holiday:
    """A single holiday record."""

    def __init__(self, data: dict):
        """Initialize from API response JSON.

        Args:
            data: Holiday data from the API.
        """
        self.id: int | None = data.get("id")
        self.date: str = data["date"]
        self.name: str = data.get("name") or ""
        self.type: str = data.get("type") or ""
        self.scope: str = data.get("scope") or ""

    @property
    def is_national(self) -> bool:
        """Return True if this holiday applies nationwide.

        Regional holidays belong to a particular province or regency, so
        they are not treated as national and are left alone.
        """
        return (self.scope or self.type).upper() == "NATIONAL"


class HolidayService:
    """Service for reading the holiday calendar.

    The calendar is fetched once and cached, so checking several dates
    costs a single API request.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        client: ApiClient | None = None,
    ):
        """Initialize with optional credentials or pre-authenticated API client."""
        self._username = username
        self._password = password
        self._client: ApiClient | None = client
        self._cache: list[Holiday] | None = None

    def _ensure_client(self):
        """Create the API client on first use."""
        if not self._client:
            self._client = ApiClient(get_access_token(self._username, self._password))

    def list_holidays(self) -> list[Holiday]:
        """Fetch every holiday visible to the account, following pagination.

        Returns:
            Holiday list, cached after the first successful call.

        Raises:
            ApiError: If the API rejects the request.
            requests.exceptions.RequestException: If the network call fails.
        """
        if self._cache is not None:
            return self._cache

        self._ensure_client()
        holidays: list[Holiday] = []
        page = 1
        while page <= MAX_PAGES:
            resp = self._client.get(
                "/holidays", params={"page": page, "limit": PAGE_LIMIT}
            )
            rows = resp.get("data") or []
            if not rows:
                break
            holidays.extend(Holiday(r) for r in rows)
            total = resp.get("total")
            if isinstance(total, int) and len(holidays) >= total:
                break
            page += 1

        self._cache = holidays
        return holidays

    def find(self, date: str) -> Holiday | None:
        """Return the national holiday on a given date.

        Args:
            date: Date in YYYY-MM-DD format.

        Returns:
            The national Holiday, or None if that date is a workday.
        """
        for holiday in self.list_holidays():
            if holiday.date == date and holiday.is_national:
                return holiday
        return None