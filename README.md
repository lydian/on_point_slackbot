# Oncall Bot
Hi, I'm oncall bot, I can help you manage oncall operations. Here are all the available commands that you can trigger via: `@oncall-bot <COMMAND> [ARGS]`:
 - `help`: show help message
 - `set-pagerduty <pagerduty_id>`: configure pagerduty for this channel
 - `get-pagerduty [channel_name]`: query pagerduty for the specified channel if provided, otherwise query for the current channel
 - `set-sheet-url <google_sheet_url>`: configure google sheet for this channel
 - `get-sheet-url [channel_name]`: query google sheet for the specified channel if provided, otherwise query for the current channel
 - `log-url-to-google-sheet <start_time>`: log the start time to the google sheet
 - `mark-complete`: mark the main thread as complete
 - `unmark-complete`: unmark the main thread as complete
 - `ping <channel_name>`: ping oncall person for the specified channel
 - if none of the command matched, I will ping the oncall person for the current channel
