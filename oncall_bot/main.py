import json
from typing import Any

import requests
from slack_bolt import Ack, App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.workflows.step import Complete, Configure, Update, WorkflowStep

from oncall_bot.bot import MentionedBot
from oncall_bot.config import load_config
from oncall_bot.pagerduty import PagerDuty
from oncall_bot.utils import get_key

app = App(
    token=load_config().slack_token,
    signing_secret=load_config().slack_signing_secret,
)

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
            "block_id": "pagerduty_schedule_id",
            "element": {
                "type": "plain_text_input",
                "action_id": "pagerduty_schedule_id",
                "multiline": False,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Add pagerduty schedule id",
                    "emoji": False
                },
                "initial_value": get_key(step, "inputs.pagerduty_schedule_id.value", "")
            },
            "label": {
                "type": "plain_text",
                "text": "Pagerduty Schedule Id",
                "emoji": False
            }
        },
        {
            "type": "input",
            "block_id": "message_format",
            "element": {
                "type": "plain_text_input",
                "action_id": "message_format",
                "multiline": True,
                "placeholder": {"type": "plain_text", "text": "The request message to post in channel"},
                "initial_value": get_key(step, "inputs.message_format.value", "")
            },
            "label": {"type": "plain_text", "text": "Request Message Format"},
        },
        {
            "type": "section",
            "block_id": "feedback_channel",
            "text": {
                "type": "mrkdwn",
                "text": "Pick a Channel to response to the completed request"
            },
            "accessory": {
                "action_id": "feedback_channel",
                "type": "conversations_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select a channel to post message",
                },
            }
        },
        {
            "type": "input",
            "block_id": "feedback_workflow_url",
            "optional": True,
            "element": {
                "type": "url_text_input",
                "action_id": "feedback_workflow_url",
            },
            "label": {"type": "plain_text", "text": "Feedback workflow"},
        },
    ]

    # Configure initial value
    support_channel = get_key(step, "inputs.support_channel.value")
    if support_channel:
        blocks[0]["accessory"]["initial_conversation"] = support_channel
    feedback_channel = get_key(step, "inputs.feedback_channel.value")
    if support_channel:
        blocks[3]["accessory"]["initial_conversation"] = feedback_channel
    feedback_workflow_url = get_key(step, "inputs.feedback_workflow_url.value")
    if feedback_workflow_url:
        blocks[4]["element"]["initial_value"] = feedback_workflow_url

    configure(blocks=blocks)


@oncall_ws_step.save
def save(ack: Ack, view: Any, update: Update, logger: Any) -> None:
    ack()

    values = view["state"]["values"]
    logger.debug(view)
    inputs = {
        "support_channel": {"value": values["support_channel"]["support_channel"]["selected_conversation"]},
        "feedback_channel": {"value": values["feedback_channel"]["feedback_channel"]["selected_conversation"]},
        "pagerduty_schedule_id": {"value": values["pagerduty_schedule_id"]["pagerduty_schedule_id"]["value"]},
        "message_format": {"value": values["message_format"]["message_format"]["value"]},
        "feedback_workflow_url": {"value": values["feedback_workflow_url"]["feedback_workflow_url"]["value"]},
    }
    outputs = [
        {
            "type": "text",
            "name": "oncall_users",
            "label": "Oncall Users",
        },
        {
            "type": "text",
            "name": "message_ts",
            "label": "Message ID",
        },
        {
            "type": "text",
            "name": "message_link",
            "label": "Link to the request message",
        }
    ]
    update(inputs=inputs, outputs=outputs)


@oncall_ws_step.execute
def execute(step: Any, complete: Complete, logger: Any) -> None:
    logger.debug(step)
    inputs = step["inputs"]
    support_channel = inputs["support_channel"]["value"]
    feedback_channel = inputs["feedback_channel"]["value"]
    pagerduty_schedule_id = inputs["pagerduty_schedule_id"]["value"]
    feedback_workflow_url = inputs["feedback_workflow_url"]["value"]

    # Post Question
    main_message = app.client.chat_postMessage(
        channel=support_channel,
        text=inputs["message_format"]["value"],
        mrkdwn=True
    )
    main_message_url = app.client.chat_getPermalink(channel=support_channel, message_ts=main_message["ts"])
    # Ping OnCall
    oncall_users = PagerDuty(load_config().pagerduty_token).get_oncall(pagerduty_schedule_id)
    oncall_user_ids = filter(
        lambda x: x is not None,
        [get_key(app.client.users_lookupByEmail(email=user["email"]), "user.id") for user in oncall_users]
    )
    oncall_pings = " ".join(f"<@{user_id}>" for user_id in oncall_user_ids)
    oncall_response = {
        "text": f"{oncall_pings} please take a look on the request.",
        "attachments": [
            {
                "fallback": "Please click complete when done",
                "callback_id": "complete",
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": [
                    {
                        "name": "completed",
                        "text": "Completed",
                        "type": "button",
                        "value": json.dumps({
                            "support_channel": support_channel,
                            "feedback_channel": feedback_channel,
                            "ts": main_message["ts"],
                            "oncall": oncall_pings,
                            "message_url": main_message_url["permalink"],
                            "feedback_workflow_url": feedback_workflow_url,
                        })
                    }
                ]
            }
        ]
    }
    app.client.chat_postMessage(
        channel=support_channel,
        thread_ts=main_message["ts"],
        **oncall_response
    )

    # if everything was successful
    outputs = {
        "message_ts": main_message["ts"],
        "oncall_users": oncall_pings,
        "message_link": main_message_url["permalink"],
    }
    complete(outputs=outputs)


app.step(oncall_ws_step)


@app.action("complete")
def handle_oncall_complete_action(ack: Ack, body: Any, logger: Any) -> None:
    ack()
    logger.debug(body)

    data = json.loads(get_key(body, 'actions.0.value'))
    try:
        app.client.reactions_add(channel=data["support_channel"], name="white_check_mark", timestamp=data["ts"])
    except Exception as e:
        logger.error(e)

    url = data["message_url"]
    r = requests.post(
        data["feedback_workflow_url"],
        json={
            "subject": "test-subject",
            "message_url": url
        }
    )
    logger.info(r.text)
    app.client.chat_update(
        channel=get_key(body, "channel.id"),
        text=f"_{get_key(body, 'user.name')}_ marked the issue completed",
        ts=get_key(body, "message_ts"),
        markdown=True,
        attachments=[]

    )


@app.event("app_mention")
def handle_app_mention_events(body):
    self_id = app.client.auth_test()['user_id']
    MentionedBot.process_command(self_id, app, body)


if __name__ == "__main__":
    handler = SocketModeHandler(app, load_config().slack_socket_app_token)
    handler.start()
