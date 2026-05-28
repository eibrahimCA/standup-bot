import os
from datetime import datetime, timedelta, timezone
from github import Github
import httpx


class GitHubClient:
    def __init__(self):
        self.token = os.environ["GITHUB_TOKEN"]
        self.gh = Github(self.token)
        self.org = os.environ["GITHUB_ORG"]
        self.repos = [r.strip() for r in os.environ["GITHUB_REPOS"].split(",")]

    def get_yesterday_prs(self):
        """Return {author_login: [pr_data, ...]} for PRs merged yesterday."""
        tz = timezone.utc
        now = datetime.now(tz)
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_start.replace(hour=23, minute=59, second=59)

        prs_by_author = {}

        for repo_name in self.repos:
            full_name = f"{self.org}/{repo_name}"
            try:
                repo = self.gh.get_repo(full_name)
            except Exception as e:
                print(f"  Warning: could not access {full_name}: {e}")
                continue

            for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
                if pr.merged_at is None:
                    continue
                if pr.merged_at < yesterday_start:
                    break
                if pr.merged_at > yesterday_end:
                    continue

                author = pr.user.login
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "url": pr.html_url,
                    "branch": pr.head.ref,
                    "body": pr.body or "",
                    "diff": self._fetch_diff(full_name, pr.number),
                    "repo": repo_name,
                }
                prs_by_author.setdefault(author, []).append(pr_data)

        return prs_by_author

    def _fetch_diff(self, full_name, pr_number):
        url = f"https://api.github.com/repos/{full_name}/pulls/{pr_number}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3.diff",
        }
        try:
            resp = httpx.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            diff = resp.text
            if len(diff) > 50_000:
                diff = diff[:50_000] + "\n... [diff truncated at 50k chars]"
            return diff
        except Exception as e:
            return f"[could not fetch diff: {e}]"
