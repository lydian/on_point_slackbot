import json
from typing import Any, Dict, Optional

import jira

from oncall_bot.config import load_config


class Jira:

    def __init__(self, base_url: str, email: str, token: str) -> None:
        self.base_url = base_url
        if base_url.strip("/").endswith('.atlassian.net'):
            self.is_cloud = True
            kwargs = {
                'basic_auth': (email, token)
            }
        else:
            self.is_cloud = False
            kwargs = {
                'token_auth': token
            }
        self.client = jira.JIRA(
            server=base_url,
            **kwargs
        )

    def get_mention_name(self, email: str) -> Optional[str]:
        if self.is_cloud:
            users = self.client.search_users(query=email)
        else:
            users = self.client.search_users(email)
        if len(users) == 0:
            return None
        if hasattr(users[0], 'accountId'):
            return users[0].accountId
        return users[0].name

    def create_ticket(self,
        project: str,
        summary: str,
        description: str,
        issue_type: str,
        kwargs: Optional[Dict[str, Any]] = None
    ) -> str:
        kwargs = json.loads(kwargs) if kwargs and isinstance(kwargs, str) else {}

        issue = self.client.create_issue(
            project={"key": project},
            summary=summary,
            description=description,
            issuetype={'name': issue_type},
            **(kwargs or {})
        )
        return f"{self.base_url}/browse/{issue.key}"

    def escape_jira_markup(self, text: str) -> str:
        # List of JIRA markup characters that might need escaping
        markup_chars = ['*', '_', '{', '}', '[', ']', '(', ')', '|', '!', '^', '~', '?']
        # Escaping characters by adding a backslash before them
        for char in markup_chars:
            text = text.replace(char, f'\\{char}')
        return text


_jira = None

def get_jira_client() -> Jira:
    global _jira
    if _jira is None:
        jira_config = load_config().jira
        _jira = Jira(
            base_url=jira_config['base_url'],
            email=jira_config.get('email', None),
            token=jira_config['token']
        )
    return _jira
