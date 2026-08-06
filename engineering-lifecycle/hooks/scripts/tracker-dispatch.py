#!/usr/bin/env python3
"""Ask the model to file queued issues, at most once per queue state.

This is the one hook in the plugin that deliberately speaks on Stop, and it exists
against the grain of a decision this repository already paid for. Every other Stop
hook here is silent, `render_hook` returns None for `stop-completion-check`, and
`hygiene-stop-check.py` is a no-op carrying the reason:

    Any stdout here is injected back into the conversation as context and
    re-invokes the model, producing an endless "(Standing by.)" loop.

That loop was not caused by speaking on Stop. It was caused by speaking on Stop
*unconditionally and statelessly* - the model replies, stops again, the hook fires
again with nothing changed, and says the same thing forever.

So the question is not whether to block, it is whether the block can be made to
happen at most once for a given state of the world. It can, with three independent
brakes, any one of which alone terminates the loop:

  1. Empty queue exits silently.
     Nothing to say means nothing is said. This is also what keeps
     `test_stop_hook_stays_silent` passing verbatim - that test runs against an
     empty temp workspace, so this hook never reaches the printing branch.

  2. The content token. PRIMARY.
     A hash of the pending queue. The model saying "filed" and stopping again
     produces the SAME token, so the second Stop cannot block. Only a genuinely
     different queue can.

  3. A per-session cap.
     One block per session, full stop, whatever the tokens say.

A fourth brake, `stop_hook_active` in the payload, is checked opportunistically. It
is NOT in the documented Stop-hook input schema, so the design must be - and is -
correct without it. If the harness supplies it, it is free extra safety.

State is written BEFORE anything is printed, so a crash between the two fails
closed: the token is recorded, and the next Stop sees it and stays quiet.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import load_hook_payload, read_json_safe, repo_root, workspace_exists, write_json  # noqa: E402

MAX_BLOCKS_PER_SESSION = 1


def _queue_token(pending: list[dict]) -> str:
    """Identity of a queue state. Same pending set, same token, no second block."""
    payload = "|".join(sorted(f"{item.get('id')}:{item.get('hash', '')}" for item in pending))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    root = repo_root()

    # Brake 0: the sentinel, checked before any JSON is parsed, so it still works
    # when settings.json is malformed.
    from tracker import (
        SEVERITIES,
        disabled_path,
        is_disabled,
        load_queue,
        load_settings,
        state_path,
    )

    if is_disabled(root) or not workspace_exists(root):
        return 0

    payload = load_hook_payload()
    # Brake 4 (opportunistic): the harness telling us this Stop was itself caused
    # by a stop hook. Undocumented, so never relied upon.
    if payload.get("stop_hook_active"):
        return 0

    try:
        settings = load_settings(root)
    except Exception:
        return 0
    dispatch = settings.get("dispatch", {}) or {}
    if not settings.get("enabled") or not dispatch.get("on_stop"):
        return 0
    if settings.get("enforcement") == "off":
        return 0

    minimum = dispatch.get("min_severity", "medium")
    order = {name: index for index, name in enumerate(SEVERITIES)}
    pending = [
        issue
        for issue in load_queue(root)["issues"]
        if issue.get("status") == "queued" and order.get(issue.get("severity", "medium"), 99) <= order.get(minimum, 99)
    ]
    # Brake 1: nothing pending, nothing said.
    if not pending:
        return 0

    token = _queue_token(pending)
    state = read_json_safe(state_path(root))
    # Brake 2: this exact queue has already been raised once.
    if state.get("last_block_token") == token:
        return 0
    # Brake 3: hard cap, regardless of tokens.
    if int(state.get("blocks_this_session", 0)) >= MAX_BLOCKS_PER_SESSION:
        return 0

    from eng_common import now_iso

    session = payload.get("session_id")
    if session and state.get("session_id") != session:
        # A genuinely new session resets the cap; the token still guards repeats.
        state["blocks_this_session"] = 0
    state.update(
        {
            "last_block_token": token,
            "last_block_at": now_iso(),
            "blocks_this_session": int(state.get("blocks_this_session", 0)) + 1,
            "session_id": session,
        }
    )
    # Written before printing, so a crash in between fails closed.
    write_json(state_path(root), state)

    capped = pending[: int(dispatch.get("max_per_turn", 10))]
    listed = "".join(f"\n  - [{item['severity']}] {item['title']}" for item in capped)
    more = f"\n  ...and {len(pending) - len(capped)} more." if len(pending) > len(capped) else ""
    reason = (
        f"{len(pending)} surfaced issue(s) have not been filed in {settings.get('provider')}:"
        f"{listed}{more}\n\n"
        'Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/surface-issue.py" plan`, execute the '
        "operations it returns against the tracker's MCP tools, then `reconcile` with the "
        "returned ids.\n\n"
        "If filing is not wanted right now, say so and stop again - this will not ask twice "
        f"for the same queue. To switch it off entirely: `eng-life tracker off` (creates "
        f"{disabled_path(root).name})."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
