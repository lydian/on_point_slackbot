from datetime import datetime, timedelta
from functools import cached_property
from typing import Dict, List

from pdpyras import APISession


class PagerDuty(object):

    def __init__(self, token: str):
        self.token = token

    @cached_property
    def session(self) -> APISession:
        return APISession(self.token)

    def get_oncall(self, schedule: str) -> List[Dict[str, str]]:
        since = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        until = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
        response = self.session.get(f"/schedules/{schedule}/users", params={"since": since, "until": until})
        users = [{"name": u["name"], "email": u["email"]} for u in response.json()["users"]]
        return users
