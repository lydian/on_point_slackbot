from datetime import datetime, timedelta, timezone
from typing import Dict, List

from pdpyras import APISession


class PagerDuty(object):

    def __init__(self, token: str):
        self.token = token

    @property
    def session(self) -> APISession:
        return APISession(self.token)

    def get_oncall(self, schedule: str) -> List[Dict[str, str]]:
        since = datetime.now(timezone.utc).isoformat()
        until = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        response = self.session.get(f"/schedules/{schedule}/users", params={"since": since, "until": until})
        users = [{"name": u["name"], "email": u["email"]} for u in response.json()["users"]]
        return users
