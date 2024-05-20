import re
from collections import namedtuple

from slack_bolt import App
from slack_sdk.errors import SlackApiError

from oncall_bot.config import load_config

_app = None

Context = namedtuple("Context", ["channel", "message_ts", "command_args", "thread_ts", "user"])


def get_app() -> App:
    global _app
    if _app is None:
        _app = App(
            token=load_config().slack_token,
            signing_secret=load_config().slack_signing_secret,
        )
    return _app


class SlackTool():

    def __init__(self, app: App, context: Context) -> None:
        self.context = context
        self.app = app

    @property
    def responser(self):
        def responser(text, markdown=False, **kwargs):
            self.app.client.chat_postMessage(
                channel=self.context.channel,
                thread_ts=self.context.message_ts,
                text=text,
                markdown=markdown,
                **kwargs
            )
        return responser

    @property
    def reaction_adder(self):
        def reaction_adder(ts, reaction_name):
            self.app.client.reactions_add(
                channel=self.context.channel,
                timestamp=ts,
                name=reaction_name,
            )
        return reaction_adder

    @property
    def reaction_remover(self):
        def reaction_remover(ts, reaction_name):
            self.app.client.reactions_remove(
                channel=self.context.channel,
                timestamp=ts,
                name=reaction_name,
            )
        return reaction_remover

    @property
    def get_thread_first_message(self):
        def get_thread_first_message(ts):
            return self.app.client.conversations_history(
                channel=self.context.channel,
                latest=ts,
                limit=1,
                inclusive=True
            )["messages"].pop()
        return get_thread_first_message

    @property
    def get_permalink(self):
        def get_permalink(ts):
            return self.app.client.chat_getPermalink(
                channel=self.context.channel,
                message_ts=ts,
            )["permalink"]
        return get_permalink

    @property
    def lookup_user(self):
        def lookup_user(email):
            return self.app.client.users_lookupByEmail(email=email)
        return lookup_user

    @property
    def parse_channel_str(self):
        def parse_channel_str(channel_str):
            match = re.match(r"<#(?P<channel_id>.*)\|(?P<channel_name>.*)>", channel_str)
            if match:
                return {"id": match.group("channel_id"), "name": match.group("channel_name")}
            else:
                return {"id": channel_str, "name": ""}
        return parse_channel_str

    @property
    def get_channel_topic(self):
        def get_channel_topic(channel_id):
            return self.app.client.conversations_info(
                channel=channel_id
            )["channel"]["topic"]["value"]
        return get_channel_topic

    @property
    def get_channel_name_from_channel_id(self):
        def get_channel_name_from_channel_id(channel_id):
            return "#" + self.app.client.conversations_info(
                channel=channel_id
            )["channel"]["name"].lstrip("#")
        return get_channel_name_from_channel_id

    @property
    def get_channel_bookmark(self):
        def get_channel_bookmark(channel_id):
            return self.app.client.conversations_info(
                channel=channel_id
            )["channel"]["topic"]["value"]
        return get_channel_bookmark

    @property
    def get_bookmarks(self):
        def get_bookmarks(channel):
            try:
                response = self.app.client.bookmarks_list(
                    channel_id=channel
                )
                return response["bookmarks"]
            except SlackApiError as e:
                print(e)
                return []
        return get_bookmarks

    @property
    def get_user_info(self):
        def get_user_info(user_id):
            print("get_user_info", user_id)
            return self.app.client.users_info(
                user=user_id
            ).data["user"]
        return get_user_info
