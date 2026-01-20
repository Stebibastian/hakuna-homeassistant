"""API client for Hakuna Time Tracking."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class HakunaApiError(Exception):
    """Exception for Hakuna API errors."""


class HakunaAuthError(HakunaApiError):
    """Exception for authentication errors."""


class HakunaRateLimitError(HakunaApiError):
    """Exception for rate limit errors."""


class HakunaApiClient:
    """API client for Hakuna."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_token: str,
        company: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._api_token = api_token
        self._company = company
        self._headers = {
            "X-Auth-Token": api_token,
            "Accept-Version": "v1",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        """Make a request to the API."""
        url = f"{API_BASE_URL}{endpoint}"

        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                params=params,
                json=json_data,
            ) as response:
                if response.status == 401:
                    raise HakunaAuthError("Invalid API token")
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "unknown")
                    raise HakunaRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after} seconds"
                    )
                if response.status == 404:
                    # Timer not running returns 404
                    return None
                if response.status >= 400:
                    text = await response.text()
                    raise HakunaApiError(
                        f"API error {response.status}: {text}"
                    )

                if response.status == 204:
                    return None

                return await response.json()

        except aiohttp.ClientError as err:
            raise HakunaApiError(f"Connection error: {err}") from err

    # ==================== Timer Endpoints ====================

    async def get_timer(self) -> dict[str, Any] | None:
        """Get the current timer status.

        Returns None if no timer is running.
        Returns timer data if a timer is running:
        {
            "date": "2016-11-08",
            "start_time": "19:00",
            "duration": "02:16",
            "duration_in_seconds": 8138,
            "note": "Did a lot of work.",
            "user": {...},
            "task": {...},
            "project": {...}
        }
        """
        result = await self._request("GET", "/timer")
        # API returns 200 with date=null when no timer is running
        if result and result.get("date") is None:
            return None
        return result

    async def start_timer(
        self,
        task_id: int | None = None,
        project_id: int | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Start a new timer."""
        data = {}
        if task_id is not None:
            data["task_id"] = task_id
        if project_id is not None:
            data["project_id"] = project_id
        if note is not None:
            data["note"] = note

        return await self._request("POST", "/timer", json_data=data if data else None)

    async def stop_timer(self) -> dict[str, Any]:
        """Stop the running timer and create a time entry."""
        return await self._request("PUT", "/timer")

    async def cancel_timer(self) -> None:
        """Cancel/delete the running timer without creating a time entry."""
        await self._request("DELETE", "/timer")

    # ==================== Overview Endpoint ====================

    async def get_overview(self, user_id: int | None = None) -> dict[str, Any]:
        """Get overview with overtime and vacation info.
        
        Returns:
        {
            "overtime": "470:30",
            "overtime_in_seconds": 1693800,
            "vacation": {
                "redeemed_days": 21.5,
                "remaining_days": 3.5
            }
        }
        """
        params = {}
        if user_id is not None:
            params["user_id"] = user_id
        return await self._request("GET", "/overview", params=params if params else None)

    # ==================== Time Entries Endpoints ====================

    async def get_time_entries(
        self,
        start_date: date | str,
        end_date: date | str | None = None,
        user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get time entries for a date range."""
        if isinstance(start_date, date):
            start_date = start_date.isoformat()
        if end_date is None:
            end_date = start_date
        elif isinstance(end_date, date):
            end_date = end_date.isoformat()

        params = {
            "start_date": start_date,
            "end_date": end_date,
        }
        if user_id is not None:
            params["user_id"] = user_id

        result = await self._request("GET", "/time_entries", params=params)
        return result if result else []

    async def get_time_entry(self, entry_id: int) -> dict[str, Any]:
        """Get a single time entry by ID."""
        return await self._request("GET", f"/time_entries/{entry_id}")

    # ==================== Absences Endpoints ====================

    async def get_absences(
        self, year: int | None = None, user_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get absences for a year."""
        params = {}
        if year is not None:
            params["year"] = year
        else:
            params["year"] = datetime.now().year
        if user_id is not None:
            params["user_id"] = user_id

        result = await self._request("GET", "/absences", params=params)
        return result if result else []

    # ==================== Users & Presence Endpoints ====================

    async def get_users(self) -> list[dict[str, Any]]:
        """Get list of users you can manage."""
        result = await self._request("GET", "/users")
        return result if result else []

    async def get_presence(self) -> list[dict[str, Any]]:
        """Get today's presence/absence information for all users.
        
        Returns:
        [
            {
                "user": {"id": 1, "name": "...", "status": "active", "groups": [...]},
                "absent_first_half_day": false,
                "absent_second_half_day": false,
                "has_timer_running": true
            },
            ...
        ]
        """
        result = await self._request("GET", "/presence")
        return result if result else []

    # ==================== Projects & Tasks Endpoints ====================

    async def get_projects(self) -> list[dict[str, Any]]:
        """Get list of all projects."""
        result = await self._request("GET", "/projects")
        return result if result else []

    async def get_tasks(self) -> list[dict[str, Any]]:
        """Get list of all tasks."""
        result = await self._request("GET", "/tasks")
        return result if result else []

    # ==================== Company Info ====================

    async def get_company(self) -> dict[str, Any]:
        """Get company information."""
        return await self._request("GET", "/company")

    async def get_absence_types(self) -> list[dict[str, Any]]:
        """Get list of absence types."""
        result = await self._request("GET", "/absence_types")
        return result if result else []

    # ==================== Ping / Health Check ====================

    async def ping(self) -> dict[str, Any]:
        """Ping the API to check connectivity."""
        return await self._request("GET", "/ping")

    # ==================== Helper Methods ====================

    async def is_timer_running(self) -> bool:
        """Check if a timer is currently running."""
        timer = await self.get_timer()
        return timer is not None

    async def get_users_with_open_time_entries(
        self, older_than_days: int = 7
    ) -> list[dict[str, Any]]:
        """Get users with time entries older than specified days without end time.
        
        This requires supervisor/admin permissions.
        """
        users_with_issues = []
        
        try:
            users = await self.get_users()
            
            from datetime import timedelta
            cutoff_date = date.today() - timedelta(days=older_than_days)
            start_date = cutoff_date - timedelta(days=30)  # Look back 30 days
            
            for user in users:
                user_id = user.get("id")
                entries = await self.get_time_entries(
                    start_date=start_date,
                    end_date=cutoff_date,
                    user_id=user_id,
                )
                
                # Check for entries without proper end time or duration issues
                for entry in entries:
                    entry_date = entry.get("date")
                    if entry_date and entry_date < cutoff_date.isoformat():
                        # Entry is older than cutoff
                        if entry.get("duration_in_seconds", 0) == 0:
                            users_with_issues.append({
                                "user": user,
                                "entry": entry,
                                "issue": "zero_duration",
                            })
                            break
                            
        except HakunaApiError as err:
            _LOGGER.warning("Could not check for open time entries: %s", err)
            
        return users_with_issues
