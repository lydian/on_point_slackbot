import re
import shlex
import traceback
from collections import namedtuple
from typing import Any, Callable, Dict, List, Optional

import dateparser

from oncall_bot.config import load_config
from oncall_bot.gsheet import get_gsheet_storage
from oncall_bot.jira import get_jira_client
from oncall_bot.pagerduty import PagerDuty
from oncall_bot.slack_app import Context, SlackTool
from oncall_bot.tables import OncallInfo, get_tracking_table
from oncall_bot.utils import MinMaxValidator, get_key

Command = namedtuple("Command", ["func", "format", "help_text", "validator", "release"])


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
        if (
            get_key(body, "event.type") != "app_mention" and  f"<@{id}>" not in get_key(body, "event.text")
        ):
            print("not a mention_event")
            return

        command_str = get_key(body, "event.text").replace(f"<@{id}>", "").strip()
        command_str = command_str.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
        try:
            command_args = shlex.split(command_str)
        except ValueError:
            command_args = command_str.split()

        print(f"command args: {command_args}")
        main_command = command_args.pop(0).lower().strip() if len(command_args) > 0 else "__DEFAULT__"
        context = Context(
            channel=get_key(body, "event.channel"),
            message_ts=get_key(body, "event.ts"),
            command_args=command_args,
            thread_ts=get_key(body, "event.thread_ts"),
            user=get_key(body, "event.user"),
        )
        slack_tool = SlackTool(app, context)

        cmd = self.commands.get(main_command, self.commands["__DEFAULT__"])
        if cmd.validator is not None and cmd.validator(command_args) is not None:
            slack_tool.responser(cmd.validator(command_args))
            return
        try:
            cmd.func(context, slack_tool)
        except Exception as e:
            # print traceback
            traceback.print_exc()
            slack_tool.responser(f"Error: {str(e)}")

    def __repr__(self) -> str:
        return (
            "Hi, I'm oncall bot, I can help you to manage oncall schedule. "
            "Here are all the available commands:\n"
        ) + "\n".join([
            f" - `{cmd.format}`: {cmd.help_text}"
            for cmd in self.commands.values()
            if cmd.release
        ])

    @classmethod
    def update_channel_name(self, slack_tool: SlackTool, channel_id: str) -> None:
        try:
            channel_name = get_gsheet_storage().query_table(
                OncallInfo, channel_id,
                [OncallInfo.c.channel_name]
            )[OncallInfo.c.channel_name.name]
            new_channel_name = slack_tool.get_channel_name_from_channel_id(channel_id)
            if new_channel_name != channel_name:
                get_gsheet_storage().upsert_table(
                    OncallInfo, channel_id, {OncallInfo.c.channel_name.name: new_channel_name}
                )
        except Exception as e:
            print(f"Error: {str(e)}")


MentionedBot = _MentionedBot()


@MentionedBot.add_command(
    "help",
    format="help",
    help_text="show help message"
)
def help(context: Context, slack_tool: SlackTool):
    slack_tool.responser(str(MentionedBot), markdown=True)


@MentionedBot.add_command(
    "set-pagerduty",
    format="set-pagerduty <pagerduty_url>",
    help_text="configure pagerduty for this channel",
    validator=MinMaxValidator(1, 1)
)
def set_pagerduty(context: Context, slack_tool: SlackTool):
    pagerduty_url = context.command_args[0].strip('<> ')
    if not PagerDuty(load_config().pagerduty_token).parse_url(pagerduty_url):
        slack_tool.responser(
            "Please provide with pagerduty url, either `schedules`, `escalation_policies` or `service-directory`"
        )
        return
    get_gsheet_storage().upsert_table(OncallInfo, context.channel, {
        OncallInfo.c.pagerduty_url.name: pagerduty_url
    })
    MentionedBot.update_channel_name(slack_tool, context.channel)
    url = get_gsheet_storage().query_table(
        OncallInfo, context.channel, [OncallInfo.c.pagerduty_url]
    )[OncallInfo.c.pagerduty_url.name]

    slack_tool.responser(
        text=(
            f"Configured pagerduty: {url}.\n"
            "You can use `set-pagerduty` to update or "
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
    oncall_info = (
        get_gsheet_storage()
        .query_table(OncallInfo, query_channel, [OncallInfo.c.pagerduty_url])
    )
    pagerduty_url = oncall_info[OncallInfo.c.pagerduty_url.name] if oncall_info else None
    slack_tool.responser(
        text=(
            f"The pagerduty for this channel is `{pagerduty_url}`"
            if pagerduty_url else "No Settings Found. Please use `set-pagerduty PAGERDUTY_ID` to configure"
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
    logging_url = context.command_args[0].strip("<> ")
    print(f"logging url: {logging_url}")
    get_gsheet_storage().upsert_table(
        OncallInfo,
        context.channel,
        {OncallInfo.c.tracking_sheet.name: logging_url}
    )
    MentionedBot.update_channel_name(slack_tool, context.channel)
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
    logging_url = get_gsheet_storage().query_table(
        OncallInfo,
        query_channel,
        [OncallInfo.c.tracking_sheet]
    )
    if logging_url:
        logging_url = logging_url[OncallInfo.c.tracking_sheet.name]
    slack_tool.responser(
        text=(
            f"The logging google sheet url for this channel is `{logging_url}`"
            if logging_url else "No Settings Found. Please use `set-sheet-url GoogleSheetUrl` to configure"
        ),
        markdown=True
    )


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


def ping_oncall_person_for_channel(channel, slack_tool: SlackTool):
    pagerduty_urls = []

    # see if we have configured that
    row = get_gsheet_storage().query_table(OncallInfo, channel, [OncallInfo.c.pagerduty_url])
    if row:
        pagerduty_urls = [row[OncallInfo.c.pagerduty_url.name]]

    # # find pagerduty url from topic
    if len(pagerduty_urls) == 0:
        print("no schedule set in google sheet, try to find from topic")
        topic = slack_tool.get_channel_topic(channel)
        has_pagerduty_url = re.search(r"(?P<url>https://.*pagerduty.com/.*)", topic)
        if has_pagerduty_url:
            pagerduty_urls = [has_pagerduty_url.group("url")]

    # find from bookmarks
    if len(pagerduty_urls) == 0:
        pagerduty_urls = [
           bookmark.get("link", "") for bookmark in slack_tool.get_bookmarks(channel)
           if "pagerduty_url" in bookmark.get("link", "")
        ]

    print(f"pagerduty urls: {pagerduty_urls}")
    pd = PagerDuty(load_config().pagerduty_token)
    oncall_users = [
        oncall
        for pagerduty_url in pagerduty_urls
        for oncall in pd.get_oncall(pagerduty_url)
    ]

    print(f"pagerduty oncall users: {oncall_users}")
    oncall_pings = None
    if len(oncall_users) > 0:
        print(oncall_users)
        oncall_user_ids = list(filter(
            lambda x: x is not None,
            [get_key(slack_tool.lookup_user(user["email"]), "user.id") for user in oncall_users]
        ))
        print(f"oncall_user_ids: {list(oncall_user_ids)}")
        oncall_pings = " ".join(f"<@{user_id}>" for user_id in oncall_user_ids)

    if oncall_pings is None:
        # find oncall user from topic
        topic = slack_tool.get_channel_topic(channel)
        found_oncall_user_from_topic = re.search(r":pagerduty: <@(?P<oncall_user>.*)>", topic)
        if found_oncall_user_from_topic:
            oncall_pings = f"<@{found_oncall_user_from_topic.group('oncall_user')}>"

    if oncall_pings:
        text = f"{oncall_pings} please take a look on the request."
    elif len(pagerduty_urls) == 0:
        text = "Sorry, the channel doesn't have pagerduty id configured."
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
    "join",
    format="join <channel_name>",
    help_text="join the specified channel",
)
def join_channel(context: Context, slack_tool: SlackTool):
    channel = slack_tool.parse_channel_str(context.command_args[0].strip())["id"]
    slack_tool.join_channel(channel)
    slack_tool.responser("joined channel")

@MentionedBot.add_command(
    "summary",
    format="summary <channel_name> <start_time> <end_time>",
    help_text="get the summary of the oncall for the specified channel",
    validator=MinMaxValidator(2, 3)
)
def summary(context: Context, slack_tool: SlackTool):
    print(f"command args: {context.command_args}")
    channel = (
        slack_tool.parse_channel_str(context.command_args[0].strip())["id"]
        if len(context.command_args) == 3 else context.channel
    )
    start_time = dateparser.parse(context.command_args[1] if len(context.command_args) == 3 else context.command_args[0])
    end_time = dateparser.parse(context.command_args[2] if len(context.command_args) == 3 else context.command_args[1])
    print(f"channel: {channel}, start_time: {start_time}, end_time: {end_time}")
    oncall_info = get_gsheet_storage().query_table(
        OncallInfo,
        channel,
        [OncallInfo.c.pagerduty_url, OncallInfo.c.tracking_sheet]
    )
    print(f"oncall info: {oncall_info}")
    summary_text = []
    if oncall_info:
        pagerduty_url = oncall_info[OncallInfo.c.pagerduty_url.name]
        summary = PagerDuty(load_config().pagerduty_token).get_summary_from_schedule(pagerduty_url, start_time, end_time)
        if summary:
            summary_text.append(f"*### Pagerduty Summary ###*")
            summary_text.append(f"Total Pages: {summary['total_pages']}")
            summary_text.append(f"Weekend Pages: {summary['weekend_pages']}")
            summary_text.append(f"Out of Business Hour Pages: {summary['out_of_hours_pages']}")
            summary_text.append("")
            summary_text.append("*#### Pages Count ####*:")
            for title, count in summary["group_by_titles"]:
                summary_text.append(f"{title}: {count}")
            summary_text.append("")

    if (oncall_info or {}).get("tracking_sheet"):
        tracking_url = oncall_info["tracking_sheet"]
        summary = get_gsheet_storage().get_summary(tracking_url, start_time, end_time)
        if summary:
            summary_text.append(f"*### Request Summary ###*")
            summary_text.append(f"Total Requests: {summary['total_requests']}")
            summary_text.append(f"Total PR Requests: {summary['total_PR_reuqests']}")
            summary_text.append(f"Total Support Requests: {summary['total_support_reuqests']}")
            summary_text.append(f"Unresolved Requests: {len(summary['unresolved_requests'])}")
            summary_text.append("")
            summary_text.append("*#### Unresolved Requests ####*:")
            for request in summary["unresolved_requests"]:
                summary_text.append(f"<{request['slack_url']}|{request['subject']}> (from {request['requested_team']})")

    print(f"summary text: {summary_text}")
    if summary_text:
        slack_tool.responser('\n'.join(summary_text), markdown=True, reply_broadcast=True)


@MentionedBot.add_command(
    "set-jira-project",
    format="set-jira-project [channel] <project> <issue_type> <metadata>",
    help_text="configure jira project for this channel",
    validator=MinMaxValidator(3, 4)
)
def set_jira_project(context: Context, slack_tool: SlackTool):
    channel = (
        context.channel
        if len(context.command_args) == 3
        else slack_tool.parse_channel_str(context.command_args.pop(0))["id"]
    )

    project, issue_type, metadata = context.command_args
    get_gsheet_storage().upsert_table(
        OncallInfo,
        channel,
        {
            OncallInfo.c.jira_project.name: project,
            OncallInfo.c.jira_issue_type.name: issue_type,
            OncallInfo.c.jira_metadata.name: metadata
        }
    )
    MentionedBot.update_channel_name(slack_tool, channel)
    slack_tool.responser(
        text=(
            "Configure done, you can use `set-jira-project` to update or "
            "use `get-jira-project` to query the current settings"
        ),
        markdown=True,
    )


@MentionedBot.add_command(
    "get-jira-project",
    format="get-jira-project [channel_name]",
    help_text="query jira project for the specified channel if provided, otherwise query for the current channel",
    validator=MinMaxValidator(0, 1)
)
def get_jira_project(context: Context, slack_tool: SlackTool):
    query_channel = (
        context.channel
        if len(context.command_args) == 0
        else slack_tool.parse_channel_str(context.command_args[0])["id"]
    )
    jira_project = get_gsheet_storage().query_table(
        OncallInfo,
        query_channel,
        [
            OncallInfo.c.jira_project,
            OncallInfo.c.jira_issue_type,
            OncallInfo.c.jira_metadata
        ]
    )
    if jira_project:
        jira_project = (
            jira_project[OncallInfo.c.jira_project.name],
            jira_project[OncallInfo.c.jira_issue_type.name],
            jira_project[OncallInfo.c.jira_metadata.name]
        )
    slack_tool.responser(
        text=(
            f"The jira project for this channel is `{jira_project}`"
            if jira_project else "No Settings Found. Please use `set-jira-project` to configure"
        ),
        markdown=True
    )


@MentionedBot.add_command(
    "create-ticket",
    format="create-ticket <summary> <description>",
    help_text="create a ticket in jira using the first message in thread as description",
)
def create_ticket(context: Context, slack_tool: SlackTool):
    jira = get_jira_client()
    project = get_gsheet_storage().query_table(
        OncallInfo,
        context.channel,
        [
            OncallInfo.c.jira_project,
            OncallInfo.c.jira_issue_type,
            OncallInfo.c.jira_metadata,
        ])
    if not project:
        raise ValueError("No Jira Project Configured")

    def slack_user_to_jira_mention(user_id: str) -> str:
        slack_user = slack_tool.get_user_info(user_id)
        if not slack_user:
            return user_id
        jira_user = jira.get_mention_name(get_key(slack_user, "profile.email"))
        if not jira_user:
            return get_key(slack_user, "name")
        return f"[~{jira_user}]"

    project_key = project[OncallInfo.c.jira_project.name]
    issue_type = project[OncallInfo.c.jira_issue_type.name]
    ticket_metadata = project[OncallInfo.c.jira_metadata.name]
    summary = context.command_args[0]
    first_message = slack_tool.get_thread_first_message(context.thread_ts)["text"]
    first_message_url = slack_tool.get_permalink(context.thread_ts)
    replaced_text = re.sub(
        r"<@(?P<user_id>.*?)>",
        lambda x: slack_user_to_jira_mention(x.group("user_id")),
        first_message
    )

    description = context.command_args[1] +  "\n\n\n\n"
    description += "=== Ticket Details ===\n\n"
    description += "ticket created by " + slack_user_to_jira_mention(context.user) + "\n\n"
    description += "Original Message:\n"
    description += f"[slack|{first_message_url}]\n"
    description += "{noformat}" + replaced_text + "{noformat}"

    ticket = jira.create_ticket(project_key, summary, description, issue_type, ticket_metadata)
    slack_tool.responser(f"Ticket created: {ticket}")


@MentionedBot.add_command(
    "__DEFAULT__",
    format="",
    help_text="if none of the command matched, we will ping the oncall person for the current channel"
)
def default_ping(context: Context, slack_tool: SlackTool):
    print(f"ping channel: {context.channel}")
    ping_oncall_person_for_channel(context.channel, slack_tool)



@MentionedBot.add_command("test", format="test", help_text="test command")
def test(context: Context, slack_tool: SlackTool):
    pass
