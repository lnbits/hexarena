from uuid import uuid4

import pytest

from hexarena.crud import (  # type: ignore[import]
    create_action,
    create_agent,
    create_game,
    create_game_run,
    create_join_request,
    delete_agent,
    delete_game,
    get_action,
    get_actions_for_run,
    get_agents_paginated,
    get_game,
    get_game_by_id,
    get_game_run,
    get_games_paginated,
    get_game_runs_paginated,
    get_join_request,
    get_run_ids_for_game,
    update_game,
)
from hexarena.engine.bootstrap import bootstrap_run_state  # type: ignore[import]
from hexarena.models import (  # type: ignore[import]
    ActionPayload,
    CreateAction,
    CreateAgent,
    CreateGame,
    CreateGameRun,
    Game,
    GameConfig,
    GameState,
)


@pytest.mark.asyncio
async def test_create_and_get_game():
    user_id = uuid4().hex

    game_one = await create_game(
        user_id,
        CreateGame(
            name="Arena Alpha",
            wallet_id="wallet-1",
            status="draft",
            default_config=GameConfig(entry_fee_sats=0, poll_interval_sec=15),
        ),
    )
    assert game_one.id is not None
    assert game_one.user_id == user_id
    assert game_one.wallet_id == "wallet-1"

    stored = await get_game(user_id, game_one.id)
    assert stored is not None
    assert stored.name == game_one.name
    assert stored.default_config.poll_interval_sec == 15

    game_two = await create_game(
        user_id,
        CreateGame(name="Arena Beta", wallet_id="wallet-1"),
    )
    assert game_two.id is not None

    page = await get_games_paginated(user_id=user_id)
    assert page.total == 2
    assert len(page.data) == 2

    await delete_game(user_id, game_one.id)
    stored_deleted = await get_game_by_id(game_one.id)
    assert stored_deleted is None


@pytest.mark.asyncio
async def test_update_game():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(name="Arena Gamma", wallet_id="wallet-1"),
    )

    updated = await update_game(
        Game(**{**game.dict(), "name": "Arena Delta", "status": "active"})
    )
    assert updated.name == "Arena Delta"

    stored = await get_game_by_id(game.id)
    assert stored is not None
    assert stored.name == "Arena Delta"
    assert stored.status == "active"


@pytest.mark.asyncio
async def test_create_run_agent_and_action():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Run",
            wallet_id="wallet-1",
            default_config=GameConfig(entry_fee_sats=0),
        ),
    )

    run = await create_game_run(
        game,
        CreateGameRun(
            status="running",
            turn=1,
            initial_state=GameState(game_id="placeholder", status="running", turn=1),
        ),
    )
    assert run.game_id == game.id

    run_page = await get_game_runs_paginated([game.id])
    assert run_page.total == 1
    assert run_page.data[0].id == run.id

    run_ids = await get_run_ids_for_game(game.id)
    assert run_ids == [run.id]

    stored_run = await get_game_run(run.id)
    assert stored_run is not None
    assert stored_run.current_state.game_id == run.id

    agent = await create_agent(
        run.id,
        CreateAgent(display_name="bot-1", profile={"kind": "test"}),
        status="active",
        api_key="api-key-1",
    )
    assert agent.run_id == run.id
    assert agent.api_key == "api-key-1"

    agents_page = await get_agents_paginated([run.id])
    assert agents_page.total == 1
    assert agents_page.data[0].id == agent.id

    action = await create_action(
        run.id,
        agent.id,
        CreateAction(
            turn=1,
            payload=ActionPayload(type="move", target_hex="h42"),
        ),
    )
    assert action.action_type == "move"

    stored_action = await get_action(action.id)
    assert stored_action is not None
    assert stored_action.run_id == run.id
    assert stored_action.payload["targetHex"] == "h42"

    replay_actions = await get_actions_for_run(run.id)
    assert len(replay_actions) == 1
    assert replay_actions[0].id == action.id

    await delete_agent(run.id, agent.id)


@pytest.mark.asyncio
async def test_create_join_request():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(name="Arena Join", wallet_id="wallet-1"),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))

    join_request = await create_join_request(
        run.id,
        display_name="bot-pay",
        profile={"model": "test"},
        payment_hash="hash-1",
        payment_request="lnbc1test",
    )
    assert join_request.run_id == run.id
    assert join_request.paid is False
    assert join_request.status == "pending_payment"

    stored = await get_join_request(join_request.id)
    assert stored is not None
    assert stored.display_name == "bot-pay"


@pytest.mark.asyncio
async def test_bootstrap_run_state():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Engine",
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
    assert initialized.status == "running"
    assert initialized.turn == 1
    assert initialized.initial_state.game_id == run.id
    assert len(initialized.initial_state.hexes) == (
        game.default_config.base_hex_count + game.default_config.max_players * 20
    )
    owned_hexes = [hex_ for hex_ in initialized.initial_state.hexes if hex_.owner]
    assert len(owned_hexes) == 2
    assert owned_hexes[0].id not in owned_hexes[1].adjacent
