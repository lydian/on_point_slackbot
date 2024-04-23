# Oncall Bot
Hi, I'm oncall bot, I can help you to manage oncall schedule. Here are all the available commands:
 - `help`: show help message
 - `set-pagerduty <pagerduty_url>`: configure pagerduty for this channel
 - `get-pagerduty [channel_name]`: query pagerduty for the specified channel if provided, otherwise query for the current channel
 - `set-sheet-url <google_sheet_url>`: configure google sheet for this channel
 - `get-sheet-url [channel_name]`: query google sheet for the specified channel if provided, otherwise query for the current channel
 - `mark-complete`: mark the main thread as complete
 - `unmark-complete`: unmark the main thread as complete
 - `ping <channel_name>`: ping oncall person for the specified channel
 - `join <channel_name>`: join the specified channel
 - `summary <channel_name> <start_time> <end_time>`: get the summary of the oncall for the specified channel
 - `set-jira-project [channel] <project> <issue_type> <metadata>`: configure jira project for this channel
 - `get-jira-project [channel_name]`: query jira project for the specified channel if provided, otherwise query for the current channel
 - `create-ticket <summary> <description>`: create a ticket in jira using the first message in thread as description
 - ``: if none of the command matched, we will ping the oncall person for the current channel
 - `test`: test command
