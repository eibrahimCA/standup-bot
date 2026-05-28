import json
import os
from datetime import date

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClient:
    def __init__(self):
        self.client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
        self.channel = os.environ["SLACK_CHANNEL_ID"]

    def build_blocks(self, summaries_by_author, linear_actions):
        today = date.today().strftime("%B %-d, %Y")
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"Daily Standup — {today}"}},
            {"type": "divider"},
        ]

        for author, bullets in summaries_by_author.items():
            bullet_text = "\n".join(f"• {b}" for b in bullets)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*:bust_in_silhouette: {author}*\n{bullet_text}"},
            })

        has_linear = any(linear_actions.get(k) for k in ("suggested_closures", "in_progress_matches", "missing_issues"))
        if has_linear:
            blocks += [
                {"type": "divider"},
                {"type": "header", "text": {"type": "plain_text", "text": "Linear — Action Items"}},
            ]

            if linear_actions.get("suggested_closures"):
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Ready to close:*"}})
                for item in linear_actions["suggested_closures"]:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"<{item['issue_url']}|{item['identifier']}> {item['title']}  →  <{item['pr_url']}|PR #{item['pr_number']}>",
                        },
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Close Issue ✓"},
                            "style": "primary",
                            "action_id": "close_issue",
                            "value": item["issue_id"],
                        },
                    })

            if linear_actions.get("in_progress_matches"):
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*In progress:*"}})
                for item in linear_actions["in_progress_matches"]:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"<{item['issue_url']}|{item['identifier']}> {item['title']}  →  <{item['pr_url']}|PR #{item['pr_number']}>",
                        },
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Document Assignment"},
                            "action_id": "document_assignment",
                            "value": json.dumps({
                                "issue_id": item["issue_id"],
                                "pr_url": item["pr_url"],
                                "pr_number": item["pr_number"],
                            }),
                        },
                    })

            if linear_actions.get("missing_issues"):
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*No issue found — suggested new issues:*"}})
                for item in linear_actions["missing_issues"]:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"<{item['pr_url']}|PR #{item['pr_number']}> — _{item['suggested_title']}_",
                        },
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Create Issue"},
                            "action_id": "create_issue",
                            "value": json.dumps({
                                "title": item["suggested_title"],
                                "description": item["suggested_description"],
                                "pr_url": item["pr_url"],
                            }),
                        },
                    })

        return blocks

    def post(self, blocks):
        try:
            self.client.chat_postMessage(channel=self.channel, blocks=blocks, text="Daily Standup")
        except SlackApiError as e:
            raise Exception(f"Slack API error: {e.response['error']}")
