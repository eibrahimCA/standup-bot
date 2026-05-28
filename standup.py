#!/usr/bin/env python3
import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

import analyzer
from clients.github import GitHubClient
from clients.linear import LinearClient
from clients.slack import SlackClient


def main():
    parser = argparse.ArgumentParser(description="Post daily standup to Slack")
    parser.add_argument("--dry-run", action="store_true", help="Print Slack Block Kit JSON without posting")
    args = parser.parse_args()

    print("Fetching GitHub activity for yesterday...")
    github = GitHubClient()
    prs_by_author = github.get_yesterday_prs()

    if not prs_by_author:
        print("No merged PRs found for yesterday. Nothing to post.")
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
