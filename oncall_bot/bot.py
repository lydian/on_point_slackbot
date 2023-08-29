import re
from collections import namedtuple
from typing import Any, Callable, Dict, List, Optional

from slack_bolt import App

from oncall_bot.config import load_config
from oncall_bot.google_sheet import GoogleSheet
from oncall_bot.pagerduty import PagerDuty
from oncall_bot.utils import MinMaxValidator, get_key

Command = namedtuple("Command", ["func", "format", "help_text", "validator", "release"])
Context = namedtuple("Context", ["channel", "message_ts", "command_args", "thread_ts"])


class SlackTool():

    def __init__(self, app: App, context: Context) -> None:
        self.context = context
        self.app = app

    @property
    def responser(self):
        def responser(text, markdown=False):
            self.app.client.chat_postMessage(
                channel=self.context.channel,
                thread_ts=self.context.message_ts,
                text=text,
                markdown=markdown,
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
    def get_channel_title(self):
        def get_channel_title(channel_id):
            return self.app.client.conversations_info(
                channel=channel_id
            )["channel"]["name"]
        return get_channel_title


class _MentionedBot():

    commands: Dict[str, Any] = {}

    # Make a decorator to register commands
    def add_command(
            self,
            command_name: str,
            format: str = "",
            help_text: str = "",
            validator: Optional[Callable[[List[str]], Optional[str]]] = None,
            release: bool = True
    ):
        def decorator(func):
            self.commands[command_name] = Command(func, format, help_text, validator, release)
            return func
        return decorator

    @classmethod
    def process_command(self, id, app, body: Dict[Any, Any]):
        command_args = get_key(body, "event.text").replace(f"<@{id}>", "").strip().split(" ")
        main_command = command_args.pop(0).lower().strip()
        context = Context(
            channel=get_key(body, "event.channel"),
            message_ts=get_key(body, "event.ts"),
            command_args=command_args,
            thread_ts=get_key(body, "event.thread_ts"),
        )
        slack_tool = SlackTool(app, context)

        cmd = self.commands.get(main_command, self.commands["__DEFAULT__"])
        if cmd.validator is not None and cmd.validator(command_args) is not None:
            slack_tool.responser(cmd.validator(command_args))
            return
        cmd.func(context, slack_tool)

    def __repr__(self) -> str:
        return (
            "Hi, I'm oncall bot, I can help you to manage oncall schedule. "
            "Here are all the available commands:\n"
        ) + "\n".join([
            f" - `{cmd.format}`: {cmd.help_text}"
            for cmd in self.commands.values()
            if cmd.release
        ])


MentionedBot = _MentionedBot()


@MentionedBot.add_command(
    "set-pagerduty",
    format="set-pagerduty <pagerduty_id>",
    help_text="configure pagerduty for this channel",
    validator=MinMaxValidator(1, 1)
)
def set_pagerduty(context: Context, slack_tool: SlackTool):
    pagerduty_schedule_id = context.command_args[0].strip()
    GoogleSheet.from_oncall_settings().add_or_update_pagerduty_schedule(context.channel, pagerduty_schedule_id)
    slack_tool.responser(
        text=(
            "Configure done, you can use `set-pagerduty` to update or "
            "use `get-pagerduty` to query the current settings"
        ),
        markdown=True,
    )


@MentionedBot.add_command(
    "get-pagerduty",
    format="get-pagerduty [channel_name]",
    help_text="query pagerduty for the specified channel if provided, otherwise query for the current channel",
    validator=MinMaxValidator(0, 1)
)
def get_pagerduty(context: Context, slack_tool: SlackTool):
    query_channel = (
        context.channel
        if len(context.command_args) == 0
        else slack_tool.parse_channel_str(context.command_args[0])["id"]
    )
    print(query_channel)
    pagerduty_schedule_id = GoogleSheet.from_oncall_settings().find_pagerduty_schedule(query_channel)
    slack_tool.responser(
        text=(
            f"The pagerduty for this channel is `{pagerduty_schedule_id}`"
            if pagerduty_schedule_id else "No Settings Found. Please use `set-pagerduty PAGERDUTY_ID` to configure"
        ),
        markdown=True
    )


@MentionedBot.add_command(
    "set-sheet-url",
    format="set-sheet-url <google_sheet_url>",
    help_text="configure google sheet for this channel",
    validator=MinMaxValidator(1, 1)
)
def set_sheet_url(context: Context, slack_tool: SlackTool):
    logging_url = context.command_args[0].strip()
    GoogleSheet.from_oncall_settings().add_or_update_tracking_sheet(context.channel, logging_url)
    slack_tool.responser(
        text=(
            "Configure done, you can use `set-sheet-url` to update or "
            "use `get-sheet-url` to query the current settings"
        ),
        markdown=True,
    )


@MentionedBot.add_command(
    "get-sheet-url",
    format="get-sheet-url [channel_name]",
    help_text="query google sheet for the specified channel if provided, otherwise query for the current channel",
    validator=MinMaxValidator(0, 1)
)
def get_sheet_url(context: Context, slack_tool: SlackTool):
    query_channel = (
        context.channel
        if len(context.command_args) == 0
        else slack_tool.parse_channel_str(context.command_args[0])["id"]
    )
    logging_url = GoogleSheet.from_oncall_settings().find_oncall_tracking_sheet(query_channel)
    slack_tool.responser(
        text=(
            f"The logging google sheet url for this channel is `{logging_url}`"
            if logging_url else "No Settings Found. Please use `set-sheet-url GoogleSheetUrl` to configure"
        ),
        markdown=True
    )


@MentionedBot.add_command(
    "log-url-to-google-sheet",
    format="log-url-to-google-sheet <start_time>",
    help_text="log the start time to the google sheet",
    validator=MinMaxValidator(min=1)
)
def log_url_to_google_sheet(context: Context, slack_tool: SlackTool):
    # get the first message
    query_value = " ".join(context.command_args)
    conversation = slack_tool.get_thread_first_message(context.thread_ts)
    main_thread_url = slack_tool.get_permalink(conversation["ts"])
    logging_url = GoogleSheet.from_oncall_settings().find_oncall_tracking_sheet(context.channel)
    if logging_url:
        try:
            GoogleSheet.from_url(logging_url).update_tracking_log("start time", query_value, main_thread_url)
            slack_tool.reaction_adder(context.message_ts, "white_check_mark")
        except ValueError as e:
            slack_tool.responser(
                text=str(e),
                markdown=True
            )
    else:
        slack_tool.responser("No tracking sheet found")


@MentionedBot.add_command(
    "mark-complete",
    format="mark-complete",
    help_text="mark the main thread as complete"
)
def mark_complete(context: Context, slack_tool: SlackTool):
    conversation = slack_tool.get_thread_first_message(context.thread_ts)
    slack_tool.reaction_adder(conversation["ts"], "white_check_mark")


@MentionedBot.add_command(
    "unmark-complete",
    format="unmark-complete",
    help_text="unmark the main thread as complete"
)
def unmark_complete(context: Context, slack_tool: SlackTool):
    conversation = slack_tool.get_thread_first_message(context.thread_ts)
    slack_tool.reaction_remover(conversation["ts"], "white_check_mark")


@MentionedBot.add_command(
    "help",
    format="help",
    help_text="show help message"
)
def help(context: Context, slack_tool: SlackTool):
    slack_tool.responser(str(MentionedBot), markdown=True)


def ping_oncall_person_for_channel(channel, slack_tool: SlackTool):
    pagerduty_schedule_id = GoogleSheet.from_oncall_settings().find_pagerduty_schedule(channel)
    print(f"pagerduty schedule id: {pagerduty_schedule_id}")
    oncall_users = (
        PagerDuty(load_config().pagerduty_token).get_oncall(pagerduty_schedule_id)
        if pagerduty_schedule_id else []
    )
    print(f"pagerduty oncall users: {oncall_users}")
    if not pagerduty_schedule_id:
        text = "Sorry, the channel doesn't have pagerduty id configured."
    elif len(oncall_users) > 0:
        oncall_user_ids = list(filter(
            lambda x: x is not None,
            [get_key(slack_tool.lookup_user(user["email"]), "user.id") for user in oncall_users]
        ))
        print(f"oncall_user_ids: {list(oncall_user_ids)}")
        oncall_pings = " ".join(f"<@{user_id}>" for user_id in oncall_user_ids)
        text = f"{oncall_pings} please take a look on the request."
    else:
        text = "There are no oncall right now. Please ping on the time there's oncall. Thanks"
    slack_tool.responser(text)


@MentionedBot.add_command(
    "ping",
    format="ping <channel_name>",
    help_text="ping oncall person for the specified channel",
    validator=MinMaxValidator(1, 1)
)
def ping_oncall(context: Context, slack_tool: SlackTool):
    channel = slack_tool.parse_channel_str(context.command_args[0].strip())["id"]
    ping_oncall_person_for_channel(channel, slack_tool)


@MentionedBot.add_command(
    "__DEFAULT__",
    format="",
    help_text="if none of the command matched, we will ping the oncall person for the current channel"
)
def default_ping(context: Context, slack_tool: SlackTool):
    print(f"ping channel: {context.channel}")
    ping_oncall_person_for_channel(context.channel, slack_tool)


@MentionedBot.add_command(
    "test",
    format="test",
    help_text="mark the main thread as complete",
    release=False
)
def test(context: Context, slack_tool: SlackTool):
    channel = slack_tool.parse_channel_str(context.command_args[0].strip())["id"]
    slack_tool.responser(slack_tool.get_channel_title(channel))
