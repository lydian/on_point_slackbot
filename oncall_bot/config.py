import os
from dataclasses import dataclass, field
from functools import lru_cache, partial
from typing import Callable, Optional, Type, TypeVar

import yaml
from dotenv import load_dotenv


def from_env(env_name: str) -> Callable[[], str]:
    return partial(os.getenv, env_name)


@dataclass
class Config(object):
    slack_token: str = field(default_factory=from_env('SLACK_TOKEN'))
    slack_signing_secret: str = field(default_factory=from_env('SLACK_SIGNING_SECRET'))
    slack_socket_app_token: Optional[str] = field(default_factory=from_env('SLACK_SOCKET_APP_TOKEN'))
    pagerduty_token: str = field(default_factory=from_env('PAGERDUTY_TOKEN'))



@lru_cache(1)
def load_config(config_path: Optional[str]=None) -> Config:
    # Trye to configure env if .env exists
    BASEDIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    load_dotenv(os.path.join(BASEDIR, ".env"), verbose=False)

    config = {}
    # Load from config_path
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as fp:
            config = yaml.load(fp)

    return Config(**config)
