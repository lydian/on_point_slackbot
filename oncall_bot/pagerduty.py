import re
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
from itertools import groupby
from typing import Any, Dict, List

from pdpyras import APISession

from oncall_bot.utils import get_key


class PagerDuty(object):

    def __init__(self, token: str):
        self.token = token

    @property
    def session(self) -> APISession:
        return APISession(self.token)

    def parse_url(self, url: str) -> Dict[str, str]:
        match = re.match(
            r"https://.*pagerduty.com/(?P<type>(schedules|escalation_policies|service-directory))[/#]?(?P<pagerduty_id>.*)", url
        )
        if not match:
            print(f"Invalid PagerDuty URL: {url}")
            return {}
        return match.groupdict()

    def get_oncall(self, pagerduty_url: str) -> List[Dict[str, str]]:
        match = self.parse_url(pagerduty_url)

        if match["type"] == "schedules":
            return self.get_oncall_from_schedule(match["pagerduty_id"])
        elif match["type"] == "escalation_policies":
            return self.get_oncall_from_escalation_policy(match["pagerduty_id"])
        elif match["type"] == "service-directory":
            return self.get_oncall_from_service(match["pagerduty_id"])
        return []

    def get_oncall_from_schedule(self, schedule: str) -> List[Dict[str, str]]:
        since = datetime.now(timezone.utc).isoformat()
        until = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        response = self.session.get(f"/schedules/{schedule}/users", params={"since": since, "until": until})
        users = [{"name": u["name"], "email": u["email"], "time_zone": u["time_zone"]} for u in response.json()["users"]]
        return users

    def get_oncall_from_escalation_policy(self, policy: str) -> List[Dict[str, str]]:
        response = self.session.get(f"/escalation_policies/{policy}")
        first = get_key(response.json(),"escalation_policy.escalation_rules", [None])[0]
        if first is None:
            return []
        users = []
        for target in first["targets"]:
            if target["type"] == "schedule_reference":
                users.extend(self.get_oncall(target["id"]))
        return users

    def get_oncall_from_service(self, service_id: str) -> List[Dict[str, str]]:
        response = self.session.get(f"/services/{service_id}")
        escalion_policy_id = get_key(response.json(), "service.escalation_policy.id", None)
        if escalion_policy_id:
            return self.get_oncall_from_escalation_policy(escalion_policy_id)
        return []

    def get_summary_from_schedule(self, schedule_url: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        match = self.parse_url(schedule_url)
        if match["type"] != "schedules":
            return {}
        schedule_id = match["pagerduty_id"]
        schedule = self.session.get(f"/schedules/{schedule_id}").json()
        print(schedule)
        team_ids = [team["id"] for team in schedule["schedule"]["teams"]]
        oncall_user = self.get_oncall_from_schedule(schedule_id)[0]
        incidents = []
        offset = 0

        while True:
            r = self.session.get(
                f"/incidents",
                params={
                    "team_ids": team_ids,
                    "since": start_time.isoformat(),
                    "until": end_time.isoformat(),
                    "offset": offset,
                    "time_zone": oncall_user["time_zone"],
                }
            )
            incidents.extend(r.json()["incidents"])
            offset = len(incidents)
            if not r.json()["more"]:
                break

        for incident in incidents:
            incident["created_at"] = datetime.fromisoformat(incident["created_at"])

        summary = OrderedDict()
        summary["total_pages"] = len(incidents)
        summary["oncall"] = oncall_user
        # group by incident title
        summary["group_by_titles"] = sorted(
            Counter([incident["title"] for incident in incidents]).items(),
            key=lambda x: x[1], reverse=True
        )

        summary["weekend_pages"] = len([
            incident
            for incident in incidents
            if incident["created_at"].weekday() in [5, 6]
        ])

        summary["out_of_hours_pages"] = len([
            incident
            for incident in incidents
            if (
                incident["created_at"].weekday() not in [5, 6]
                and (
                   incident["created_at"].hour < 9
                    or incident["created_at"].hour > 18
                )

            )
        ])


        return summary
