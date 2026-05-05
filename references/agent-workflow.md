Use this reference when the goal is to launch one HexArena bot reliably.

Operator model:

- the LLM is the operator
- the Python bot process is the player
- join exactly one seat
- launch exactly one bot
- do not spawn helper bots
- do not fill seats

Required working directory for this unreleased local project:

```bash
cd /home/talvasconcelos/Work/lnbits_pg/lnbits/extensions/hexarena
```

Bootstrap the local workspace:

```bash
python3 agentkit/bootstrap_workspace.py --target .hexarena
```

Refresh an existing workspace:

```bash
python3 agentkit/bootstrap_workspace.py --target .hexarena --force
```

Default command to join one free run and launch one bot in the background:

```bash
python3 .hexarena/scripts/play_with_bot.py \
  --base-url http://127.0.0.1:5000 \
  --display-name my-agent \
  --strategy aggressive
```

Target a specific game template:

```bash
python3 .hexarena/scripts/play_with_bot.py \
  --base-url http://127.0.0.1:5000 \
  --display-name my-agent \
  --strategy aggressive \
  --game-id GAME_ID
```

Target a specific waiting run:

```bash
python3 .hexarena/scripts/play_with_bot.py \
  --base-url http://127.0.0.1:5000 \
  --display-name my-agent \
  --strategy aggressive \
  --run-id RUN_ID
```

What `play_with_bot.py` does:

1. chooses a waiting free run unless `--run-id` points somewhere else
2. joins once
3. refuses payment-required joins by default
4. launches `runtime_bot.py` in the background
5. prints one JSON object describing:
   - selected run
   - join result
   - launch mode
   - bot pid
   - log file

Artifacts created in `.hexarena/`:

- `runs/<run_id>.json`
- `logs/<run_id>-<agent_id>.log`

Success criteria:

- the command prints one `join_result` JSON object
- `join.agent_id` exists
- `join.api_key` exists
- `launch.mode == "background"`
- `launch.pid` exists

If the run is still `waiting` after join:

- this is not an error
- the background bot keeps polling and waits for the run to start
- the operator should report that the bot is running and the run is waiting for more players

Do not speculate about missing config files, venv activation, or generic bot frameworks.
The supported local flow is the exact command sequence above.
