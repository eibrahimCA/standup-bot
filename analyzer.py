import json
import os

import litellm

SYSTEM_PROMPT = (
    "You are a technical writer generating daily standup notes for a software team. "
    "Write in plain English focused on business impact and intent, not implementation details or line counts. "
    "Be concise. Respond only with valid JSON — no markdown fences, no explanation outside the JSON."
)


def _call_ai(messages):
    model = os.environ.get("AI_MODEL", "gpt-4o-mini")
    resp = litellm.completion(model=model, messages=messages, temperature=0.3)
    return resp.choices[0].message.content.strip()


def _parse_json(raw, fallback):
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return fallback


def summarize_author_prs(author, prs):
    """Return a list of 2-4 plain-English bullet strings for what the author accomplished."""
    pr_blocks = []
    for pr in prs:
        pr_blocks.append(
            f"PR #{pr['number']} ({pr['repo']}): {pr['title']}\n"
            f"Branch: {pr['branch']}\n\n"
            f"Diff (first 8k chars):\n{pr['diff'][:8000]}"
        )

    combined = "\n\n---\n\n".join(pr_blocks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Analyze these pull requests merged by {author} yesterday and write 2-4 bullet points "
                "summarizing what they accomplished. Focus on what changed and why it matters, not how.\n\n"
                f"{combined}\n\n"
                'Return JSON: {"bullets": ["...", "..."]}'
            ),
        },
    ]
    result = _parse_json(_call_ai(messages), None)
    if result and "bullets" in result:
        return result["bullets"]
    return [f"Worked on {len(prs)} PR(s): {', '.join(p['title'] for p in prs)}"]


def cross_reference(prs_by_author, linear_issues):
    """
    Match PRs to Linear issues.
    Returns:
      {
        suggested_closures:   [{issue_id, identifier, title, issue_url, pr_number, pr_url}],
        in_progress_matches:  [{issue_id, identifier, title, issue_url, pr_number, pr_url}],
        missing_issues:       [{pr_number, pr_url, suggested_title, suggested_description}],
      }
    """
    empty = {"suggested_closures": [], "in_progress_matches": [], "missing_issues": []}

    all_prs = [
        {"number": pr["number"], "title": pr["title"], "branch": pr["branch"], "url": pr["url"], "repo": pr["repo"]}
        for prs in prs_by_author.values()
        for pr in prs
    ]

    if not all_prs or not linear_issues:
        return empty

    issues_payload = json.dumps([
        {
            "id": i["id"],
            "identifier": i["identifier"],
            "title": i["title"],
            "url": i["url"],
            "state": i["state"]["name"],
            "branchName": i.get("branchName") or "",
        }
        for i in linear_issues
    ], indent=2)

    prs_payload = json.dumps(all_prs, indent=2)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Cross-reference these pull requests with the Linear issues.\n\n"
                f"PRs merged yesterday:\n{prs_payload}\n\n"
                f"Open Linear issues:\n{issues_payload}\n\n"
                "Return a JSON object with exactly three keys:\n"
                "- suggested_closures: PRs that appear to fully resolve a Linear issue\n"
                "- in_progress_matches: PRs actively working on a Linear issue (work not yet complete)\n"
                "- missing_issues: PRs with no matching Linear issue (include a suggested title and description for a new issue)\n\n"
                "Schema:\n"
                '{"suggested_closures": [{"issue_id":"...","identifier":"...","title":"...","issue_url":"...","pr_number":0,"pr_url":"..."}],'
                '"in_progress_matches": [{"issue_id":"...","identifier":"...","title":"...","issue_url":"...","pr_number":0,"pr_url":"..."}],'
                '"missing_issues": [{"pr_number":0,"pr_url":"...","suggested_title":"...","suggested_description":"..."}]}'
            ),
        },
    ]

    result = _parse_json(_call_ai(messages), empty)
    for key in ("suggested_closures", "in_progress_matches", "missing_issues"):
        result.setdefault(key, [])
    return result
