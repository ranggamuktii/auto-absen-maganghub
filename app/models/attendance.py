"""Attendance service for MagangHub Monev API."""

from app.config import settings
from app.auth.sso import get_access_token
from app.api.client import ApiClient


class DailyLog:
    """Daily attendance log."""

    def __init__(self, data: dict):
        """Initialize from API response JSON.

        Args:
            data: Log data from the API.
        """
        self.id: int = data["id"]
        self.date: str = data["date"]
        self.clock_in: str | None = data.get("clock_in")
        self.activity_log: str | None = data.get("activity_log")
        self.lesson_learned: str | None = data.get("lesson_learned")
        self.obstacles: str | None = data.get("obstacles")


class AttendanceService:
    """Service for attendance operations."""

    def __init__(self, username: str | None = None, password: str | None = None):
        """Initialize with optional credentials; call login() first."""
        self._username = username
        self._password = password
        self._client: ApiClient | None = None

    def login(self) -> None:
        """Authenticate and initialize the API client."""
        self._ensure_client()

    def _ensure_client(self):
        """Create the API client on first use."""
        if not self._client:
            token = get_access_token(self._username, self._password)
            self._client = ApiClient(token)

    @staticmethod
    def attendance_payload(date: str) -> dict:
        """Build the attendance payload for a given date.

        Args:
            date: Date in YYYY-MM-DD format.

        Returns:
            Payload that clock_in sends to the API.
        """
        try:
            lat = float(settings.latitude)
        except (ValueError, TypeError):
            lat = settings.latitude

        try:
            lon = float(settings.longitude)
        except (ValueError, TypeError):
            lon = settings.longitude

        return {
            "date": date,
            "status": "PRESENT",
            "latitude": lat,
            "longitude": lon,
            "location": settings.location,
            "activity_log": settings.activity_log,
            "lesson_learned": settings.lesson_learned,
            "obstacles": settings.obstacles,
        }

    def clock_in(self, date: str) -> dict:
        """Submit attendance (PRESENT) for a given date.

        Args:
            date: Date in YYYY-MM-DD format.

        Returns:
            JSON response from the API.
        """
        self._ensure_client()
        return self._client.post("/attendances/with-daily-log", self.attendance_payload(date))

    def get_log(self, date: str) -> DailyLog | None:
        """Fetch the attendance log for a given date.

        The API ignores the date parameter and returns recent logs,
        so match the date field manually across pages.

        Args:
            date: Date in YYYY-MM-DD format.

        Returns:
            DailyLog if found, None otherwise.
        """
        self._ensure_client()
        seen = set()
        page = 1
        while True:
            resp = self._client.get("/daily-logs", params={"date": date, "page": page})
            data = resp.get("data", [])
            for row in data:
                if row.get("date") == date:
                    return DailyLog(row)
            if not data:
                return None
            first_id = data[0].get("id")
            if first_id in seen:
                return None
            seen.add(first_id)
            total = resp.get("total")
            if isinstance(total, int) and len(seen) * len(data) >= total:
                return None
            page += 1
