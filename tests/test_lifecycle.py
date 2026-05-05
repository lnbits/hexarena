from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from hexarena.crud import (  # type: ignore[import]
    create_action,
    create_agent,
    create_game,
    create_game_run,
    get_action,
    get_agent_by_id,
    get_agents_for_run,
    get_game_run,
    get_game_runs_paginated,
    get_public_joinable_runs,
    update_game_run,
)
from hexarena.engine.bootstrap import bootstrap_run_state  # type: ignore[import]
from hexarena.engine.resolution import resolve_turn  # type: ignore[import]
from hexarena.models import (  # type: ignore[import]
    ActionPayload,
    CreateAction,
    CreateAgent,
    CreateGame,
    CreateGameRun,
    CreateJoinRequest,
    GameConfig,
)
from hexarena.services import (  # type: ignore[import]
    auto_start_waiting_runs,
    create_join_flow,
    ensure_waiting_runs_for_finished_games,
    initialize_run,
    process_due_running_runs,
    process_run_turn,
    utc_now,
)
from hexarena.views_api import api_get_public_run  # type: ignore[import]


def _pick_open_adjacent_target(run, agent_id: str):
    owned_hex = next(tile for tile in run.current_state.hexes if tile.owner == agent_id)
    target = next(
        tile
        for tile in run.current_state.hexes
        if tile.id in owned_hex.adjacent and tile.owner is None and tile.terrain != "water"
    )
    owned_hex.power = 2
    return owned_hex, target


@pytest.mark.asyncio
async def test_free_join_flow_creates_active_agent_with_api_key():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Free Join",
            wallet_id="wallet-1",
            default_config=GameConfig(entry_fee_sats=0, min_players=2, max_players=4),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))

    joined = await create_join_flow(
        run.id,
        CreateJoinRequest(display_name="happy-bot", profile={"kind": "test"}),
    )

    assert joined.paid is False
    assert joined.payment_required is False
    assert joined.credentials_ready is True
    assert joined.agent_id
    assert joined.api_key

    stored_agent = await get_agent_by_id(joined.agent_id)
    assert stored_agent is not None
    assert stored_agent.status == "active"
    assert stored_agent.api_key == joined.api_key


@pytest.mark.asyncio
async def test_auto_start_waiting_run_when_min_players_joined():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Auto Start",
            wallet_id="wallet-1",
            default_config=GameConfig(
                entry_fee_sats=0,
                min_players=2,
                max_players=4,
                auto_start_after_sec=60,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a")
    await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b")

    started = await auto_start_waiting_runs()
    updated_run = await get_game_run(run.id)

    assert started >= 1
    assert updated_run is not None
    assert updated_run.status == "running"
    assert updated_run.turn == 1
    assert len([tile for tile in updated_run.current_state.hexes if tile.owner]) == 2


@pytest.mark.asyncio
async def test_waiting_run_does_not_auto_start_below_min_players_even_after_timeout():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena No Solo Autostart",
            wallet_id="wallet-1",
            default_config=GameConfig(
                entry_fee_sats=0,
                min_players=2,
                max_players=4,
                auto_start_after_sec=1,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    stale_run = run.copy(update={"created_at": utc_now() - timedelta(seconds=120)})
    await update_game_run(stale_run)
    await create_agent(stale_run.id, CreateAgent(display_name="solo-bot"), status="active", api_key="solo")

    started = await auto_start_waiting_runs()
    updated_run = await get_game_run(run.id)

    assert started >= 0
    assert updated_run is not None
    assert updated_run.status == "waiting"
    assert updated_run.turn == 0


@pytest.mark.asyncio
async def test_public_run_list_exposes_seat_counts_and_start_hint():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Seat Hints",
            wallet_id="wallet-1",
            default_config=GameConfig(
                entry_fee_sats=0,
                min_players=2,
                max_players=4,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a")

    runs = await get_public_joinable_runs()
    public_run = next(item for item in runs if item.id == run.id)

    assert public_run.active_agent_count == 1
    assert public_run.pending_join_count == 0
    assert public_run.open_seats == 3
    assert public_run.needs_players == 1
    assert public_run.can_start_now is False
    assert public_run.starts_on_join is True


@pytest.mark.asyncio
async def test_initialized_state_exposes_display_names_in_public_standings():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Display Names",
            wallet_id="wallet-1",
            default_config=GameConfig(
                entry_fee_sats=0,
                min_players=2,
                max_players=2,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    await create_agent(run.id, CreateAgent(display_name="red-bot"), status="active", api_key="a")
    await create_agent(run.id, CreateAgent(display_name="blue-bot"), status="active", api_key="b")

    await initialize_run(run.id)
    initialized = await get_game_run(run.id)
    assert initialized is not None

    leaderboard_names = {entry.display_name for entry in initialized.current_state.leaderboard}
    standing_names = {entry.display_name for entry in initialized.current_state.agents}

    assert {"red-bot", "blue-bot"} <= leaderboard_names
    assert {"red-bot", "blue-bot"} <= standing_names


@pytest.mark.asyncio
async def test_join_flow_rejects_full_waiting_run():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Full Run",
            wallet_id="wallet-1",
            default_config=GameConfig(
                entry_fee_sats=0,
                min_players=2,
                max_players=2,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a")
    await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b")

    with pytest.raises(ValueError, match="Run is full."):
        await create_join_flow(
            run.id,
            CreateJoinRequest(display_name="late-bot", profile={"kind": "test"}),
        )


@pytest.mark.asyncio
async def test_public_run_exposes_winner_when_finished():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Public Winner",
            wallet_id="wallet-1",
            default_config=GameConfig(
                entry_fee_sats=0,
                min_players=2,
                max_players=2,
                poll_interval_sec=10,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)
    finished_state = initialized.current_state.copy(deep=True)
    finished_state.status = "finished"
    winner_run = initialized.copy(
        update={
            "status": "finished",
            "winner_agent_id": agents[0].id,
            "current_state": finished_state,
        }
    )
    await update_game_run(winner_run)

    public_run = await api_get_public_run(run.id)

    assert public_run.status == "finished"
    assert public_run.winner_agent_id == winner_run.winner_agent_id


@pytest.mark.asyncio
async def test_process_run_turn_does_not_mark_all_active_agents_eliminated():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Turn Progression",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents).copy(
        update={"started_at": utc_now() - timedelta(seconds=30)}
    )
    for tile in initialized.current_state.hexes:
        if tile.owner:
            tile.power = 2
    await update_game_run(initialized)

    processed = await process_run_turn(run.id)
    updated_run = await get_game_run(run.id)
    updated_agents = await get_agents_for_run(run.id)

    assert processed is True
    assert updated_run is not None
    assert updated_run.turn == 2
    assert any(not standing.eliminated for standing in updated_run.current_state.agents)
    assert not all(agent.is_eliminated for agent in updated_agents)
    assert len([tile for tile in updated_run.current_state.hexes if tile.owner]) >= 1


@pytest.mark.asyncio
async def test_process_due_running_runs_limits_catch_up_per_call():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Restart Resume",
            wallet_id="wallet-1",
            default_config=GameConfig(
                min_players=2,
                max_players=4,
                entry_fee_sats=0,
                poll_interval_sec=10,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents).copy(
        update={"started_at": utc_now() - timedelta(seconds=120)}
    )
    await update_game_run(initialized)

    processed = await process_due_running_runs(max_turns_per_run=1)
    updated_run = await get_game_run(run.id)

    assert processed >= 1
    assert updated_run is not None
    assert updated_run.turn == 2


@pytest.mark.asyncio
async def test_persisted_action_resolves_after_downtime_resume():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Resume Action",
            wallet_id="wallet-1",
            default_config=GameConfig(
                min_players=2,
                max_players=4,
                entry_fee_sats=0,
                poll_interval_sec=10,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents).copy(
        update={"started_at": utc_now() - timedelta(seconds=30)}
    )
    await update_game_run(initialized)
    action = await create_action(
        run.id,
        agents[0].id,
        CreateAction(turn=initialized.turn, payload=ActionPayload(type="talk", message="still alive")),
    )

    processed = await process_run_turn(run.id)
    resolved_action = await get_action(action.id)
    updated_run = await get_game_run(run.id)

    assert processed is True
    assert resolved_action is not None
    assert resolved_action.status == "resolved"
    assert resolved_action.outcome["success"] is True
    assert updated_run is not None
    assert updated_run.turn == 2
    assert any(
        log.type == "talk" and log.message == "still alive"
        for log in updated_run.current_state.recent_actions
    )


@pytest.mark.asyncio
async def test_disconnected_idle_agents_keep_single_starting_hex_for_recovery(monkeypatch):
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Disconnect",
            wallet_id="wallet-1",
            default_config=GameConfig(
                min_players=2,
                max_players=2,
                entry_fee_sats=0,
                poll_interval_sec=10,
                power_growth_every_n_turns=99,
                max_rounds=20,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)
    # Single starting hexes at starting power should survive idle turns to allow recovery.
    for tile in initialized.current_state.hexes:
        if tile.owner == agents[0].id:
            tile.power = 1
            tile.power_next_growth_in_turns = 99
        elif tile.owner == agents[1].id:
            tile.power = 1
            tile.power_next_growth_in_turns = 99
    initialized = initialized.copy(update={"started_at": utc_now() - timedelta(seconds=200)})
    await update_game_run(initialized)

    async def fake_get_pr_from_lnurl(*args, **kwargs):
        return "lnbc1tribute"

    async def fake_pay_invoice(**kwargs):
        return SimpleNamespace(payment_hash="fee-paid")

    monkeypatch.setattr("hexarena.services.get_pr_from_lnurl", fake_get_pr_from_lnurl)
    monkeypatch.setattr("hexarena.services.pay_invoice", fake_pay_invoice)

    processed = await process_due_running_runs(max_turns_per_run=3)
    updated_run = await get_game_run(run.id)
    updated_agents = await get_agents_for_run(run.id)

    assert processed >= 1
    assert updated_run is not None
    assert updated_run.status == "running"
    assert updated_run.winner_agent_id is None
    assert all(not agent.is_eliminated for agent in updated_agents)
    assert all(standing.hex_count == 1 for standing in updated_run.current_state.agents)


@pytest.mark.asyncio
async def test_all_idle_players_with_available_actions_finish_deterministically():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena All Idle Deadlock",
            wallet_id="wallet-1",
            default_config=GameConfig(
                min_players=2,
                max_players=2,
                entry_fee_sats=0,
                poll_interval_sec=10,
                power_growth_every_n_turns=99,
                max_rounds=20,
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)
    for tile in initialized.current_state.hexes:
        if tile.owner:
            tile.power = 1
            tile.power_next_growth_in_turns = 99
    initialized = initialized.copy(update={"started_at": utc_now() - timedelta(seconds=30)})
    await update_game_run(initialized)

    await process_run_turn(run.id)
    updated_run = await get_game_run(run.id)

    assert updated_run is not None
    assert updated_run.status == "running"
    assert updated_run.winner_agent_id is None
    assert all(standing.hex_count == 1 for standing in updated_run.current_state.agents)


@pytest.mark.asyncio
async def test_finished_run_spawns_fresh_waiting_run_after_cooldown():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Respawn",
            wallet_id="wallet-1",
            default_config=GameConfig(entry_fee_sats=0, min_players=2, max_players=4),
        ),
    )
    finished_run = await create_game_run(
        game,
        CreateGameRun(
            status="finished",
            config=game.default_config.copy(deep=True),
            finished_at=utc_now() - timedelta(seconds=120),
        ),
    )

    spawned = await ensure_waiting_runs_for_finished_games(cooldown_seconds=60)
    page = await get_game_runs_paginated([game.id])
    waiting_runs = [run for run in page.data if run.status == "waiting"]

    assert spawned == 1
    assert finished_run.id != waiting_runs[0].id
    assert len(waiting_runs) == 1
    assert waiting_runs[0].config == finished_run.config


@pytest.mark.asyncio
async def test_finished_run_does_not_spawn_duplicate_waiting_run():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Respawn Dedup",
            wallet_id="wallet-1",
            default_config=GameConfig(entry_fee_sats=0, min_players=2, max_players=4),
        ),
    )
    await create_game_run(
        game,
        CreateGameRun(
            status="finished",
            config=game.default_config.copy(deep=True),
            finished_at=utc_now() - timedelta(seconds=120),
        ),
    )
    existing_waiting = await create_game_run(
        game,
        CreateGameRun(
            status="waiting",
            config=game.default_config.copy(deep=True),
        ),
    )

    spawned = await ensure_waiting_runs_for_finished_games(cooldown_seconds=60)
    page = await get_game_runs_paginated([game.id])
    waiting_runs = [run for run in page.data if run.status == "waiting"]

    assert spawned == 0
    assert len(waiting_runs) == 1
    assert waiting_runs[0].id == existing_waiting.id
