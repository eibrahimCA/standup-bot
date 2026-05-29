#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

import analyzer
from clients.github import GitHubClient
from clients.linear import LinearClient
from clients.slack import SlackClient

STANDUP_HOUR = 6  # 6am — must match your crontab


def get_standup_window():
    """Return (since, until) covering all work since the last weekday standup at STANDUP_HOUR."""
    now = datetime.now(timezone.utc)
    local_now = datetime.now()  # local time for day-of-week check
    weekday = local_now.weekday()  # 0=Mon, 4=Fri

    # On Monday, look back to Friday 6am (skip the weekend).
    # On Tue–Fri, look back to the previous weekday at 6am.
    days_back = 3 if weekday == 0 else 1

    since_local = (local_now - timedelta(days=days_back)).replace(
        hour=STANDUP_HOUR, minute=0, second=0, microsecond=0
    )
    # Convert local since to UTC for GitHub API comparison
    utc_offset = now - datetime.now(timezone.utc).replace(tzinfo=None)  # approx local→UTC delta
    since_utc = since_local.replace(tzinfo=timezone.utc) - utc_offset
    until_utc = now

    return since_utc, until_utc


def main():
    parser = argparse.ArgumentParser(description="Post daily standup to Slack")
    parser.add_argument("--dry-run", action="store_true", help="Print Slack Block Kit JSON without posting")
    args = parser.parse_args()

    since, until = get_standup_window()
    since_label = since.strftime("%a %b %-d %-I:%M%p")
    print(f"Fetching GitHub activity since {since_label}...")

    github = GitHubClient()
    prs_by_author = github.get_prs_since(since, until)

    if not prs_by_author:
        print(f"No merged PRs found since {since_label}. Nothing to post.")
        sys.exit(0)

    print(f"Found PRs from {len(prs_by_author)} author(s): {', '.join(prs_by_author)}")

    print("Analyzing diffs with AI...")
    summaries_by_author = {}
    for author, prs in prs_by_author.items():
        print(f"  Summarizing {len(prs)} PR(s) for {author}...")
        summaries_by_author[author] = analyzer.summarize_author_prs(author, prs)

    linear_actions = {"suggested_closures": [], "in_progress_matches": [], "missing_issues": []}
    try:
        print("Fetching Linear issues...")
        linear = LinearClient()
        linear_issues = linear.get_open_issues()
        print(f"  Found {len(linear_issues)} open issue(s)")

        print("Cross-referencing PRs with Linear issues...")
        linear_actions = analyzer.cross_reference(prs_by_author, linear_issues)
    except KeyError:
        print("  Linear env vars not set — skipping Linear section")
    except Exception as e:
        print(f"  Warning: Linear step failed: {e}")

    print("Building Slack message...")
    slack = SlackClient()
    blocks = slack.build_blocks(summaries_by_author, linear_actions)

    if args.dry_run:
        print("\n--- Slack Block Kit JSON (dry run, not posted) ---")
        print(json.dumps(blocks, indent=2))
        print("--- End ---")
    else:
        print("Posting to Slack...")
        slack.post(blocks)
        print("Done!")


if __name__ == "__main__":
    main()
