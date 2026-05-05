from http import HTTPStatus

from fastapi import APIRouter, Depends, Header, Request
from fastapi.exceptions import HTTPException
from lnurl import encode as lnurl_encode
from lnbits.core.models import SimpleStatus
from lnbits.core.models.users import AccountId
from lnbits.db import Filters, Page
from lnbits.decorators import check_account_id_exists, parse_filters
from lnbits.helpers import generate_filter_params_openapi
from loguru import logger

from .crud import (
    create_action,
    create_agent,
    create_game,
    create_game_run,
    delete_agent,
    delete_game,
    delete_game_run,
    generate_api_key,
    get_action as get_action_record,
    get_actions_for_run,
    get_actions_for_turn,
    get_actions_paginated,
    get_agent,
    get_agent_by_api_key,
    get_agent_by_id,
    get_agents_paginated,
    get_game,
    get_game_by_id,
    get_game_ids_by_user,
    get_game_run,
    get_game_run_for_user,
    get_game_runs_paginated,
    get_join_request_for_user,
    get_join_requests_paginated,
    get_public_joinable_runs,
    get_run_active_agent_count,
    get_run_pending_join_count,
    get_run_ids_for_game,
    get_games_paginated,
    update_agent,
    update_game,
    update_game_run,
)
from .realtime import get_admin_channel_id, publish_admin_event_for_user
from .engine import ActionValidationError, validate_action_submission
from .models import (
    Action,
    ActionFilters,
    Agent,
    AgentFilters,
    AgentPayoutResponse,
    CreateAction,
    CreateAgent,
    CreateGame,
    CreateJoinRequest,
    CreateGameRun,
    FinishRunRequest,
    Game,
    GameFilters,
    GameRun,
    GameRunFilters,
    JoinRequest,
    JoinRequestFilters,
    JoinRunResponse,
    PublicAgent,
    PublicGame,
    PublicGameRun,
    PublicRunListItem,
    ReplayResponse,
    SettlePayoutRequest,
    UpdateAgent,
    UpdateGame,
    UpdateGameRun,
)
from .services import (
    cancel_run,
    create_join_flow,
    finalize_run,
    get_agent_payout_claim,
    get_public_join_flow_status,
    initialize_run,
    retry_run_fee_settlement,
    settle_agent_payout_admin,
)

hexarena_api_router = APIRouter()
game_filters = parse_filters(GameFilters)
run_filters = parse_filters(GameRunFilters)
agent_filters = parse_filters(AgentFilters)
action_filters = parse_filters(ActionFilters)
join_request_filters = parse_filters(JoinRequestFilters)


async def require_run_api_key(
    run_id: str,
    x_api_key: str | None = Header(default=None),
) -> Agent:
    if not x_api_key:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Missing X-API-Key header.")

    agent = await get_agent_by_api_key(run_id, x_api_key)
    if not agent:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid API key.")

    return agent


############################ Games ############################
@hexarena_api_router.post("/api/v1/games", status_code=HTTPStatus.CREATED)
async def api_create_game(
    data: CreateGame,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Game:
    game = await create_game(account_id.id, data)
    await publish_admin_event_for_user(account_id.id, scope="games", event="created", entity_id=game.id)
    return game


@hexarena_api_router.put("/api/v1/games/{game_id}", response_model=Game)
async def api_update_game(
    game_id: str,
    data: UpdateGame,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Game:
    game = await get_game(account_id.id, game_id)
    if not game:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Game not found.")
    updated = await update_game(game.copy(update=data.dict(exclude_unset=True)))
    await publish_admin_event_for_user(account_id.id, scope="games", event="updated", entity_id=updated.id)
    return updated


@hexarena_api_router.get(
    "/api/v1/games/paginated",
    openapi_extra=generate_filter_params_openapi(GameFilters),
    response_model=Page[Game],
)
async def api_get_games_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    filters: Filters = Depends(game_filters),
) -> Page[Game]:
    return await get_games_paginated(account_id.id, filters)


@hexarena_api_router.get("/api/v1/games/{game_id}", response_model=Game)
async def api_get_game(
    game_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Game:
    game = await get_game(account_id.id, game_id)
    if not game:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Game not found.")
    return game


@hexarena_api_router.get("/api/v1/public/games/{game_id}", response_model=PublicGame)
async def api_get_public_game(game_id: str) -> PublicGame:
    game = await get_game_by_id(game_id)
    if not game:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Game not found.")
    return PublicGame(**game.dict())


@hexarena_api_router.get("/api/v1/public/runs", response_model=list[PublicRunListItem])
async def api_get_public_runs() -> list[PublicRunListItem]:
    return await get_public_joinable_runs()


@hexarena_api_router.get("/api/v1/admin/ws")
async def api_get_admin_ws_channel(
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    return {"channel": get_admin_channel_id(account_id.id)}


@hexarena_api_router.delete("/api/v1/games/{game_id}", response_model=SimpleStatus)
async def api_delete_game(
    game_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    await delete_game(account_id.id, game_id)
    await publish_admin_event_for_user(account_id.id, scope="games", event="deleted", entity_id=game_id)
    return SimpleStatus(success=True, message="Game deleted")


############################ Game Runs ############################
@hexarena_api_router.post(
    "/api/v1/games/{game_id}/runs",
    response_model=GameRun,
    status_code=HTTPStatus.CREATED,
)
async def api_create_game_run(
    game_id: str,
    data: CreateGameRun,
    account_id: AccountId = Depends(check_account_id_exists),
) -> GameRun:
    game = await get_game(account_id.id, game_id)
    if not game:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Game not found.")
    run = await create_game_run(game, data)
    await publish_admin_event_for_user(account_id.id, scope="runs", event="created", entity_id=run.id)
    return run


@hexarena_api_router.put("/api/v1/runs/{run_id}", response_model=GameRun)
async def api_update_game_run(
    run_id: str,
    data: UpdateGameRun,
    account_id: AccountId = Depends(check_account_id_exists),
) -> GameRun:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    updated = await update_game_run(run.copy(update=data.dict(exclude_unset=True)))
    await publish_admin_event_for_user(account_id.id, scope="runs", event="updated", entity_id=updated.id)
    return updated


@hexarena_api_router.post(
    "/api/v1/runs/{run_id}/start",
    response_model=GameRun,
    status_code=HTTPStatus.OK,
)
async def api_start_run(
    run_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> GameRun:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    try:
        await initialize_run(run_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    updated = await get_game_run_for_user(account_id.id, run_id)
    assert updated
    await publish_admin_event_for_user(account_id.id, scope="runs", event="started", entity_id=updated.id)
    return updated


@hexarena_api_router.post(
    "/api/v1/runs/{run_id}/finish",
    response_model=GameRun,
    status_code=HTTPStatus.OK,
)
async def api_finish_run(
    run_id: str,
    data: FinishRunRequest,
    account_id: AccountId = Depends(check_account_id_exists),
) -> GameRun:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    try:
        updated = await finalize_run(run_id, winner_agent_id=data.winner_agent_id)
        await publish_admin_event_for_user(account_id.id, scope="runs", event="finished", entity_id=updated.id)
        return updated
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@hexarena_api_router.post(
    "/api/v1/runs/{run_id}/cancel",
    response_model=GameRun,
    status_code=HTTPStatus.OK,
)
async def api_cancel_run(
    run_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> GameRun:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    try:
        updated = await cancel_run(run_id)
        await publish_admin_event_for_user(account_id.id, scope="runs", event="cancelled", entity_id=updated.id)
        return updated
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@hexarena_api_router.post(
    "/api/v1/runs/{run_id}/fees/retry",
    response_model=GameRun,
    status_code=HTTPStatus.OK,
)
async def api_retry_run_fees(
    run_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> GameRun:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    try:
        updated = await retry_run_fee_settlement(run_id)
        await publish_admin_event_for_user(account_id.id, scope="runs", event="fees_retried", entity_id=updated.id)
        return updated
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@hexarena_api_router.get(
    "/api/v1/runs/paginated",
    openapi_extra=generate_filter_params_openapi(GameRunFilters),
    response_model=Page[GameRun],
)
async def api_get_runs_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    game_id: str | None = None,
    filters: Filters = Depends(run_filters),
) -> Page[GameRun]:
    game_ids = await get_game_ids_by_user(account_id.id)
    if game_id:
        if game_id not in game_ids:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Not your game.")
        game_ids = [game_id]
    return await get_game_runs_paginated(game_ids=game_ids, filters=filters)


@hexarena_api_router.get("/api/v1/runs/{run_id}", response_model=GameRun)
async def api_get_run(
    run_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> GameRun:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    return run


@hexarena_api_router.get(
    "/api/v1/public/runs/{run_id}",
    response_model=PublicGameRun,
)
async def api_get_public_run(run_id: str) -> PublicGameRun:
    run = await get_game_run(run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    active_agent_count = await get_run_active_agent_count(run_id)
    pending_join_count = await get_run_pending_join_count(run_id)
    occupied_seats = active_agent_count + pending_join_count
    open_seats = max(0, run.config.max_players - occupied_seats)
    needs_players = max(0, run.config.min_players - active_agent_count)
    return PublicGameRun(
        **run.dict(),
        active_agent_count=active_agent_count,
        pending_join_count=pending_join_count,
        occupied_seats=occupied_seats,
        open_seats=open_seats,
        needs_players=needs_players,
        can_start_now=active_agent_count >= run.config.min_players,
        starts_on_join=(
            open_seats > 0
            and active_agent_count < run.config.min_players
            and active_agent_count + 1 >= run.config.min_players
        ),
    )


@hexarena_api_router.get("/api/v1/public/runs/{run_id}/lnurl")
async def api_get_public_run_lnurl(
    run_id: str, request: Request, display_name: str | None = None
) -> dict:
    run = await get_game_run(run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    if run.config.entry_fee_sats <= 0:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "This run does not require LNURL-pay."
        )
    join_url = str(request.url_for("hexarena.lnurl_join", run_id=run_id))
    if display_name:
        join_url += f"?display_name={display_name}"
    return {"lnurl": lnurl_encode(join_url), "url": join_url}


@hexarena_api_router.get("/api/v1/public/runs/{run_id}/state", response_model=dict)
async def api_get_public_state(run_id: str) -> dict:
    run = await get_game_run(run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    return run.current_state.dict(
        by_alias=True, exclude={"my_agent_id", "my_hexes", "my_power_ups"}
    )


@hexarena_api_router.delete("/api/v1/runs/{run_id}", response_model=SimpleStatus)
async def api_delete_run(
    run_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    await delete_game_run(run.id)
    await publish_admin_event_for_user(account_id.id, scope="runs", event="deleted", entity_id=run_id)
    return SimpleStatus(success=True, message="Run deleted")


############################ Agents ############################
@hexarena_api_router.post(
    "/api/v1/runs/{run_id}/agents",
    response_model=Agent,
    status_code=HTTPStatus.CREATED,
)
async def api_create_agent(
    run_id: str,
    data: CreateAgent,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Agent:
    run = await get_game_run_for_user(account_id.id, run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    agent = await create_agent(run_id, data, status="active", api_key=generate_api_key())
    await publish_admin_event_for_user(account_id.id, scope="agents", event="created", entity_id=agent.id)
    return agent


@hexarena_api_router.post(
    "/api/v1/public/runs/{run_id}/join",
    response_model=JoinRunResponse,
    status_code=HTTPStatus.CREATED,
)
async def api_join_run(run_id: str, data: CreateAgent) -> JoinRunResponse:
    try:
        return await create_join_flow(
            run_id,
            CreateJoinRequest(
                display_name=data.display_name,
                profile=data.profile,
            ),
        )
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@hexarena_api_router.get(
    "/api/v1/public/join-requests/{join_request_id}",
    name="hexarena.api_get_join_status",
    response_model=JoinRunResponse,
)
async def api_get_join_status(
    join_request_id: str, token: str | None = None
) -> JoinRunResponse:
    join_status = await get_public_join_flow_status(
        join_request_id,
        claim_token=token,
    )
    if not join_status:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Join request not found.")
    return join_status


@hexarena_api_router.get(
    "/api/v1/join-requests/paginated",
    openapi_extra=generate_filter_params_openapi(JoinRequestFilters),
    response_model=Page[JoinRequest],
)
async def api_get_join_requests_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    game_id: str | None = None,
    run_id: str | None = None,
    filters: Filters = Depends(join_request_filters),
) -> Page[JoinRequest]:
    if run_id:
        run = await get_game_run_for_user(account_id.id, run_id)
        if not run:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Not your run.")
        run_ids = [run_id]
    else:
        game_ids = await get_game_ids_by_user(account_id.id)
        if game_id:
            if game_id not in game_ids:
                raise HTTPException(HTTPStatus.FORBIDDEN, "Not your game.")
            game_ids = [game_id]
        run_ids = []
        for gid in game_ids:
            run_ids.extend(await get_run_ids_for_game(gid))
    return await get_join_requests_paginated(run_ids=run_ids, filters=filters)


@hexarena_api_router.get("/api/v1/join-requests/{join_request_id}", response_model=JoinRequest)
async def api_get_join_request(
    join_request_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> JoinRequest:
    join_request = await get_join_request_for_user(account_id.id, join_request_id)
    if not join_request:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Join request not found.")
    return join_request


@hexarena_api_router.put("/api/v1/agents/{agent_id}", response_model=Agent)
async def api_update_agent(
    agent_id: str,
    data: UpdateAgent,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Agent:
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Agent not found.")
    run = await get_game_run_for_user(account_id.id, agent.run_id)
    if not run:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your agent.")
    updated = await update_agent(agent.copy(update=data.dict(exclude_unset=True)))
    await publish_admin_event_for_user(account_id.id, scope="agents", event="updated", entity_id=updated.id)
    return updated


@hexarena_api_router.get(
    "/api/v1/agents/paginated",
    openapi_extra=generate_filter_params_openapi(AgentFilters),
    response_model=Page[Agent],
)
async def api_get_agents_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    game_id: str | None = None,
    run_id: str | None = None,
    filters: Filters = Depends(agent_filters),
) -> Page[Agent]:
    if run_id:
        run = await get_game_run_for_user(account_id.id, run_id)
        if not run:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Not your run.")
        run_ids = [run_id]
    else:
        game_ids = await get_game_ids_by_user(account_id.id)
        if game_id:
            if game_id not in game_ids:
                raise HTTPException(HTTPStatus.FORBIDDEN, "Not your game.")
            game_ids = [game_id]
        run_ids = []
        for gid in game_ids:
            run_ids.extend(await get_run_ids_for_game(gid))
    return await get_agents_paginated(run_ids=run_ids, filters=filters)


@hexarena_api_router.get("/api/v1/agents/{agent_id}", response_model=Agent)
async def api_get_agent(
    agent_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Agent:
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Agent not found.")
    run = await get_game_run_for_user(account_id.id, agent.run_id)
    if not run:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your agent.")
    return agent


@hexarena_api_router.post(
    "/api/v1/agents/{agent_id}/settle-payout",
    response_model=Agent,
    status_code=HTTPStatus.OK,
)
async def api_settle_agent_payout(
    agent_id: str,
    data: SettlePayoutRequest,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Agent:
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Agent not found.")
    run = await get_game_run_for_user(account_id.id, agent.run_id)
    if not run:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your agent.")
    try:
        return await settle_agent_payout_admin(agent_id, data.payment_request)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@hexarena_api_router.get(
    "/api/v1/public/runs/{run_id}/agents/{agent_id}",
    response_model=PublicAgent,
)
async def api_get_public_agent(run_id: str, agent_id: str) -> PublicAgent:
    agent = await get_agent(run_id, agent_id)
    if not agent:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Agent not found.")
    return PublicAgent(**agent.dict())


@hexarena_api_router.delete("/api/v1/agents/{agent_id}", response_model=SimpleStatus)
async def api_delete_agent(
    agent_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Agent not found.")
    run = await get_game_run_for_user(account_id.id, agent.run_id)
    if not run:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your agent.")
    await delete_agent(agent.run_id, agent.id)
    await publish_admin_event_for_user(account_id.id, scope="agents", event="deleted", entity_id=agent.id)
    return SimpleStatus(success=True, message="Agent deleted")


############################ Actions ############################
@hexarena_api_router.post(
    "/api/v1/runs/{run_id}/actions",
    status_code=HTTPStatus.ACCEPTED,
    response_model=Action,
)
async def api_submit_action(
    run_id: str,
    data: CreateAction,
    agent: Agent = Depends(require_run_api_key),
) -> Action:
    run = await get_game_run(run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    if run.status != "running":
        logger.warning(
            "HexArena action rejected: run not active "
            f"run_id={run_id} agent_id={agent.id} requested_turn={data.turn} "
            f"current_turn={run.turn} action_type={data.payload.type} "
            f"payload={data.payload.dict(by_alias=True, exclude_none=True)}"
        )
        raise HTTPException(HTTPStatus.CONFLICT, "GAME_NOT_ACTIVE")
    if agent.status not in {"active", "alive"}:
        logger.warning(
            "HexArena action rejected: agent not active "
            f"run_id={run_id} agent_id={agent.id} agent_status={agent.status} "
            f"requested_turn={data.turn} current_turn={run.turn} "
            f"action_type={data.payload.type} "
            f"payload={data.payload.dict(by_alias=True, exclude_none=True)}"
        )
        raise HTTPException(HTTPStatus.CONFLICT, "Agent is not active.")
    normalized = data.copy(update={"turn": run.turn})
    queued_actions = await get_actions_for_turn(run_id, run.turn)
    logger.info(
        "HexArena action submitted "
        f"run_id={run_id} agent_id={agent.id} requested_turn={data.turn} "
        f"normalized_turn={normalized.turn} action_type={normalized.payload.type} "
        f"phase={normalized.phase} "
        f"queued_group1_actions="
        f"{len([action for action in queued_actions if action.agent_id == agent.id and action.phase == 'group1'])} "
        f"payload={normalized.payload.dict(by_alias=True, exclude_none=True)}"
    )
    try:
        validate_action_submission(run, agent, normalized.payload, queued_actions)
    except ActionValidationError as exc:
        logger.warning(
            "HexArena action validation failed "
            f"run_id={run_id} agent_id={agent.id} turn={run.turn} "
            f"action_type={normalized.payload.type} phase={normalized.phase} "
            f"reason={exc} payload={normalized.payload.dict(by_alias=True, exclude_none=True)}"
        )
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc
    action = await create_action(run_id, agent.id, normalized)
    logger.info(
        "HexArena action queued "
        f"run_id={run_id} agent_id={agent.id} action_id={action.id} "
        f"turn={action.turn} action_type={action.action_type} phase={action.phase}"
    )
    return action


@hexarena_api_router.get("/api/v1/runs/{run_id}/state", response_model=dict)
async def api_get_agent_state(
    run_id: str,
    agent: Agent = Depends(require_run_api_key),
) -> dict:
    run = await get_game_run(run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    state = run.current_state.copy(deep=True)
    state.my_agent_id = agent.id
    state.my_hexes = [tile.id for tile in state.hexes if tile.owner == agent.id]
    state.my_power_ups = list(agent.inventory or [])
    state_dict = state.dict(by_alias=True)
    logger.info(
        "HexArena state fetched "
        f"run_id={run_id} agent_id={agent.id} status={state_dict.get('status')} "
        f"turn={state_dict.get('turn')} my_hexes={state_dict.get('myHexes')} "
        f"owned_hex_count={len(state_dict.get('myHexes') or [])}"
    )
    return state_dict


@hexarena_api_router.get(
    "/api/v1/runs/{run_id}/payout",
    response_model=AgentPayoutResponse,
)
async def api_get_agent_payout(
    run_id: str,
    request: Request,
    agent: Agent = Depends(require_run_api_key),
) -> AgentPayoutResponse:
    try:
        return await get_agent_payout_claim(run_id, agent, request)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@hexarena_api_router.get(
    "/api/v1/public/runs/{run_id}/replay",
    response_model=ReplayResponse,
)
async def api_get_replay(run_id: str) -> ReplayResponse:
    run = await get_game_run(run_id)
    if not run:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Run not found.")
    game = await get_game_by_id(run.game_id)
    if not game:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Game not found.")
    actions = await get_actions_for_run(run_id)
    return ReplayResponse(
        game=PublicGame(**game.dict()),
        run=PublicGameRun(**run.dict()),
        initial_state=run.initial_state,
        actions=actions,
    )


@hexarena_api_router.get(
    "/api/v1/actions/paginated",
    openapi_extra=generate_filter_params_openapi(ActionFilters),
    response_model=Page[Action],
)
async def api_get_actions_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    game_id: str | None = None,
    run_id: str | None = None,
    filters: Filters = Depends(action_filters),
) -> Page[Action]:
    if run_id:
        run = await get_game_run_for_user(account_id.id, run_id)
        if not run:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Not your run.")
        run_ids = [run_id]
    else:
        game_ids = await get_game_ids_by_user(account_id.id)
        if game_id:
            if game_id not in game_ids:
                raise HTTPException(HTTPStatus.FORBIDDEN, "Not your game.")
            game_ids = [game_id]
        run_ids = []
        for gid in game_ids:
            run_ids.extend(await get_run_ids_for_game(gid))
    return await get_actions_paginated(run_ids=run_ids, filters=filters)


@hexarena_api_router.get("/api/v1/actions/{action_id}", response_model=Action)
async def api_get_action(
    action_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Action:
    action = await get_action_record(action_id)
    if not action:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Action not found.")
    run = await get_game_run_for_user(account_id.id, action.run_id)
    if not run:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your action.")
    return action
