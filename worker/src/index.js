const LINEAR_API_URL = "https://api.linear.app/graphql";

async function verifySlackSignature(request, body, env) {
  const timestamp = request.headers.get("x-slack-request-timestamp");
  const slackSig = request.headers.get("x-slack-signature");
  if (!timestamp || !slackSig) return false;

  // Reject stale requests (replay protection)
  if (Math.abs(Date.now() / 1000 - parseInt(timestamp)) > 300) return false;

  const sigBase = `v0:${timestamp}:${body}`;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(env.SLACK_SIGNING_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(sigBase));
  const computed = "v0=" + Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, "0")).join("");
  return computed === slackSig;
}

async function linearQuery(query, variables, apiKey) {
  const resp = await fetch(LINEAR_API_URL, {
    method: "POST",
    headers: { "Authorization": apiKey, "Content-Type": "application/json" },
    body: JSON.stringify({ query, variables }),
  });
  const data = await resp.json();
  if (data.errors) throw new Error(JSON.stringify(data.errors));
  return data.data;
}

async function getDoneStateId(env) {
  const data = await linearQuery(
    `query($teamId: String!) { team(id: $teamId) { states { nodes { id type } } } }`,
    { teamId: env.LINEAR_TEAM_ID },
    env.LINEAR_API_KEY
  );
  const done = data.team.states.nodes.find(s => s.type === "completed");
  if (!done) throw new Error("No completed state found for this Linear team");
  return done.id;
}

async function handleCloseIssue(issueId, env) {
  const stateId = await getDoneStateId(env);
  await linearQuery(
    `mutation($id: String!, $stateId: String!) { issueUpdate(id: $id, input: { stateId: $stateId }) { success } }`,
    { id: issueId, stateId },
    env.LINEAR_API_KEY
  );
  return "Issue marked as Done.";
}

async function handleDocumentAssignment(value, env) {
  const { issue_id, pr_url, pr_number } = JSON.parse(value);
  const body = `Linked to PR #${pr_number}: ${pr_url}`;
  await linearQuery(
    `mutation($issueId: String!, $body: String!) { commentCreate(input: { issueId: $issueId, body: $body }) { success } }`,
    { issueId: issue_id, body },
    env.LINEAR_API_KEY
  );
  return `PR #${pr_number} documented on issue.`;
}

async function handleCreateIssue(value, env) {
  const { title, description, pr_url } = JSON.parse(value);
  const fullDescription = `${description}\n\nOriginated from: ${pr_url}`;
  const data = await linearQuery(
    `mutation($teamId: String!, $title: String!, $description: String!) {
      issueCreate(input: { teamId: $teamId, title: $title, description: $description }) {
        success
        issue { identifier url }
      }
    }`,
    { teamId: env.LINEAR_TEAM_ID, title, description: fullDescription },
    env.LINEAR_API_KEY
  );
  const issue = data.issueCreate.issue;
  return `Created ${issue.identifier}: ${issue.url}`;
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const body = await request.text();

    if (!(await verifySlackSignature(request, body, env))) {
      return new Response("Unauthorized", { status: 401 });
    }

    const payload = JSON.parse(new URLSearchParams(body).get("payload"));
    const action = payload.actions?.[0];
    if (!action) return new Response("No action", { status: 400 });

    let message;
    try {
      switch (action.action_id) {
        case "close_issue":
          message = await handleCloseIssue(action.value, env);
          break;
        case "document_assignment":
          message = await handleDocumentAssignment(action.value, env);
          break;
        case "create_issue":
          message = await handleCreateIssue(action.value, env);
          break;
        default:
          message = `Unknown action: ${action.action_id}`;
      }
    } catch (e) {
      return new Response(JSON.stringify({ text: `Error: ${e.message}` }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ text: message }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  },
};
