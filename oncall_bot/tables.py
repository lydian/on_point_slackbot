from sqlalchemy import JSON, Column, DateTime, MetaData, String, Table

metadata = MetaData()

OncallInfo = Table(
    "oncall_info",
    MetaData(),
    Column("channel_id", String(), primary_key=True),
    Column("pagerduty_url", String()),
    Column("channel_name", String()),
    Column("tracking_sheet", String()),
)


def get_tracking_table(url: str) -> Table:
    return Table(
        url,
        MetaData(),
        Column("slack_url", String(), primary_key=True),
        Column("requested_at", DateTime()),
        Column("completed_at", DateTime()),
        Column("requested_by", String()),
        Column("requested_team", String()),
        Column("subject", String()),
        Column("request_content", String()),
        Column("metadata", JSON()),
        Column("classification", String()),
        Column("note", String()),
        Column("feedback_written_by", String()),
    )
