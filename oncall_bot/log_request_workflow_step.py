import uuid
from typing import Any

from slack_bolt import Ack
from slack_bolt.workflows.step import Complete, Configure, Update, WorkflowStep

from oncall_bot.gsheet import get_gsheet_storage
from oncall_bot.tables import OncallInfo, get_tracking_table
from oncall_bot.utils import get_key

oncall_ws_step = WorkflowStep.builder("post_request_and_ping_oncall")


@oncall_ws_step.edit
def edit(ack: Ack, step: Any, configure: Configure, logger: Any) -> None:
    ack()
    logger.debug(step)
    blocks = [
        {
            "type": "section",
            "block_id": "support_channel",
            "text": {
                "type": "mrkdwn",
                "text": "Pick a Channel to post the request message"
            },
            "accessory": {
                "action_id": "support_channel",
                "type": "conversations_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select a channel to post message"
                },
                "default_to_current_conversation": True,
            }
        },
        {
            "type": "input",
            "block_id": "json_content",
            "element": {
                "type": "plain_text_input",
                "action_id": "json_content",
                "multiline": True,
                "placeholder": {"type": "plain_text", "text": "The content to log in JSON format"},
                "initial_value": get_key(step, "inputs.json_content.value", "")
            },
            "label": {"type": "plain_text", "text": "the data to log in JSON format"},
        },
    ]

    # Configure initial value
    support_channel = get_key(step, "inputs.support_channel.value")
    if support_channel:
        blocks[0]["accessory"]["initial_conversation"] = support_channel
    configure(blocks=blocks)


@oncall_ws_step.save
def save(ack: Ack, view: Any, update: Update, logger: Any) -> None:
    ack()

    values = view["state"]["values"]
    logger.debug(view)
    inputs = {
        "support_channel": {"value": values["support_channel"]["support_channel"]["selected_conversation"]},
        "json_content": {"value": values["json_content"]["json_content"]["value"]},
    }
    outputs = [
        {
            "type": "text",
            "name": "request_uuid",
            "label": "Request UUID",
        },
    ]
    update(inputs=inputs, outputs=outputs)


@oncall_ws_step.execute
def execute(step: Any, complete: Complete, logger: Any) -> None:
    logger.debug(step)
    inputs = step["inputs"]
    support_channel = inputs["support_channel"]["value"]
    json_content = inputs["json_content"]["value"]

    tracking_url = get_gsheet_storage().query_table(OncallInfo, support_channel, ["tracking_url"])["tracking_url"]
    tracking_table = get_tracking_table(tracking_url)
    log_id = uuid.uuid4().hex
    get_gsheet_storage().upsert_table(tracking_table, log_id, json_content)

    # if everything was successful
    outputs = {
        "request_uuid": log_id,
    }
    complete(outputs=outputs)
