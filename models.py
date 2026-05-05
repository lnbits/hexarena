from datetime import datetime, timezone
from typing import Any

from lnbits.db import FilterModel
from pydantic import BaseModel, Field


class HexArenaBaseModel(BaseModel):
    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class GameConfig(HexArenaBaseModel):
    min_players: int = Field(default=2, ge=2)
    max_players: int = Field(default=8, ge=2)
    poll_interval_sec: int = Field(default=10, ge=10, le=60)
    auto_start_after_sec: int | None = Field(default=None, ge=0)
    max_rounds: int = Field(default=120, ge=1)
    entry_fee_sats: int = Field(default=0, ge=0)
    base_hex_count: int = Field(default=40, ge=1)
    power_growth_every_n_turns: int = Field(default=10, ge=1)
    powerup_spawn_every_n_turns: int = Field(default=12, ge=1)
    starting_power_new_hex: int = Field(default=1, ge=0, le=10)
    payout_scheme: str = "winner_takes_all"
    enable_fortify: bool = True
    pot_rollover: bool = False
    house_fee_percent: float = Field(default=0.0, ge=0, le=100)
    terrain_distribution: dict[str, int] = Field(default_factory=dict)
    powerup_types_enabled: list[str] = Field(default_factory=list)


class HexThought(HexArenaBaseModel):
    reasoning: str | None = None
    planned: str | None = None


class HexTile(HexArenaBaseModel):
    id: str
    q: int
    r: int
    owner: str | None = None
    power: int = Field(default=0, ge=0, le=10)
    power_next_growth_in_turns: int | None = Field(
        default=None, ge=0, alias="powerNextGrowthInTurns"
    )
    defense_mod: float = Field(default=0.0, alias="defenseMod")
    terrain: str = "plains"
    adjacent: list[str] = Field(default_factory=list)


class MapPowerUp(HexArenaBaseModel):
    hex_id: str = Field(alias="hexId")
    type: str
    claimed: bool = False


class AgentStanding(HexArenaBaseModel):
    id: str
    display_name: str | None = Field(default=None, alias="displayName")
    hex_count: int = Field(default=0, ge=0, alias="hexCount")
    total_power: int = Field(default=0, ge=0, alias="totalPower")
    eliminated: bool = False


class LeaderboardEntry(HexArenaBaseModel):
    agent_id: str = Field(alias="agentId")
    display_name: str | None = Field(default=None, alias="displayName")
    hexes: int = Field(default=0, ge=0)
    total_power: int = Field(default=0, ge=0, alias="totalPower")
    rank: int = Field(default=1, ge=1)


class PublicActionLog(HexArenaBaseModel):
    id: str | None = None
    type: str
    agent_id: str | None = Field(default=None, alias="agentId")
    target_hex: str | None = Field(default=None, alias="targetHex")
    message: str | None = None
    outcome: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class GameState(HexArenaBaseModel):
    game_id: str = Field(alias="gameId")
    status: str
    turn: int = Field(default=0, ge=0)
    poll_interval_sec: int = Field(default=10, ge=1, alias="pollIntervalSec")
    hexes: list[HexTile] = Field(default_factory=list)
    power_ups: list[MapPowerUp] = Field(default_factory=list, alias="powerUps")
    agents: list[AgentStanding] = Field(default_factory=list)
    my_agent_id: str | None = Field(default=None, alias="myAgentId")
    my_hexes: list[str] = Field(default_factory=list, alias="myHexes")
    my_power_ups: list[str] = Field(default_factory=list, alias="myPowerUps")
    leaderboard: list[LeaderboardEntry] = Field(default_factory=list)
    recent_actions: list[PublicActionLog] = Field(
        default_factory=list, alias="recentActions"
    )
    next_power_up_spawn_in_turns: int | None = Field(
        default=None, ge=0, alias="nextPowerUpSpawnInTurns"
    )


############################ Games ############################
class CreateGame(BaseModel):
    name: str
    wallet_id: str
    fee_wallet_id: str | None = None
    status: str = "draft"
    default_config: GameConfig = Field(default_factory=GameConfig)


class UpdateGame(BaseModel):
    name: str | None = None
    wallet_id: str | None = None
    fee_wallet_id: str | None = None
    status: str | None = None
    default_config: GameConfig | None = None
    latest_run_id: str | None = None


class Game(BaseModel):
    id: str
    user_id: str
    wallet_id: str
    fee_wallet_id: str | None = None
    name: str
    status: str
    default_config: GameConfig = Field(default_factory=GameConfig)
    latest_run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublicGame(BaseModel):
    id: str
    name: str
    status: str
    default_config: GameConfig = Field(default_factory=GameConfig)
    latest_run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GameFilters(FilterModel):
    __search_fields__ = ["name", "status", "wallet_id", "latest_run_id"]
    __sort_fields__ = [
        "name",
        "status",
        "wallet_id",
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None = None
    updated_at: datetime | None = None


############################ Game Runs ############################
class CreateGameRun(BaseModel):
    status: str = "waiting"
    config: GameConfig | None = None
    initial_state: GameState | None = None
    current_state: GameState | None = None
    turn: int = Field(default=0, ge=0)
    winner_agent_id: str | None = None
    prize_pool_sats: int = Field(default=0, ge=0)
    house_fee_sats: int = Field(default=0, ge=0)
    tribute_fee_sats: int = Field(default=0, ge=0)
    payouts_total_sats: int = Field(default=0, ge=0)
    fee_status: str = "none"
    fees_settled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class UpdateGameRun(BaseModel):
    status: str | None = None
    config: GameConfig | None = None
    initial_state: GameState | None = None
    current_state: GameState | None = None
    turn: int | None = Field(default=None, ge=0)
    winner_agent_id: str | None = None
    prize_pool_sats: int | None = Field(default=None, ge=0)
    house_fee_sats: int | None = Field(default=None, ge=0)
    tribute_fee_sats: int | None = Field(default=None, ge=0)
    payouts_total_sats: int | None = Field(default=None, ge=0)
    fee_status: str | None = None
    fees_settled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class FinishRunRequest(BaseModel):
    winner_agent_id: str | None = None


class SettlePayoutRequest(BaseModel):
    payment_request: str


class GameRun(BaseModel):
    id: str
    game_id: str
    status: str
    config: GameConfig = Field(default_factory=GameConfig)
    initial_state: GameState = Field(
        default_factory=lambda: GameState(game_id="", status="waiting")
    )
    current_state: GameState = Field(
        default_factory=lambda: GameState(game_id="", status="waiting")
    )
    turn: int = Field(default=0, ge=0)
    winner_agent_id: str | None = None
    prize_pool_sats: int = Field(default=0, ge=0)
    house_fee_sats: int = Field(default=0, ge=0)
    tribute_fee_sats: int = Field(default=0, ge=0)
    payouts_total_sats: int = Field(default=0, ge=0)
    fee_status: str = "none"
    fees_settled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublicGameRun(BaseModel):
    id: str
    game_id: str
    status: str
    config: GameConfig = Field(default_factory=GameConfig)
    turn: int = Field(default=0, ge=0)
    winner_agent_id: str | None = None
    active_agent_count: int = Field(default=0, ge=0)
    pending_join_count: int = Field(default=0, ge=0)
    occupied_seats: int = Field(default=0, ge=0)
    open_seats: int = Field(default=0, ge=0)
    needs_players: int = Field(default=0, ge=0)
    can_start_now: bool = False
    starts_on_join: bool = False
    prize_pool_sats: int = Field(default=0, ge=0)
    house_fee_sats: int = Field(default=0, ge=0)
    tribute_fee_sats: int = Field(default=0, ge=0)
    payouts_total_sats: int = Field(default=0, ge=0)
    fee_status: str = "none"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublicRunListItem(BaseModel):
    id: str
    game_id: str
    game_name: str
    game_status: str
    run_status: str
    config: GameConfig = Field(default_factory=GameConfig)
    turn: int = Field(default=0, ge=0)
    winner_agent_id: str | None = None
    active_agent_count: int = Field(default=0, ge=0)
    pending_join_count: int = Field(default=0, ge=0)
    occupied_seats: int = Field(default=0, ge=0)
    open_seats: int = Field(default=0, ge=0)
    needs_players: int = Field(default=0, ge=0)
    can_start_now: bool = False
    starts_on_join: bool = False
    prize_pool_sats: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReplayResponse(BaseModel):
    game: PublicGame
    run: PublicGameRun
    initial_state: GameState
    actions: list["Action"] = Field(default_factory=list)


class GameRunFilters(FilterModel):
    __search_fields__ = ["game_id", "status", "winner_agent_id"]
    __sort_fields__ = [
        "status",
        "turn",
        "prize_pool_sats",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    turn: int | None = None
    prize_pool_sats: int | None = None


############################ Agents ############################
class CreateAgent(BaseModel):
    display_name: str | None = None
    payment_hash: str | None = None
    payment_request: str | None = None
    payout_request: str | None = None
    profile: dict = Field(default_factory=dict)


class UpdateAgent(BaseModel):
    display_name: str | None = None
    status: str | None = None
    api_key: str | None = None
    payment_hash: str | None = None
    payment_request: str | None = None
    payout_request: str | None = None
    profile: dict | None = None
    inventory: list[str] | None = None
    payout_amount_sats: int | None = Field(default=None, ge=0)
    payout_status: str | None = None
    payout_unique_hash: str | None = None
    payout_k1: str | None = None
    payout_payment_hash: str | None = None
    payout_settled_at: datetime | None = None
    start_hex_id: str | None = None
    is_eliminated: bool | None = None
    eliminated_turn: int | None = None
    last_action_turn: int | None = None
    last_seen_at: datetime | None = None
    joined_at: datetime | None = None


class Agent(BaseModel):
    id: str
    run_id: str
    display_name: str | None = None
    status: str
    api_key: str | None = None
    payment_hash: str | None = None
    payment_request: str | None = None
    payout_request: str | None = None
    profile: dict = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    payout_amount_sats: int = Field(default=0, ge=0)
    payout_status: str = "none"
    payout_unique_hash: str | None = None
    payout_k1: str | None = None
    payout_payment_hash: str | None = None
    payout_settled_at: datetime | None = None
    start_hex_id: str | None = None
    is_eliminated: bool = False
    eliminated_turn: int | None = None
    last_action_turn: int | None = None
    last_seen_at: datetime | None = None
    joined_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublicAgent(BaseModel):
    id: str
    run_id: str
    display_name: str | None = None
    status: str
    inventory: list[str] = Field(default_factory=list)
    payout_amount_sats: int = Field(default=0, ge=0)
    payout_status: str = "none"
    start_hex_id: str | None = None
    is_eliminated: bool = False
    eliminated_turn: int | None = None
    last_action_turn: int | None = None
    joined_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JoinRunResponse(BaseModel):
    join_request_id: str | None = None
    agent_id: str | None = None
    run_id: str
    status: str
    paid: bool = False
    payment_required: bool = False
    credentials_ready: bool = False
    api_key: str | None = None
    payment_hash: str | None = None
    payment_request: str | None = None
    expires_at: datetime | None = None


class AgentPayoutResponse(BaseModel):
    run_id: str
    agent_id: str
    status: str
    payout_amount_sats: int = Field(default=0, ge=0)
    payout_request: str | None = None
    payout_settled_at: datetime | None = None
    lnurl: str | None = None
    url: str | None = None


class CreateJoinRequest(BaseModel):
    display_name: str | None = None
    profile: dict = Field(default_factory=dict)


class JoinRequest(BaseModel):
    id: str
    run_id: str
    status: str
    paid: bool = False
    claim_token: str | None = None
    display_name: str | None = None
    profile: dict = Field(default_factory=dict)
    payment_hash: str | None = None
    payment_request: str | None = None
    agent_id: str | None = None
    expires_at: datetime | None = None
    settled_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JoinRequestFilters(FilterModel):
    __search_fields__ = ["run_id", "status", "display_name", "payment_hash", "agent_id"]
    __sort_fields__ = [
        "run_id",
        "status",
        "paid",
        "display_name",
        "expires_at",
        "settled_at",
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    settled_at: datetime | None = None
    paid: bool | None = None


class AgentFilters(FilterModel):
    __search_fields__ = ["run_id", "display_name", "status", "payment_hash"]
    __sort_fields__ = [
        "run_id",
        "display_name",
        "status",
        "is_eliminated",
        "last_action_turn",
        "joined_at",
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None = None
    updated_at: datetime | None = None
    joined_at: datetime | None = None
    last_action_turn: int | None = None
    is_eliminated: bool | None = None


############################ Actions ############################
class ActionPayload(HexArenaBaseModel):
    type: str
    target_hex: str | None = Field(default=None, alias="targetHex")
    from_hex: str | None = Field(default=None, alias="fromHex")
    to_hex: str | None = Field(default=None, alias="toHex")
    amount: int | None = Field(default=None, ge=1, le=3)
    powerup_type: str | None = Field(default=None, alias="powerupType")
    target_agent: str | None = Field(default=None, alias="targetAgent")
    message: str | None = None


class CreateAction(BaseModel):
    turn: int = Field(default=0, ge=0)
    phase: str = "group1"
    payload: ActionPayload
    thought: HexThought = Field(default_factory=HexThought)


class Action(BaseModel):
    id: str
    run_id: str
    agent_id: str | None = None
    turn: int = Field(default=0, ge=0)
    phase: str
    action_type: str
    status: str
    target_hex: str | None = None
    from_hex: str | None = None
    to_hex: str | None = None
    target_agent_id: str | None = None
    powerup_type: str | None = None
    amount: int | None = None
    message: str | None = None
    thought: HexThought = Field(default_factory=HexThought)
    payload: dict = Field(default_factory=dict)
    outcome: dict = Field(default_factory=dict)
    resolution_order: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActionFilters(FilterModel):
    __search_fields__ = ["run_id", "agent_id", "phase", "action_type", "status"]
    __sort_fields__ = [
        "turn",
        "phase",
        "action_type",
        "status",
        "resolution_order",
        "created_at",
    ]

    created_at: datetime | None = None
    resolved_at: datetime | None = None
    turn: int | None = None
    resolution_order: int | None = None


ReplayResponse.update_forward_refs()
