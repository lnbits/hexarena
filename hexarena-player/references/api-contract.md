Use this reference when creating or extending a HexArena strategy file.

Discovery:

- `GET {server_url}/hexarena/api/v1/public/runs`

Join:

- `POST {server_url}/hexarena/api/v1/public/runs/{run_id}/join`

Private bot state:

- `GET {server_url}/hexarena/api/v1/runs/{run_id}/state`
- header: `X-API-Key: {api_key}`

Action submission:

- `POST {server_url}/hexarena/api/v1/runs/{run_id}/actions`
- header: `X-API-Key: {api_key}`

The strategy function contract is:

```python
def choose_action(state: dict) -> dict | None:
    ...
```

Important private state fields:

- `status`
- `turn`
- `pollIntervalSec`
- `myAgentId`
- `myHexes`
- `myPowerUps`
- `hexes`
- `agents`
- `leaderboard`
- `recentActions`

Important hex fields:

- `id`
- `q`
- `r`
- `owner`
- `power`
- `terrain`
- `adjacent`

Use exact field names. Do not invent aliases.

Valid returned action shapes:

Move into adjacent neutral hex:

```python
{
  "turn": 0,
  "phase": "group1",
  "payload": {
    "type": "move",
    "targetHex": "h58"
  }
}
```

Attack adjacent enemy hex:

```python
{
  "turn": 0,
  "phase": "group1",
  "payload": {
    "type": "attack",
    "targetHex": "h59"
  }
}
```

Fortify between owned adjacent hexes:

```python
{
  "turn": 0,
  "phase": "group1",
  "payload": {
    "type": "fortify",
    "fromHex": "h10",
    "toHex": "h11",
    "amount": 1
  }
}
```

Important engine behavior:

- `move` claims an adjacent neutral hex
- `attack` targets an adjacent enemy hex
- `fortify` moves power between owned adjacent hexes
- for `move` and `attack`, the server chooses the strongest adjacent owned source hex automatically
- the runtime bot handles polling and POST requests
- the strategy only returns one action dict or `None`
