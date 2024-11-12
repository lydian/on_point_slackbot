from slack_bolt.adapter.socket_mode import SocketModeHandler

from oncall_bot.config import load_config
from oncall_bot.log_request_workflow_step import oncall_ws_step
from oncall_bot.mention_bot import MentionedBot
from oncall_bot.slack_app import get_app

slack_app = get_app()

# Add workflow step
slack_app.step(oncall_ws_step)

# Allow bot interacts with mentioned events
@slack_app.event("app_mention")
def handle_app_mention_events(body):
    print("app_mention", )
    self_id = slack_app.client.auth_test()['user_id']
    MentionedBot.process_command(self_id, slack_app, body)

@slack_app.event("message")
def handle_im(body):
    # self_id = slack_app.client.auth_test()['user_id']
    # print(body)
    # MentionedBot.process_command(self_id, slack_app, body)
    pass



if __name__ == "__main__":
    handler = SocketModeHandler(slack_app, load_config().slack_socket_app_token)
    handler.start()
