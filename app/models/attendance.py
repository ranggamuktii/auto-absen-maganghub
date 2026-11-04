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

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        location: str | None = None,
        latitude: float | str | None = None,
        longitude: float | str | None = None,
        activity_log: str | None = None,
        lesson_learned: str | None = None,
        obstacles: str | None = None,
    ):
        """Initialize with optional credentials and attendance defaults."""
        self._username = username
        self._password = password
        self._location = location
        self._latitude = latitude
        self._longitude = longitude
        self._activity_log = activity_log
        self._lesson_learned = lesson_learned
        self._obstacles = obstacles
        self._client: ApiClient | None = None

    def login(self) -> None:
        """Authenticate and initialize the API client."""
        self._ensure_client()

    def get_profile(self) -> dict:
        """Fetch the current user profile from MagangHub Monev API (/users/me).

        Returns:
            Dict containing parsed profile details (name, photo_url, mitra_name, etc.).
        """
        self._ensure_client()
        try:
            resp = self._client.get("/users/me")
        except Exception as e:
            return {"error": str(e)}

        raw = resp.get("data", resp) if isinstance(resp, dict) else {}
        if not isinstance(raw, dict):
            return {}

        name = (
            raw.get("name")
            or raw.get("full_name")
            or raw.get("nama")
            or ""
        )
        photo = (
            raw.get("photo_url")
            or raw.get("photo")
            or raw.get("avatar")
            or raw.get("picture")
            or raw.get("image")
            or ""
        )
        if photo and str(photo).startswith("/"):
            photo = f"https://monev.maganghub.kemnaker.go.id{photo}"

        email = raw.get("email") or ""
        phone = raw.get("phone") or raw.get("phone_number") or raw.get("no_hp") or ""
        nik = raw.get("nik") or ""

        # Internship / Mitra details
        internship = (
            raw.get("internship")
            or raw.get("active_internship")
            or (raw.get("internships")[0] if isinstance(raw.get("internships"), list) and raw.get("internships") else None)
        )
        mitra_name = ""
        position = ""
        if isinstance(internship, dict):
            mitra_name = (
                internship.get("company_name")
                or internship.get("mitra_name")
                or (internship.get("mitra") or {}).get("name")
                or (internship.get("company") or {}).get("name")
                or ""
            )
            position = (
                internship.get("position")
                or internship.get("posisi")
                or (internship.get("position") or {}).get("name")
                or ""
            )

        if not mitra_name and isinstance(raw.get("mitra"), dict):
            mitra_name = raw.get("mitra", {}).get("name", "")
        elif not mitra_name and isinstance(raw.get("mitra"), str):
            mitra_name = raw.get("mitra", "")
        elif not mitra_name and isinstance(raw.get("company"), dict):
            mitra_name = raw.get("company", {}).get("name", "")
        elif not mitra_name and isinstance(raw.get("company"), str):
            mitra_name = raw.get("company", "")

        return {
            "name": name,
            "photo_url": photo,
            "email": email,
            "phone": phone,
            "nik": nik,
            "mitra_name": mitra_name,
            "position": position,
            "raw": raw,
        }

    def _ensure_client(self):
        """Create the API client on first use."""
        if not self._client:
            token = get_access_token(self._username, self._password)
            self._client = ApiClient(token)

    @staticmethod
    def attendance_payload(
        date: str,
        latitude: float | str | None = None,
        longitude: float | str | None = None,
        location: str | None = None,
        activity_log: str | None = None,
        lesson_learned: str | None = None,
        obstacles: str | None = None,
    ) -> dict:
        """Build the attendance payload for a given date.

        Args:
            date: Date in YYYY-MM-DD format.
            latitude: Optional latitude override.
            longitude: Optional longitude override.
            location: Optional location name override.
            activity_log: Optional activity log override.
            lesson_learned: Optional lesson learned override.
            obstacles: Optional obstacles override.

        Returns:
            Payload that clock_in sends to the API.
        """
        raw_lat = latitude if latitude is not None else settings.latitude
        try:
            lat = float(raw_lat)
        except (ValueError, TypeError):
            lat = raw_lat

        raw_lon = longitude if longitude is not None else settings.longitude
        try:
            lon = float(raw_lon)
        except (ValueError, TypeError):
            lon = raw_lon

        loc = location if location is not None else settings.location
        act = activity_log if activity_log is not None else settings.activity_log
        les = lesson_learned if lesson_learned is not None else settings.lesson_learned
        obs = obstacles if obstacles is not None else settings.obstacles

        return {
            "date": date,
            "status": "PRESENT",
            "latitude": lat,
            "longitude": lon,
            "location": loc,
            "activity_log": act,
            "lesson_learned": les,
            "obstacles": obs,
        }

    def clock_in(self, date: str, payload_override: dict | None = None) -> dict:
        """Submit attendance (PRESENT) for a given date.

        Args:
            date: Date in YYYY-MM-DD format.
            payload_override: Optional explicit payload dictionary.

        Returns:
            JSON response from the API.
        """
        self._ensure_client()
        if payload_override:
            payload = payload_override
        else:
            payload = self.attendance_payload(
                date=date,
                latitude=self._latitude,
                longitude=self._longitude,
                location=self._location,
                activity_log=self._activity_log,
                lesson_learned=self._lesson_learned,
                obstacles=self._obstacles,
            )
        return self._client.post("/attendances/with-daily-log", payload)


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
