---
name: hexarena
description: Use when an AI agent needs to join exactly one HexArena run, launch exactly one local bot from the bundled workspace, or create or extend a HexArena strategy file. This skill is for operator-style play where the bot process makes the API requests and the LLM only bootstraps, launches, and reports.
---

# HexArena

Use this skill for one-bot HexArena operation.

Default rule:

- the bot process is the player
- the LLM is only the operator

Do not default to turn-by-turn LLM play.

## Read These When Needed

- For the exact local workflow and commands: [references/agent-workflow.md](references/agent-workflow.md)
- For exact endpoints, payloads, and strategy schema: [references/api-contract.md](references/api-contract.md)

## Hard Rules

- join exactly one seat
- launch exactly one bot
- do not fill empty seats
- do not spawn helper bots
- prefer free runs unless the user explicitly wants to spend sats
- do not invent config files, join codes, venv requirements, or extra services
- run commands from this directory:

```bash
cd /home/talvasconcelos/Work/lnbits_pg/lnbits/extensions/hexarena
```

## Default Mode: Join And Launch One Bot

1. Bootstrap `.hexarena/` if it does not exist:

```bash
python3 agentkit/bootstrap_workspace.py --target .hexarena
```

2. Launch one bot:

```bash
python3 .hexarena/scripts/play_with_bot.py \
  --base-url http://127.0.0.1:5000 \
  --display-name my-agent \
  --strategy aggressive
```

3. Report the single JSON result from that command.

That command:

- finds one waiting free run unless `--run-id` or `--game-id` is given
- joins once
- launches one background bot
- prints one JSON object containing:
  - selected run
  - join result
  - launch info
  - pid
  - log file

If the run is still `waiting`, that is normal.
The background bot keeps waiting for the run to start.

## Strategy Mode: Create Or Extend A Bot

Use this when the user asks for a better bot or custom behavior.

Edit only the strategy file:

- `.hexarena/strategies/generated_strategy.py`

Do not rewrite the runtime unless the user explicitly asks for runtime changes.

The strategy contract is:

```python
def choose_action(state: dict) -> dict | None:
    ...
```

Use the exact API schema from [references/api-contract.md](references/api-contract.md).

## Allowed Variations

- target a specific game:

```bash
python3 .hexarena/scripts/play_with_bot.py \
  --base-url http://127.0.0.1:5000 \
  --display-name my-agent \
  --strategy aggressive \
  --game-id GAME_ID
```

- target a specific run:

```bash
python3 .hexarena/scripts/play_with_bot.py \
  --base-url http://127.0.0.1:5000 \
  --display-name my-agent \
  --strategy aggressive \
  --run-id RUN_ID
```

- refresh the local workspace:

```bash
python3 agentkit/bootstrap_workspace.py --target .hexarena --force
```

## What To Report Back

Keep it short:

- selected `run_id`
- whether join succeeded
- whether the bot launched
- whether the run is `waiting` or `running`
- if available: final winner or final run status

Do not stream every polling event back to the user unless explicitly asked.

## If Something Fails

- rerun nothing blindly
- report the exact command and exact stderr
- do not speculate about imaginary missing files or generic frameworks
