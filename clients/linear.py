import os
import httpx

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearClient:
    def __init__(self):
        self.api_key = os.environ["LINEAR_API_KEY"]
        self.team_id = os.environ["LINEAR_TEAM_ID"]
        self._headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }
        self._done_state_id = None  # cached after first fetch

    def _query(self, query, variables=None):
        resp = httpx.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables or {}},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise Exception(f"Linear API error: {data['errors']}")
        return data["data"]

    def get_open_issues(self):
        """Fetch open/in-progress issues for the team."""
        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                issues(
                    filter: { state: { type: { in: ["started", "unstarted", "backlog"] } } }
                    first: 100
                ) {
                    nodes {
                        id
                        identifier
                        title
                        description
                        url
                        state { name type }
                        assignee { name }
                        branchName
                    }
                }
            }
        }
        """
        data = self._query(query, {"teamId": self.team_id})
        return data["team"]["issues"]["nodes"]

    def _get_done_state_id(self):
        if self._done_state_id:
            return self._done_state_id
        data = self._query(
            "query($teamId: String!) { team(id: $teamId) { states { nodes { id type } } } }",
            {"teamId": self.team_id},
        )
        done = next(
            (s for s in data["team"]["states"]["nodes"] if s["type"] == "completed"),
            None,
        )
        if not done:
            raise Exception("No completed state found for team")
        self._done_state_id = done["id"]
        return self._done_state_id

    def close_issue(self, issue_id):
        state_id = self._get_done_state_id()
        self._query(
            "mutation($id: String!, $stateId: String!) { issueUpdate(id: $id, input: { stateId: $stateId }) { success } }",
            {"id": issue_id, "stateId": state_id},
        )

    def add_comment(self, issue_id, body):
        self._query(
            "mutation($issueId: String!, $body: String!) { commentCreate(input: { issueId: $issueId, body: $body }) { success } }",
            {"issueId": issue_id, "body": body},
        )

    def create_issue(self, title, description):
        data = self._query(
            """mutation($teamId: String!, $title: String!, $description: String!) {
                issueCreate(input: { teamId: $teamId, title: $title, description: $description }) {
                    success
                    issue { id identifier url }
                }
            }""",
            {"teamId": self.team_id, "title": title, "description": description},
        )
        return data["issueCreate"]["issue"]
