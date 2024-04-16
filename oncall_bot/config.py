import os
from dataclasses import dataclass, field
from functools import lru_cache, partial
from typing import Callable, Dict, Optional, Type, TypeVar

import yaml
from dotenv import load_dotenv


def from_env(env_name: str) -> Callable[[], str]:
    return partial(os.getenv, env_name)


@dataclass
class Config(object):
    slack_token: str = field(default_factory=from_env("SLACK_TOKEN"))
    slack_signing_secret: str = field(default_factory=from_env("SLACK_SIGNING_SECRET"))
    slack_socket_app_token: Optional[str] = field(default_factory=from_env("SLACK_SOCKET_APP_TOKEN"))
    pagerduty_token: str = field(default_factory=from_env("PAGERDUTY_TOKEN"))
    google_sheet_service_account: Dict[str, str] = field(default_factory=from_env("GOOGLE_SHEET_SERVICE_ACCOUNT"))
    google_sheet_root_db: str = field(default_factory=from_env("GOOGLE_SHEET_ROOT_DB"))
    google_sheet_root_id: str = field(default_factory=from_env("GOOGLE_SHEET_ROOT_ID"))
    jira_api_token: str = field(default_factory=from_env("JIRA_API_TOKEN"))

@lru_cache(1)
def load_config() -> Config:
    # Try to configure env if .env exists
    BASEDIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    load_dotenv(os.path.join(BASEDIR, ".env"), verbose=False)

    config = {}
    # Load from config_path
    config_path = os.getenv("CONFIG_PATH", None)
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as fp:
            config = yaml.safe_load(fp.read())

    return Config(**config)
