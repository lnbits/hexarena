import json
import asyncio
from datetime import datetime, timedelta, timezone
from math import floor

from lnbits.core.crud.payments import get_standalone_payment
from lnbits.core.models import Payment
from lnbits.core.services import (
    create_invoice,
    get_pr_from_lnurl,
    pay_invoice,
    websocket_updater,
)
from loguru import logger

from .crud import (
    create_agent,
    create_game_run,
    create_join_request,
    generate_api_key,
    get_actions_for_turn,
    get_agent_by_id,
    get_agent_by_payout_hash,
    get_agents_for_run,
    get_finished_runs,
    get_game_by_id,
    get_game_run,
    get_run_active_agent_count,
    get_run_pending_join_count,
    get_join_request,
    get_join_request_by_payment_hash,
    get_running_runs,
    get_waiting_runs,
    update_action,
    update_agent,
    update_game_run,
    update_join_request,
)
from .engine import bootstrap_run_state, resolve_turn, should_auto_start_run
from .models import (
    Agent,
    AgentPayoutResponse,
    CreateAgent,
    CreateGameRun,
    CreateJoinRequest,
    GameRun,
    JoinRunResponse,
    JoinRequest,
)
from .realtime import (
    publish_public_run_event,
    publish_admin_event_for_game,
    publish_admin_event_for_join_request,
    publish_admin_event_for_run,
)
from lnbits.helpers import urlsafe_short_hash
from secrets import token_urlsafe

JOIN_REQUEST_TTL_SECONDS = 60
RUN_RESPAWN_COOLDOWN_SECONDS = 60
LNBITS_TRIBUTE_PERCENT = 0.5
LNBITS_TRIBUTE_ADDRESS = "lnbits@nostr.com"
join_request_locks: dict[str, asyncio.Lock] = {}
payout_locks: dict[str, asyncio.Lock] = {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def create_join_flow(run_id: str, data: CreateJoinRequest) -> JoinRunResponse:
    run = await require_joinable_run(run_id)

    if run.config.entry_fee_sats <= 0:
        agent = await create_agent(
            run_id,
            CreateAgent(
                display_name=data.display_name,
                profile=data.profile,
            ),
            status="active",
            api_key=generate_api_key(),
        )
        await publish_admin_event_for_run(run_id, scope="agents", event="joined")
        await publish_public_run_event(run_id, event="agent_joined")
        return JoinRunResponse(
            run_id=run_id,
            agent_id=agent.id,
            status=agent.status,
            paid=False,
            payment_required=False,
            credentials_ready=True,
            api_key=agent.api_key,
        )

    join_request = await create_paid_join_request(run_id, data)

    return JoinRunResponse(
        join_request_id=join_request.id,
        run_id=run_id,
        status=join_request.status,
        paid=False,
        payment_required=True,
        credentials_ready=False,
        payment_hash=join_request.payment_hash,
        payment_request=join_request.payment_request,
        expires_at=join_request.expires_at,
    )


async def create_paid_join_request(
    run_id: str,
    data: CreateJoinRequest,
    *,
    memo: str | None = None,
    unhashed_description: bytes | None = None,
    extra: dict | None = None,
) -> JoinRequest:
    run = await require_joinable_run(run_id)
    if run.config.entry_fee_sats <= 0:
        raise ValueError("Run does not require payment.")

    join_request_id = urlsafe_short_hash()
    claim_token = token_urlsafe(24)
    payment = await create_invoice(
        wallet_id=(await _get_run_wallet_id(run_id)),
        amount=run.config.entry_fee_sats,
        memo=memo or f"HexArena join {run_id}",
        unhashed_description=unhashed_description,
        extra={
            "tag": "hexarena_join",
            "run_id": run_id,
            "join_request_id": join_request_id,
            "display_name": data.display_name,
            **(extra or {}),
        },
    )

    join_request = await create_join_request(
        run_id,
        join_request_id=join_request_id,
        claim_token=claim_token,
        display_name=data.display_name,
        profile=data.profile,
        payment_hash=payment.payment_hash,
        payment_request=payment.bolt11,
        expires_at=utc_now() + timedelta(seconds=JOIN_REQUEST_TTL_SECONDS),
    )
    await publish_admin_event_for_run(run_id, scope="join_requests", event="created")
    return join_request


async def get_join_flow_status(join_request_id: str) -> JoinRunResponse | None:
    return await get_public_join_flow_status(join_request_id)


async def get_public_join_flow_status(
    join_request_id: str, claim_token: str | None = None
) -> JoinRunResponse | None:
    join_request = await get_join_request(join_request_id)
    if not join_request:
        return None

    if join_request.agent_id:
        agent = await get_agent_by_id(join_request.agent_id)
        include_credentials = bool(
            claim_token and join_request.claim_token and claim_token == join_request.claim_token
        )
        return JoinRunResponse(
            join_request_id=join_request.id,
            run_id=join_request.run_id,
            agent_id=join_request.agent_id if include_credentials else None,
            status=join_request.status,
            paid=join_request.paid,
            payment_required=bool(join_request.payment_hash),
            credentials_ready=bool(join_request.agent_id),
            api_key=agent.api_key if include_credentials and agent else None,
            payment_hash=join_request.payment_hash,
            payment_request=join_request.payment_request,
            expires_at=join_request.expires_at,
        )

    if join_request.payment_hash:
        payment = await get_standalone_payment(join_request.payment_hash, incoming=True)
        if payment and payment.success:
            join_request = await settle_join_request(join_request)

    return JoinRunResponse(
        join_request_id=join_request.id,
        run_id=join_request.run_id,
        agent_id=None,
        status=join_request.status,
        paid=join_request.paid,
        payment_required=bool(join_request.payment_hash),
        credentials_ready=bool(join_request.agent_id),
        payment_hash=join_request.payment_hash,
        payment_request=join_request.payment_request,
        expires_at=join_request.expires_at,
        api_key=None,
    )


async def settle_join_request(join_request: JoinRequest) -> JoinRequest:
    lock = join_request_locks.setdefault(join_request.id, asyncio.Lock())
    async with lock:
        current = await get_join_request(join_request.id)
        if not current:
            raise ValueError("Join request not found.")
        if current.agent_id:
            return current

        agent = await create_agent(
            current.run_id,
            CreateAgent(
                display_name=current.display_name,
                profile=current.profile,
            ),
            status="active",
            api_key=generate_api_key(),
        )
        current.status = "completed"
        current.paid = True
        current.agent_id = agent.id
        current.settled_at = utc_now()
        run = await get_game_run(current.run_id)
        if run and run.config.entry_fee_sats > 0:
            await update_game_run(
                run.copy(
                    update={
                        "prize_pool_sats": run.prize_pool_sats + run.config.entry_fee_sats
                    }
                )
            )
        updated = await update_join_request(current)
        await publish_join_request_update(updated)
        await publish_admin_event_for_join_request(updated.id, event="settled")
        await publish_public_run_event(updated.run_id, event="agent_joined")
        return updated


async def expire_stale_join_requests() -> int:
    from .crud import get_expired_pending_join_requests

    expired = await get_expired_pending_join_requests()
    count = 0
    for join_request in expired:
        if join_request.status != "pending_payment":
            continue
        join_request.status = "expired"
        updated = await update_join_request(join_request)
        await publish_join_request_update(updated)
        await publish_admin_event_for_join_request(updated.id, event="expired")
        count += 1
    return count


async def payment_received_for_player(payment: Payment) -> bool:
    if not payment.extra or payment.extra.get("tag") != "hexarena_join":
        return False

    join_request_id = payment.extra.get("join_request_id")
    join_request = (
        await get_join_request(join_request_id)
        if join_request_id
        else await get_join_request_by_payment_hash(payment.payment_hash)
    )
    if not join_request:
        logger.warning(f"No join request found for payment {payment.payment_hash}.")
        return False

    await settle_join_request(join_request)
    logger.info(
        f"Activated HexArena join request {join_request.id} for payment {payment.payment_hash}."
    )
    return True


async def _get_agent_api_key(agent_id: str | None) -> str | None:
    if not agent_id:
        return None
    agent = await get_agent_by_id(agent_id)
    return agent.api_key if agent else None


async def _get_run_wallet_id(run_id: str) -> str:
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Run not found.")

    game = await get_game_by_id(run.game_id)
    if not game:
        raise ValueError("Game not found for run.")
    return game.wallet_id


async def _get_run_fee_wallet_id(run_id: str) -> str | None:
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Run not found.")
    game = await get_game_by_id(run.game_id)
    if not game:
        raise ValueError("Game not found for run.")
    return game.fee_wallet_id


async def require_joinable_run(run_id: str):
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Invalid run ID.")
    if run.status != "waiting":
        raise ValueError("Run is not accepting joins.")
    active_agent_count = await get_run_active_agent_count(run_id)
    pending_join_count = await get_run_pending_join_count(run_id)
    occupied_seats = active_agent_count + pending_join_count
    if occupied_seats >= run.config.max_players:
        raise ValueError("Run is full.")
    return run


async def publish_join_request_update(join_request: JoinRequest) -> None:
    await websocket_updater(
        join_request.id,
        json.dumps(
            {
                "join_request_id": join_request.id,
                "run_id": join_request.run_id,
                "status": join_request.status,
                "paid": join_request.paid,
                "agent_id": join_request.agent_id,
            }
        ),
    )


async def initialize_run(run_id: str) -> None:
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Run not found.")
    if run.status != "waiting":
        raise ValueError("Only waiting runs can be initialized.")

    agents = await get_agents_for_run(run_id, active_only=True)
    if len(agents) < run.config.min_players:
        raise ValueError("Not enough active agents to start run.")

    initialized = bootstrap_run_state(run, agents)
    await update_game_run(initialized)
    await publish_admin_event_for_run(run_id, event="started")
    await publish_public_run_event(run_id, event="started")


async def auto_start_waiting_runs() -> int:
    started = 0
    for run in await get_waiting_runs():
        agents = await get_agents_for_run(run.id, active_only=True)
        if should_auto_start_run(run, len(agents)):
            await update_game_run(bootstrap_run_state(run, agents))
            await publish_admin_event_for_run(run.id, event="started")
            await publish_public_run_event(run.id, event="started")
            started += 1
    return started


async def ensure_waiting_runs_for_finished_games(
    *, cooldown_seconds: int = RUN_RESPAWN_COOLDOWN_SECONDS
) -> int:
    spawned = 0
    now = utc_now()
    waiting_game_ids = {run.game_id for run in await get_waiting_runs()}
    respawned_game_ids: set[str] = set()

    for run in await get_finished_runs():
        if run.game_id in waiting_game_ids or run.game_id in respawned_game_ids:
            continue
        if not run.finished_at:
            continue
        if (now - run.finished_at).total_seconds() < cooldown_seconds:
            continue

        game = await get_game_by_id(run.game_id)
        if not game:
            continue

        await create_game_run(
            game,
            CreateGameRun(
                status="waiting",
                config=run.config.copy(deep=True),
            ),
        )
        await publish_admin_event_for_game(game.id, scope="runs", event="spawned")
        waiting_game_ids.add(run.game_id)
        respawned_game_ids.add(run.game_id)
        spawned += 1

    return spawned


def is_turn_due(run, now: datetime | None = None) -> bool:
    if run.status != "running" or not run.started_at:
        return False
    now = now or utc_now()
    deadline = run.started_at + timedelta(seconds=run.turn * run.config.poll_interval_sec)
    return now >= deadline


async def process_run_turn(run_id: str) -> bool:
    run = await get_game_run(run_id)
    if not run or run.status != "running":
        return False
    if not is_turn_due(run):
        return False

    agents = await get_agents_for_run(run_id)
    actions = await get_actions_for_turn(run_id, run.turn)
    updated_run, updated_agents, updated_actions = resolve_turn(run, agents, actions)
    if updated_run.status == "finished":
        updated_run = await settle_run_fees(updated_run)
        updated_agents = await prepare_run_payouts(updated_run, updated_agents)

    await update_game_run(updated_run)
    for agent in updated_agents:
        await update_agent(agent)
    for action in updated_actions:
        await update_action(action)
    await publish_admin_event_for_run(run_id, event="turn_processed")
    await publish_public_run_event(
        run_id,
        event="finished" if updated_run.status == "finished" else "turn_processed",
    )
    return True


async def process_due_running_runs(*, max_turns_per_run: int = 3) -> int:
    processed = 0
    for run in await get_running_runs():
        turns_processed = 0
        while turns_processed < max_turns_per_run and await process_run_turn(run.id):
            processed += 1
            turns_processed += 1
            run = await get_game_run(run.id)
            if not run:
                break
    return processed


def calculate_payout_amounts(run, agents: list[Agent]) -> dict[str, int]:
    standings = [
        standing for standing in (run.current_state.agents or []) if standing.hex_count > 0
    ]
    if not standings or run.prize_pool_sats <= 0:
        return {}

    distributable = run.payouts_total_sats or calculate_fee_breakdown(run)["payouts_total_sats"]
    if distributable <= 0:
        return {}

    ranked_agent_ids = [standing.id for standing in standings]
    scheme = run.config.payout_scheme or "winner_takes_all"
    if scheme == "winner_takes_all":
        return {ranked_agent_ids[0]: distributable}

    if scheme == "top_3_60_30_10":
        winners = ranked_agent_ids[:3]
        weights = [60, 30, 10][: len(winners)]
        payouts: dict[str, int] = {}
        allocated = 0
        for agent_id, weight in zip(winners, weights):
            amount = floor(distributable * weight / 100)
            payouts[agent_id] = amount
            allocated += amount
        if winners and allocated < distributable:
            payouts[winners[0]] += distributable - allocated
        return {agent_id: amount for agent_id, amount in payouts.items() if amount > 0}

    return {ranked_agent_ids[0]: distributable}


async def prepare_run_payouts(run, agents: list[Agent]) -> list[Agent]:
    if run.status != "finished":
        return agents

    payout_amounts = calculate_payout_amounts(run, agents)
    updated_agents: list[Agent] = []
    for agent in agents:
        current_status = agent.payout_status or "none"
        if current_status == "paid":
            updated_agents.append(agent)
            continue
        payout_amount = payout_amounts.get(agent.id, 0)
        if payout_amount <= 0:
            updated_agents.append(
                agent.copy(
                    update={
                        "payout_amount_sats": 0,
                        "payout_status": "none",
                        "payout_unique_hash": None,
                        "payout_k1": None,
                    }
                )
            )
            continue
        updated_agents.append(
            agent.copy(
                update={
                    "payout_amount_sats": payout_amount,
                    "payout_status": current_status
                    if current_status in {"pending_claim", "paid"}
                    else "pending_claim",
                    "payout_unique_hash": agent.payout_unique_hash or token_urlsafe(24),
                    "payout_k1": agent.payout_k1 or token_urlsafe(24),
                }
            )
        )
    return updated_agents


def calculate_fee_breakdown(run) -> dict[str, int]:
    gross_pool = max(0, run.prize_pool_sats)
    house_fee_sats = floor(gross_pool * max(0.0, run.config.house_fee_percent) / 100.0)
    tribute_fee_sats = floor(gross_pool * LNBITS_TRIBUTE_PERCENT / 100.0)
    payouts_total_sats = max(0, gross_pool - house_fee_sats - tribute_fee_sats)
    return {
        "house_fee_sats": house_fee_sats,
        "tribute_fee_sats": tribute_fee_sats,
        "payouts_total_sats": payouts_total_sats,
    }


async def pay_tribute(tribute: int, wallet_id: str) -> None:
    if tribute <= 0:
        return
    try:
        pr = await get_pr_from_lnurl(
            LNBITS_TRIBUTE_ADDRESS,
            tribute * 1000,
            comment="HexArena tribute",
        )
        await pay_invoice(
            wallet_id=wallet_id,
            payment_request=pr,
            max_sat=tribute,
            description="Tribute to help support LNbits",
        )
    except Exception as exc:
        logger.warning(exc)
        raise


async def settle_run_fees(run):
    if run.fee_status == "settled":
        return run

    breakdown = calculate_fee_breakdown(run)
    updated_run = run.copy(update=breakdown)
    wallet_id = await _get_run_wallet_id(run.id)
    fee_wallet_id = await _get_run_fee_wallet_id(run.id)

    try:
        if breakdown["house_fee_sats"] > 0 and fee_wallet_id and fee_wallet_id != wallet_id:
            operator_invoice = await create_invoice(
                wallet_id=fee_wallet_id,
                amount=breakdown["house_fee_sats"],
                memo=f"HexArena house fee for run {run.id}",
                extra={"tag": "hexarena_house_fee", "run_id": run.id},
            )
            await pay_invoice(
                wallet_id=wallet_id,
                payment_request=operator_invoice.bolt11,
                max_sat=breakdown["house_fee_sats"],
                description=f"HexArena house fee for run {run.id}",
                tag="hexarena_house_fee",
            )

        if breakdown["tribute_fee_sats"] > 0:
            await pay_tribute(breakdown["tribute_fee_sats"], wallet_id)

        return updated_run.copy(
            update={"fee_status": "settled", "fees_settled_at": utc_now()}
        )
    except Exception as exc:
        logger.warning(f"Error settling HexArena fees for run {run.id}: {exc}")
        return updated_run.copy(update={"fee_status": "pending"})


def determine_run_winner(run: GameRun) -> str | None:
    standings = list(run.current_state.agents or [])
    if not standings:
        return None
    alive = [standing for standing in standings if not standing.eliminated]
    if len(alive) == 1:
        return alive[0].id
    ranked = sorted(
        standings,
        key=lambda standing: (-standing.hex_count, -standing.total_power, standing.id),
    )
    return ranked[0].id if ranked else None


async def finalize_run(run_id: str, *, winner_agent_id: str | None = None) -> GameRun:
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Run not found.")
    if run.status == "cancelled":
        raise ValueError("Cancelled runs cannot be finalized.")

    agents = await get_agents_for_run(run_id)
    winner = winner_agent_id or run.winner_agent_id or determine_run_winner(run)
    now = utc_now()
    state = run.current_state.copy(deep=True)
    state.status = "finished"

    updated_run = run.copy(
        update={
            "status": "finished",
            "winner_agent_id": winner,
            "finished_at": run.finished_at or now,
            "current_state": state,
        }
    )
    updated_run = await settle_run_fees(updated_run)
    updated_agents = await prepare_run_payouts(updated_run, agents)

    await update_game_run(updated_run)
    for agent in updated_agents:
        await update_agent(agent)
    await publish_admin_event_for_run(run_id, event="finished")
    await publish_public_run_event(run_id, event="finished")
    return updated_run


async def cancel_run(run_id: str) -> GameRun:
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Run not found.")
    now = utc_now()
    state = run.current_state.copy(deep=True)
    state.status = "cancelled"
    updated_run = run.copy(
        update={
            "status": "cancelled",
            "finished_at": run.finished_at or now,
            "current_state": state,
            "fee_status": "none",
        }
    )
    await update_game_run(updated_run)
    await publish_admin_event_for_run(run_id, event="cancelled")
    await publish_public_run_event(run_id, event="cancelled")
    return updated_run


async def retry_run_fee_settlement(run_id: str) -> GameRun:
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Run not found.")
    if run.status != "finished":
        raise ValueError("Only finished runs can settle fees.")

    updated = await settle_run_fees(run.copy(update={"fee_status": "pending"}))
    await update_game_run(updated)
    await publish_admin_event_for_run(run_id, event="fees_retried")
    await publish_public_run_event(run_id, event="fees_retried")
    return updated


async def get_agent_payout_claim(run_id: str, agent: Agent, request) -> AgentPayoutResponse:
    run = await get_game_run(run_id)
    if not run:
        raise ValueError("Run not found.")
    if agent.run_id != run_id:
        raise ValueError("Agent does not belong to this run.")

    if run.status != "finished":
        return AgentPayoutResponse(
            run_id=run_id,
            agent_id=agent.id,
            status="not_ready",
            payout_amount_sats=0,
        )

    if agent.payout_amount_sats <= 0 or not agent.payout_unique_hash:
        return AgentPayoutResponse(
            run_id=run_id,
            agent_id=agent.id,
            status="not_eligible",
            payout_amount_sats=0,
        )

    withdraw_url = str(
        request.url_for(
            "hexarena.lnurl_withdraw",
            payout_unique_hash=agent.payout_unique_hash,
        )
    )
    from lnurl import encode as lnurl_encode

    return AgentPayoutResponse(
        run_id=run_id,
        agent_id=agent.id,
        status=agent.payout_status,
        payout_amount_sats=agent.payout_amount_sats,
        payout_request=agent.payout_request,
        payout_settled_at=agent.payout_settled_at,
        lnurl=lnurl_encode(withdraw_url),
        url=withdraw_url,
    )


async def get_payout_agent_by_hash(payout_unique_hash: str) -> Agent:
    agent = await get_agent_by_payout_hash(payout_unique_hash)
    if not agent or not agent.payout_unique_hash:
        raise ValueError("Payout claim not found.")
    if agent.payout_amount_sats <= 0:
        raise ValueError("No payout available for this claim.")
    return agent


async def settle_agent_payout(
    payout_unique_hash: str,
    *,
    k1: str,
    payment_request: str,
) -> Agent:
    lock = payout_locks.setdefault(payout_unique_hash, asyncio.Lock())
    async with lock:
        agent = await get_payout_agent_by_hash(payout_unique_hash)
        if agent.payout_status == "paid":
            raise ValueError("Payout already claimed.")
        if not agent.payout_k1 or agent.payout_k1 != k1:
            raise ValueError("Invalid payout secret.")

        wallet_id = await _get_run_wallet_id(agent.run_id)
        payment = await pay_invoice(
            wallet_id=wallet_id,
            payment_request=payment_request,
            max_sat=agent.payout_amount_sats,
            extra={
                "tag": "hexarena_payout",
                "run_id": agent.run_id,
                "agent_id": agent.id,
            },
            description=f"HexArena payout for run {agent.run_id}",
            tag="hexarena_payout",
        )
        updated = await update_agent(
            agent.copy(
                update={
                    "payout_status": "paid",
                    "payout_request": payment_request,
                    "payout_payment_hash": payment.payment_hash,
                    "payout_settled_at": utc_now(),
                }
            )
        )
        await publish_admin_event_for_run(agent.run_id, scope="agents", event="payout_settled")
        return updated


async def settle_agent_payout_admin(agent_id: str, payment_request: str) -> Agent:
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise ValueError("Agent not found.")
    if agent.payout_amount_sats <= 0:
        raise ValueError("No payout available for this agent.")
    if agent.payout_status == "paid":
        raise ValueError("Payout already claimed.")

    wallet_id = await _get_run_wallet_id(agent.run_id)
    payment = await pay_invoice(
        wallet_id=wallet_id,
        payment_request=payment_request,
        max_sat=agent.payout_amount_sats,
        extra={
            "tag": "hexarena_payout_admin",
            "run_id": agent.run_id,
            "agent_id": agent.id,
        },
        description=f"HexArena admin payout for run {agent.run_id}",
        tag="hexarena_payout_admin",
    )
    updated = await update_agent(
        agent.copy(
            update={
                "payout_status": "paid",
                "payout_request": payment_request,
                "payout_payment_hash": payment.payment_hash,
                "payout_settled_at": utc_now(),
            }
        )
    )
    await publish_admin_event_for_run(agent.run_id, scope="agents", event="payout_settled")
    return updated
