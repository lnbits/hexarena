from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hexarena import hexarena_ext  # type: ignore[import]
from hexarena.crud import create_game, create_game_run, get_game_run, update_game_run  # type: ignore[import]
from hexarena.models import CreateGame, CreateGameRun, GameConfig  # type: ignore[import]
from hexarena.services import auto_start_waiting_runs, process_due_running_runs, utc_now  # type: ignore[import]


def _choose_skill_action(state: dict) -> dict | None:
    my_agent_id = state.get("myAgentId")
    my_hex_ids = set(state.get("myHexes") or [])
    tiles = state.get("hexes") or []
    if not my_agent_id or not my_hex_ids:
        return None

    tiles_by_id = {tile["id"]: tile for tile in tiles}
    owned_tiles = [tiles_by_id[tile_id] for tile_id in my_hex_ids if tile_id in tiles_by_id]

    def passable(tile: dict) -> bool:
        return tile.get("terrain") != "water"

    enemy_targets: list[tuple[dict, dict]] = []
    neutral_targets: list[tuple[dict, dict]] = []
    fortify_targets: list[tuple[dict, dict, int]] = []

    for source in owned_tiles:
        source_power = source.get("power") or 0
        for target_hex_id in source.get("adjacent") or []:
            target = tiles_by_id.get(target_hex_id)
            if not target or not passable(target):
                continue
            owner = target.get("owner")
            if owner is None and source_power >= 1:
                neutral_targets.append((source, target))
            elif owner and owner != my_agent_id and source_power >= 2:
                enemy_targets.append((source, target))
            elif owner == my_agent_id and source_power >= 2:
                amount = min(3, source_power - 1, max(0, 10 - (target.get("power") or 0)))
                if amount >= 1:
                    fortify_targets.append((source, target, amount))

    if enemy_targets:
        enemy_targets.sort(
            key=lambda pair: ((pair[1].get("power") or 0), -(pair[0].get("power") or 0), pair[1]["id"])
        )
        return {
            "turn": 0,
            "phase": "group1",
            "payload": {"type": "attack", "targetHex": enemy_targets[0][1]["id"]},
        }

    if neutral_targets:
        neutral_targets.sort(
            key=lambda pair: (-(pair[0].get("power") or 0), pair[1]["id"])
        )
        return {
            "turn": 0,
            "phase": "group1",
            "payload": {"type": "move", "targetHex": neutral_targets[0][1]["id"]},
        }

    if fortify_targets:
        fortify_targets.sort(
            key=lambda pair: (-(pair[0].get("power") or 0), pair[1].get("power") or 0, pair[1]["id"])
        )
        source, target, amount = fortify_targets[0]
        return {
            "turn": 0,
            "phase": "group1",
            "payload": {
                "type": "fortify",
                "fromHex": source["id"],
                "toHex": target["id"],
                "amount": amount,
            },
        }

    return None


@pytest.mark.asyncio
async def test_free_run_e2e_skill_agent_flow(capsys):
    app = FastAPI()
    app.include_router(hexarena_ext)
    transport = ASGITransport(app=app)

    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena E2E Free Run",
            wallet_id="wallet-1",
            default_config=GameConfig(
                entry_fee_sats=0,
                min_players=2,
                max_players=2,
                poll_interval_sec=10,
                max_rounds=20,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        runs_response = await client.get("/hexarena/api/v1/public/runs")
        assert runs_response.status_code == 200
        public_runs = runs_response.json()
        selected_run = next(item for item in public_runs if item["id"] == run.id)
        assert selected_run["open_seats"] == 2
        assert selected_run["starts_on_join"] is False

        red_join = await client.post(
            f"/hexarena/api/v1/public/runs/{run.id}/join",
            json={"display_name": "skill-red", "profile": {"kind": "skill-agent"}},
        )
        assert red_join.status_code == 201
        red = red_join.json()
        print(f"Joined skill-red: {red['agent_id']}")

        blue_join = await client.post(
            f"/hexarena/api/v1/public/runs/{run.id}/join",
            json={"display_name": "skill-blue", "profile": {"kind": "skill-agent"}},
        )
        assert blue_join.status_code == 201
        blue = blue_join.json()
        print(f"Joined skill-blue: {blue['agent_id']}")

        started = await auto_start_waiting_runs()
        assert started >= 1
        started_run = await get_game_run(run.id)
        assert started_run is not None
        assert started_run.status == "running"
        await update_game_run(
            started_run.copy(update={"started_at": utc_now() - timedelta(seconds=300)})
        )

        final_status = "running"
        final_winner = None
        for _ in range(8):
            run_snapshot = await get_game_run(run.id)
            assert run_snapshot is not None
            if run_snapshot.status != "running":
                final_status = run_snapshot.status
                final_winner = run_snapshot.winner_agent_id
                break

            turn = run_snapshot.turn
            print(f"Turn {turn}")
            for name, joined in (("skill-red", red), ("skill-blue", blue)):
                state_response = await client.get(
                    f"/hexarena/api/v1/runs/{run.id}/state",
                    headers={"X-API-Key": joined["api_key"]},
                )
                assert state_response.status_code == 200
                state = state_response.json()
                action = _choose_skill_action(state)
                if not action:
                    print(f"  {name}: no action")
                    continue
                action_response = await client.post(
                    f"/hexarena/api/v1/runs/{run.id}/actions",
                    headers={"X-API-Key": joined["api_key"]},
                    json=action,
                )
                assert action_response.status_code == 202, action_response.text
                payload = action_response.json()
                print(f"  {name}: {payload['action_type']} -> queued")

            processed = await process_due_running_runs(max_turns_per_run=1)
            assert processed >= 1

        updated_run = await get_game_run(run.id)
        assert updated_run is not None
        final_status = updated_run.status
        final_winner = updated_run.winner_agent_id
        print(f"Finished status={final_status} winner={final_winner}")
        print(f"Leaderboard={updated_run.current_state.leaderboard}")

        public_run_response = await client.get(f"/hexarena/api/v1/public/runs/{run.id}")
        assert public_run_response.status_code == 200
        public_run = public_run_response.json()

        assert public_run["winner_agent_id"] == final_winner
        assert final_status in {"running", "finished"}
        assert red["agent_id"] in {entry.agent_id for entry in updated_run.current_state.leaderboard}
        assert blue["agent_id"] in {entry.agent_id for entry in updated_run.current_state.leaderboard}

    captured = capsys.readouterr()
    assert "Joined skill-red" in captured.out
    assert "Turn 1" in captured.out
