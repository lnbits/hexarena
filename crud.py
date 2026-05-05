import json
from datetime import datetime, timezone
from enum import Enum
from secrets import token_urlsafe

from lnbits.db import Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash
from pydantic import BaseModel

from .models import (
    Action,
    ActionFilters,
    Agent,
    AgentFilters,
    CreateAction,
    CreateAgent,
    CreateGame,
    CreateGameRun,
    Game,
    GameFilters,
    GameRun,
    GameRunFilters,
    GameState,
    JoinRequest,
    JoinRequestFilters,
    PublicRunListItem,
)

db = Database("ext_hexarena")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_api_key() -> str:
    return token_urlsafe(32)


def _ensure_utc_datetime(value: datetime | None) -> datetime | None:
    if not value:
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _json_safe(value):
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {key: _json_safe(item) for key, item in value.dict().items()}
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _prepare_state_for_storage(state: GameState) -> dict:
    state_dict = _json_safe(state)
    recent_actions = state_dict.get("recent_actions") or []
    for action_log in recent_actions:
        outcome = action_log.get("outcome")
        if isinstance(outcome, dict):
            action_log["outcome"] = json.dumps(outcome)
    return state_dict


def _load_jsonish(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _normalize_state_from_storage(state_value) -> dict:
    state_dict = _load_jsonish(state_value)
    if not isinstance(state_dict, dict):
        raise ValueError("Invalid HexArena game state payload.")

    recent_actions = state_dict.get("recent_actions") or []
    for action_log in recent_actions:
        outcome = action_log.get("outcome")
        if isinstance(outcome, str):
            try:
                action_log["outcome"] = json.loads(outcome)
            except json.JSONDecodeError:
                action_log["outcome"] = {}
    return state_dict


def _parse_game_run_row(row: dict) -> GameRun:
    payload = dict(row)
    payload["config"] = _load_jsonish(payload.get("config") or {})
    payload["initial_state"] = _normalize_state_from_storage(payload.get("initial_state") or {})
    payload["current_state"] = _normalize_state_from_storage(payload.get("current_state") or {})
    run = GameRun.parse_obj(payload)
    return run.copy(
        update={
            "created_at": _ensure_utc_datetime(run.created_at),
            "updated_at": _ensure_utc_datetime(run.updated_at),
            "started_at": _ensure_utc_datetime(run.started_at),
            "finished_at": _ensure_utc_datetime(run.finished_at),
            "fees_settled_at": _ensure_utc_datetime(run.fees_settled_at),
        }
    )


def _prepare_run_for_storage(run: GameRun) -> GameRun:
    return run.copy(
        update={
            "config": _json_safe(run.config),
            "initial_state": _prepare_state_for_storage(run.initial_state),
            "current_state": _prepare_state_for_storage(run.current_state),
        }
    )


def _compute_public_run_seat_fields(
    config,
    *,
    active_agent_count: int,
    pending_join_count: int,
) -> dict:
    occupied_seats = max(0, active_agent_count) + max(0, pending_join_count)
    open_seats = max(0, config.max_players - occupied_seats)
    needs_players = max(0, config.min_players - active_agent_count)
    can_start_now = active_agent_count >= config.min_players
    starts_on_join = (
        open_seats > 0
        and active_agent_count < config.min_players
        and active_agent_count + 1 >= config.min_players
    )
    return {
        "active_agent_count": active_agent_count,
        "pending_join_count": pending_join_count,
        "occupied_seats": occupied_seats,
        "open_seats": open_seats,
        "needs_players": needs_players,
        "can_start_now": can_start_now,
        "starts_on_join": starts_on_join,
    }


def _parse_public_run_list_item_row(row: dict) -> PublicRunListItem:
    payload = dict(row)
    payload["config"] = _load_jsonish(payload.get("config") or {})
    payload["active_agent_count"] = int(payload.get("active_agent_count") or 0)
    payload["pending_join_count"] = int(payload.get("pending_join_count") or 0)
    item = PublicRunListItem.parse_obj(payload)
    return item.copy(
        update=_compute_public_run_seat_fields(
            item.config,
            active_agent_count=item.active_agent_count,
            pending_join_count=item.pending_join_count,
        )
    )


############################ Games ############################
async def create_game(user_id: str, data: CreateGame) -> Game:
    now = utc_now()
    game = Game(
        id=urlsafe_short_hash(),
        user_id=user_id,
        wallet_id=data.wallet_id,
        fee_wallet_id=data.fee_wallet_id,
        name=data.name,
        status=data.status,
        default_config=data.default_config,
        created_at=now,
        updated_at=now,
    )
    await db.insert("hexarena.games", game)
    return game


async def get_game(user_id: str, game_id: str) -> Game | None:
    return await db.fetchone(
        """
        SELECT * FROM hexarena.games
        WHERE id = :id AND user_id = :user_id
        """,
        {"id": game_id, "user_id": user_id},
        Game,
    )


async def get_game_by_id(game_id: str) -> Game | None:
    return await db.fetchone(
        "SELECT * FROM hexarena.games WHERE id = :id",
        {"id": game_id},
        Game,
    )


async def get_game_ids_by_user(user_id: str) -> list[str]:
    rows: list[dict] = await db.fetchall(
        "SELECT DISTINCT id FROM hexarena.games WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    return [row["id"] for row in rows]


async def get_games_paginated(
    user_id: str | None = None,
    filters: Filters[GameFilters] | None = None,
) -> Page[Game]:
    where = []
    values = {}
    if user_id:
        where.append("user_id = :user_id")
        values["user_id"] = user_id

    return await db.fetch_page(
        "SELECT * FROM hexarena.games",
        where=where,
        values=values,
        filters=filters,
        model=Game,
        table_name="hexarena.games",
    )


async def update_game(data: Game) -> Game:
    updated = data.copy(update={"updated_at": utc_now()})
    await db.update("hexarena.games", updated)
    return updated


async def delete_game(user_id: str, game_id: str) -> None:
    run_ids = await get_run_ids_for_game(game_id)
    if run_ids:
        await db.execute(
            "DELETE FROM hexarena.join_requests WHERE run_id IN ({})".format(
                ", ".join([f":run_id__{i}" for i, _ in enumerate(run_ids)])
            ),
            {f"run_id__{i}": run_id for i, run_id in enumerate(run_ids)},
        )
        await db.execute(
            "DELETE FROM hexarena.actions WHERE run_id IN ({})".format(
                ", ".join([f":run_id__{i}" for i, _ in enumerate(run_ids)])
            ),
            {f"run_id__{i}": run_id for i, run_id in enumerate(run_ids)},
        )
        await db.execute(
            "DELETE FROM hexarena.agents WHERE run_id IN ({})".format(
                ", ".join([f":run_id__{i}" for i, _ in enumerate(run_ids)])
            ),
            {f"run_id__{i}": run_id for i, run_id in enumerate(run_ids)},
        )
        await db.execute(
            "DELETE FROM hexarena.game_runs WHERE game_id = :game_id",
            {"game_id": game_id},
        )

    await db.execute(
        "DELETE FROM hexarena.games WHERE id = :id AND user_id = :user_id",
        {"id": game_id, "user_id": user_id},
    )


############################ Game Runs ############################
async def create_game_run(game: Game, data: CreateGameRun) -> GameRun:
    run_id = urlsafe_short_hash()
    config = data.config or game.default_config
    initial_state = (
        data.initial_state.copy(
            update={
                "game_id": run_id,
                "status": data.status,
                "turn": data.turn,
                "poll_interval_sec": config.poll_interval_sec,
            }
        )
        if data.initial_state
        else GameState(
            game_id=run_id,
            status=data.status,
            turn=data.turn,
            poll_interval_sec=config.poll_interval_sec,
        )
    )
    current_state = data.current_state or initial_state.copy(deep=True)
    current_state = current_state.copy(
        update={
            "game_id": run_id,
            "status": data.status,
            "turn": data.turn,
            "poll_interval_sec": config.poll_interval_sec,
        }
    )
    now = utc_now()
    run = GameRun(
        id=run_id,
        game_id=game.id,
        status=data.status,
        config=config,
        initial_state=initial_state,
        current_state=current_state,
        turn=data.turn,
        winner_agent_id=data.winner_agent_id,
        prize_pool_sats=data.prize_pool_sats,
        house_fee_sats=data.house_fee_sats,
        tribute_fee_sats=data.tribute_fee_sats,
        payouts_total_sats=data.payouts_total_sats,
        fee_status=data.fee_status,
        fees_settled_at=data.fees_settled_at,
        started_at=data.started_at,
        finished_at=data.finished_at,
        created_at=now,
        updated_at=now,
    )
    await db.insert("hexarena.game_runs", _prepare_run_for_storage(run))
    await update_game(game.copy(update={"latest_run_id": run.id}))
    return run


async def get_game_run(run_id: str) -> GameRun | None:
    row = await db.fetchone(
        "SELECT * FROM hexarena.game_runs WHERE id = :id",
        {"id": run_id},
    )
    return _parse_game_run_row(row) if row else None


async def get_game_run_for_user(user_id: str, run_id: str) -> GameRun | None:
    row = await db.fetchone(
        """
        SELECT r.* FROM hexarena.game_runs r
        JOIN hexarena.games g ON g.id = r.game_id
        WHERE r.id = :id AND g.user_id = :user_id
        """,
        {"id": run_id, "user_id": user_id},
    )
    return _parse_game_run_row(row) if row else None


async def get_run_ids_for_game(game_id: str) -> list[str]:
    rows: list[dict] = await db.fetchall(
        "SELECT id FROM hexarena.game_runs WHERE game_id = :game_id",
        {"game_id": game_id},
    )
    return [row["id"] for row in rows]


async def get_game_runs_paginated(
    game_ids: list[str] | None = None,
    filters: Filters[GameRunFilters] | None = None,
) -> Page[GameRun]:
    if not game_ids:
        return Page(data=[], total=0)

    values = {}
    ids = []
    for i, game_id in enumerate(game_ids):
        key = f"game_id__{i}"
        ids.append(f"game_id = :{key}")
        values[key] = game_id

    page = await db.fetch_page(
        "SELECT * FROM hexarena.game_runs",
        where=[f"({' OR '.join(ids)})"],
        values=values,
        filters=filters,
        table_name="hexarena.game_runs",
    )
    return Page(data=[_parse_game_run_row(row) for row in page.data], total=page.total)


async def get_public_joinable_runs() -> list[PublicRunListItem]:
    rows = await db.fetchall(
        """
        SELECT
            r.id,
            r.game_id,
            g.name AS game_name,
            g.status AS game_status,
            r.status AS run_status,
            r.config,
            r.turn,
            r.winner_agent_id,
            COALESCE(a.active_agent_count, 0) AS active_agent_count,
            COALESCE(j.pending_join_count, 0) AS pending_join_count,
            r.prize_pool_sats,
            r.started_at,
            r.finished_at,
            r.created_at
        FROM hexarena.game_runs r
        JOIN hexarena.games g ON g.id = r.game_id
        LEFT JOIN (
            SELECT run_id, COUNT(*) AS active_agent_count
            FROM hexarena.agents
            WHERE status = 'active'
            GROUP BY run_id
        ) a ON a.run_id = r.id
        LEFT JOIN (
            SELECT run_id, COUNT(*) AS pending_join_count
            FROM hexarena.join_requests
            WHERE status = 'pending_payment'
            GROUP BY run_id
        ) j ON j.run_id = r.id
        WHERE r.status IN ('waiting', 'running')
        ORDER BY r.created_at DESC
        """,
    )
    return [_parse_public_run_list_item_row(row) for row in rows]


async def get_run_pending_join_count(run_id: str) -> int:
    row = await db.fetchone(
        """
        SELECT COUNT(*) AS pending_join_count
        FROM hexarena.join_requests
        WHERE run_id = :run_id AND status = 'pending_payment'
        """,
        {"run_id": run_id},
    )
    return int((row or {}).get("pending_join_count") or 0)


async def get_run_active_agent_count(run_id: str) -> int:
    row = await db.fetchone(
        """
        SELECT COUNT(*) AS active_agent_count
        FROM hexarena.agents
        WHERE run_id = :run_id AND status = 'active'
        """,
        {"run_id": run_id},
    )
    return int((row or {}).get("active_agent_count") or 0)


async def get_waiting_runs() -> list[GameRun]:
    rows = await db.fetchall(
        """
        SELECT * FROM hexarena.game_runs
        WHERE status = 'waiting'
        ORDER BY created_at ASC
        """,
    )
    return [_parse_game_run_row(row) for row in rows]


async def get_running_runs() -> list[GameRun]:
    rows = await db.fetchall(
        """
        SELECT * FROM hexarena.game_runs
        WHERE status = 'running'
        ORDER BY started_at ASC, created_at ASC
        """,
    )
    return [_parse_game_run_row(row) for row in rows]


async def get_finished_runs() -> list[GameRun]:
    rows = await db.fetchall(
        """
        SELECT * FROM hexarena.game_runs
        WHERE status = 'finished'
        ORDER BY finished_at DESC, created_at DESC
        """
    )
    return [_parse_game_run_row(row) for row in rows]


async def update_game_run(data: GameRun) -> GameRun:
    updated = data.copy(update={"updated_at": utc_now()})
    await db.update("hexarena.game_runs", _prepare_run_for_storage(updated))
    return updated


async def delete_game_run(run_id: str) -> None:
    await db.execute(
        "DELETE FROM hexarena.join_requests WHERE run_id = :run_id",
        {"run_id": run_id},
    )
    await db.execute("DELETE FROM hexarena.actions WHERE run_id = :run_id", {"run_id": run_id})
    await db.execute("DELETE FROM hexarena.agents WHERE run_id = :run_id", {"run_id": run_id})
    await db.execute("DELETE FROM hexarena.game_runs WHERE id = :id", {"id": run_id})


############################ Agents ############################
async def create_agent(
    run_id: str,
    data: CreateAgent,
    *,
    status: str = "pending",
    api_key: str | None = None,
) -> Agent:
    now = utc_now()
    agent = Agent(
        id=urlsafe_short_hash(),
        run_id=run_id,
        display_name=data.display_name,
        status=status,
        api_key=api_key,
        payment_hash=getattr(data, "payment_hash", None),
        payment_request=getattr(data, "payment_request", None),
        payout_request=getattr(data, "payout_request", None),
        profile=data.profile,
        inventory=[],
        joined_at=now if status == "active" else None,
        created_at=now,
        updated_at=now,
    )
    await db.insert("hexarena.agents", agent)
    return agent


async def get_agent(run_id: str, agent_id: str) -> Agent | None:
    return await db.fetchone(
        "SELECT * FROM hexarena.agents WHERE id = :id AND run_id = :run_id",
        {"id": agent_id, "run_id": run_id},
        Agent,
    )


async def get_agent_by_id(agent_id: str) -> Agent | None:
    return await db.fetchone(
        "SELECT * FROM hexarena.agents WHERE id = :id",
        {"id": agent_id},
        Agent,
    )


async def get_agent_by_api_key(run_id: str, api_key: str) -> Agent | None:
    return await db.fetchone(
        """
        SELECT * FROM hexarena.agents
        WHERE run_id = :run_id AND api_key = :api_key
        """,
        {"run_id": run_id, "api_key": api_key},
        Agent,
    )


async def get_agent_by_payout_hash(payout_unique_hash: str) -> Agent | None:
    return await db.fetchone(
        """
        SELECT * FROM hexarena.agents
        WHERE payout_unique_hash = :payout_unique_hash
        """,
        {"payout_unique_hash": payout_unique_hash},
        Agent,
    )


async def get_agents_paginated(
    run_ids: list[str] | None = None,
    filters: Filters[AgentFilters] | None = None,
) -> Page[Agent]:
    if not run_ids:
        return Page(data=[], total=0)

    values = {}
    ids = []
    for i, run_id in enumerate(run_ids):
        key = f"run_id__{i}"
        ids.append(f"run_id = :{key}")
        values[key] = run_id

    return await db.fetch_page(
        "SELECT * FROM hexarena.agents",
        where=[f"({' OR '.join(ids)})"],
        values=values,
        filters=filters,
        model=Agent,
        table_name="hexarena.agents",
    )


async def get_agents_for_run(run_id: str, *, active_only: bool = False) -> list[Agent]:
    where = "WHERE run_id = :run_id"
    if active_only:
        where += " AND status = 'active'"
    return await db.fetchall(
        f"""
        SELECT * FROM hexarena.agents
        {where}
        ORDER BY created_at ASC
        """,
        {"run_id": run_id},
        Agent,
    )


async def update_agent(data: Agent) -> Agent:
    updated = data.copy(update={"updated_at": utc_now()})
    await db.update("hexarena.agents", updated)
    return updated


async def delete_agent(run_id: str, agent_id: str) -> None:
    await db.execute(
        "DELETE FROM hexarena.agents WHERE id = :id AND run_id = :run_id",
        {"id": agent_id, "run_id": run_id},
    )


############################ Join Requests ############################
async def create_join_request(
    run_id: str,
    *,
    join_request_id: str | None = None,
    claim_token: str | None = None,
    display_name: str | None = None,
    profile: dict | None = None,
    payment_hash: str | None = None,
    payment_request: str | None = None,
    expires_at: datetime | None = None,
) -> JoinRequest:
    now = utc_now()
    join_request = JoinRequest(
        id=join_request_id or urlsafe_short_hash(),
        run_id=run_id,
        status="pending_payment",
        paid=False,
        claim_token=claim_token,
        display_name=display_name,
        profile=profile or {},
        payment_hash=payment_hash,
        payment_request=payment_request,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    await db.insert("hexarena.join_requests", join_request)
    return join_request


async def get_join_request(join_request_id: str) -> JoinRequest | None:
    return await db.fetchone(
        "SELECT * FROM hexarena.join_requests WHERE id = :id",
        {"id": join_request_id},
        JoinRequest,
    )


async def get_join_request_by_payment_hash(payment_hash: str) -> JoinRequest | None:
    return await db.fetchone(
        """
        SELECT * FROM hexarena.join_requests
        WHERE payment_hash = :payment_hash
        """,
        {"payment_hash": payment_hash},
        JoinRequest,
    )


async def get_join_request_for_user(
    user_id: str,
    join_request_id: str,
) -> JoinRequest | None:
    return await db.fetchone(
        """
        SELECT jr.* FROM hexarena.join_requests jr
        JOIN hexarena.game_runs r ON r.id = jr.run_id
        JOIN hexarena.games g ON g.id = r.game_id
        WHERE jr.id = :id AND g.user_id = :user_id
        """,
        {"id": join_request_id, "user_id": user_id},
        JoinRequest,
    )


async def get_join_requests_paginated(
    run_ids: list[str] | None = None,
    filters: Filters[JoinRequestFilters] | None = None,
) -> Page[JoinRequest]:
    if not run_ids:
        return Page(data=[], total=0)

    values = {}
    ids = []
    for i, run_id in enumerate(run_ids):
        key = f"run_id__{i}"
        ids.append(f"run_id = :{key}")
        values[key] = run_id

    return await db.fetch_page(
        "SELECT * FROM hexarena.join_requests",
        where=[f"({' OR '.join(ids)})"],
        values=values,
        filters=filters,
        model=JoinRequest,
        table_name="hexarena.join_requests",
    )


async def update_join_request(data: JoinRequest) -> JoinRequest:
    updated = data.copy(update={"updated_at": utc_now()})
    await db.update("hexarena.join_requests", updated)
    return updated


async def get_expired_pending_join_requests(now: datetime | None = None) -> list[JoinRequest]:
    ref = now or utc_now()
    return await db.fetchall(
        f"""
        SELECT * FROM hexarena.join_requests
        WHERE status = 'pending_payment'
        AND expires_at IS NOT NULL
        AND expires_at <= {db.timestamp_placeholder('expires_at')}
        """,
        {"expires_at": ref},
        JoinRequest,
    )


############################ Actions ############################
async def create_action(
    run_id: str,
    agent_id: str | None,
    data: CreateAction,
    *,
    status: str = "queued",
) -> Action:
    phase = "group2" if data.payload.type in {"talk", "whisper"} else data.phase
    action = Action(
        id=urlsafe_short_hash(),
        run_id=run_id,
        agent_id=agent_id,
        turn=data.turn,
        phase=phase,
        action_type=data.payload.type,
        status=status,
        target_hex=data.payload.target_hex,
        from_hex=data.payload.from_hex,
        to_hex=data.payload.to_hex,
        target_agent_id=data.payload.target_agent,
        powerup_type=data.payload.powerup_type,
        amount=data.payload.amount,
        message=data.payload.message,
        thought=data.thought,
        payload=data.payload.dict(exclude_none=True, by_alias=True),
        created_at=utc_now(),
    )
    await db.insert("hexarena.actions", action)
    return action


async def get_action(action_id: str) -> Action | None:
    return await db.fetchone(
        "SELECT * FROM hexarena.actions WHERE id = :id",
        {"id": action_id},
        Action,
    )


async def get_actions_paginated(
    run_ids: list[str] | None = None,
    filters: Filters[ActionFilters] | None = None,
) -> Page[Action]:
    if not run_ids:
        return Page(data=[], total=0)

    values = {}
    ids = []
    for i, run_id in enumerate(run_ids):
        key = f"run_id__{i}"
        ids.append(f"run_id = :{key}")
        values[key] = run_id

    return await db.fetch_page(
        "SELECT * FROM hexarena.actions",
        where=[f"({' OR '.join(ids)})"],
        values=values,
        filters=filters,
        model=Action,
        table_name="hexarena.actions",
    )


async def get_actions_for_run(run_id: str) -> list[Action]:
    return await db.fetchall(
        """
        SELECT * FROM hexarena.actions
        WHERE run_id = :run_id
        ORDER BY turn ASC, resolution_order ASC, created_at ASC
        """,
        {"run_id": run_id},
        Action,
    )


async def get_actions_for_turn(run_id: str, turn: int) -> list[Action]:
    return await db.fetchall(
        """
        SELECT * FROM hexarena.actions
        WHERE run_id = :run_id AND turn = :turn
        ORDER BY created_at ASC
        """,
        {"run_id": run_id, "turn": turn},
        Action,
    )


async def update_action(data: Action) -> Action:
    await db.update("hexarena.actions", data)
    return data
