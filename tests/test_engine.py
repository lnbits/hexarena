from uuid import uuid4

import pytest

from hexarena.engine.bootstrap import bootstrap_run_state  # type: ignore[import]
from hexarena.engine.resolution import resolve_turn  # type: ignore[import]
from hexarena.engine.validation import (  # type: ignore[import]
    ActionValidationError,
    has_available_group1_action,
    validate_action_submission,
)
from hexarena.models import (  # type: ignore[import]
    Action,
    ActionPayload,
    Agent,
    CreateAgent,
    CreateGame,
    CreateGameRun,
    GameConfig,
)
from hexarena.crud import (  # type: ignore[import]
    create_agent,
    create_game,
    create_game_run,
    get_game_run,
    update_game_run,
)


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
async def test_validate_action_submission_rejects_second_group1_action():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Validation",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)
    _, target = _pick_open_adjacent_target(initialized, agents[0].id)

    existing_action = Action(
        id="act-1",
        run_id=initialized.id,
        agent_id=agents[0].id,
        turn=initialized.turn,
        phase="group1",
        action_type="move",
        status="queued",
        target_hex=target.id,
        payload={"type": "move", "targetHex": target.id},
    )

    with pytest.raises(ActionValidationError, match="RATE_LIMITED"):
        validate_action_submission(
            initialized,
            agents[0],
            ActionPayload(type="move", target_hex=target.id),
            [existing_action],
        )


@pytest.mark.asyncio
async def test_resolve_turn_moves_into_empty_hex_and_advances_turn():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Resolution",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)
    source, target = _pick_open_adjacent_target(initialized, agents[0].id)

    action = Action(
        id="act-2",
        run_id=initialized.id,
        agent_id=agents[0].id,
        turn=initialized.turn,
        phase="group1",
        action_type="move",
        status="queued",
        target_hex=target.id,
        payload={"type": "move", "targetHex": target.id},
    )

    updated_run, updated_agents, updated_actions = resolve_turn(initialized, agents, [action])

    claimed_hex = next(tile for tile in updated_run.current_state.hexes if tile.id == target.id)
    moved_from = next(tile for tile in updated_run.current_state.hexes if tile.id == source.id)

    assert updated_run.turn == initialized.turn + 1
    assert updated_actions[0].status == "resolved"
    assert updated_actions[0].outcome["success"] is True
    assert claimed_hex.owner == agents[0].id
    assert claimed_hex.power >= 1
    assert moved_from.power == 2
    assert any(agent.last_action_turn == initialized.turn for agent in updated_agents if agent.id == agents[0].id)


@pytest.mark.asyncio
async def test_resolved_turn_state_persists_recent_action_timestamps():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Persisted Resolution",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)
    source, target = _pick_open_adjacent_target(initialized, agents[0].id)

    action = Action(
        id="act-persist-1",
        run_id=initialized.id,
        agent_id=agents[0].id,
        turn=initialized.turn,
        phase="group1",
        action_type="move",
        status="queued",
        target_hex=target.id,
        payload={"type": "move", "targetHex": target.id},
    )

    updated_run, _, _ = resolve_turn(initialized, agents, [action])
    persisted_run = await update_game_run(updated_run)
    reloaded_run = await get_game_run(persisted_run.id)

    assert reloaded_run is not None
    assert reloaded_run.current_state.recent_actions
    assert reloaded_run.current_state.recent_actions[-1].created_at is not None
    claimed_hex = next(tile for tile in reloaded_run.current_state.hexes if tile.id == target.id)
    moved_from = next(tile for tile in reloaded_run.current_state.hexes if tile.id == source.id)
    assert claimed_hex.owner == agents[0].id
    assert moved_from.power == 2


@pytest.mark.asyncio
async def test_resolve_turn_applies_skip_penalty_to_idle_agent():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Skip Penalty",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)

    idle_tile = next(tile for tile in initialized.current_state.hexes if tile.owner == agents[1].id)
    idle_tile.power = 3

    updated_run, updated_agents, updated_actions = resolve_turn(initialized, agents, [])

    penalized_tile = next(tile for tile in updated_run.current_state.hexes if tile.id == idle_tile.id)
    assert not updated_actions
    assert penalized_tile.power == 2
    assert any(
        log.type == "skip_penalty" and log.agent_id == agents[1].id
        for log in updated_run.current_state.recent_actions
    )
    assert any(agent.id == agents[1].id and not agent.is_eliminated for agent in updated_agents)


@pytest.mark.asyncio
async def test_skip_penalty_ignores_bomb_consumed_turn():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Bomb Skip",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)

    bomb_agent = agents[1].copy(update={"profile": {"skip_group1_turns": [initialized.turn]}})
    bomb_tile = next(tile for tile in initialized.current_state.hexes if tile.owner == bomb_agent.id)
    bomb_tile.power = 3

    updated_run, _, _ = resolve_turn(initialized, [agents[0], bomb_agent], [])

    unchanged_tile = next(
        tile for tile in updated_run.current_state.hexes if tile.id == bomb_tile.id
    )
    assert unchanged_tile.power == 3
    assert not any(
        log.type == "skip_penalty" and log.agent_id == bomb_agent.id
        for log in updated_run.current_state.recent_actions
    )


@pytest.mark.asyncio
async def test_idle_agents_keep_single_starting_hex_when_they_skip_turn_one():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena No Legal Action",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)

    # Freshly bootstrapped players can now expand from power 1, so skipping should be penalized.
    for agent in agents:
        assert has_available_group1_action(initialized, agent) is True

    updated_run, updated_agents, updated_actions = resolve_turn(initialized, agents, [])

    assert not updated_actions
    assert updated_run.status == "running"
    assert updated_run.turn == initialized.turn + 1
    assert any(log.type == "skip_penalty" for log in updated_run.current_state.recent_actions)
    assert all(not agent.is_eliminated for agent in updated_agents)
    assert updated_run.winner_agent_id is None
    for agent in agents:
        standing = next(
            standing for standing in updated_run.current_state.agents if standing.id == agent.id
        )
        assert standing.hex_count == 1
        assert standing.total_power == 1


@pytest.mark.asyncio
async def test_fresh_agents_have_legal_turn_one_expansion_move():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Turn One Expansion",
            wallet_id="wallet-1",
            default_config=GameConfig(min_players=2, max_players=4, entry_fee_sats=0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    initialized = bootstrap_run_state(run, agents)

    assert all(has_available_group1_action(initialized, agent) for agent in agents)
