from types import SimpleNamespace
from uuid import uuid4

import pytest

from hexarena.crud import (  # type: ignore[import]
    create_agent,
    create_game,
    create_game_run,
    update_agent,
)
from hexarena.models import (  # type: ignore[import]
    AgentStanding,
    CreateAgent,
    CreateGame,
    CreateGameRun,
    GameConfig,
    LeaderboardEntry,
)
from hexarena.services import (  # type: ignore[import]
    calculate_fee_breakdown,
    calculate_payout_amounts,
    cancel_run,
    finalize_run,
    prepare_run_payouts,
    require_joinable_run,
    retry_run_fee_settlement,
    settle_agent_payout,
    settle_run_fees,
)


@pytest.mark.asyncio
async def test_prepare_run_payouts_assigns_top3_distribution():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Payouts",
            wallet_id="wallet-1",
            default_config=GameConfig(
                min_players=3,
                max_players=4,
                payout_scheme="top_3_60_30_10",
            ),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="finished", prize_pool_sats=100))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
        await create_agent(run.id, CreateAgent(display_name="bot-c"), status="active", api_key="c"),
    ]

    run.current_state.agents = [
        AgentStanding(id=agents[0].id, hex_count=8, total_power=20, eliminated=False),
        AgentStanding(id=agents[1].id, hex_count=5, total_power=12, eliminated=False),
        AgentStanding(id=agents[2].id, hex_count=2, total_power=5, eliminated=False),
    ]
    run.current_state.leaderboard = [
        LeaderboardEntry(agent_id=agents[0].id, hexes=8, total_power=20, rank=1),
        LeaderboardEntry(agent_id=agents[1].id, hexes=5, total_power=12, rank=2),
        LeaderboardEntry(agent_id=agents[2].id, hexes=2, total_power=5, rank=3),
    ]

    payouts = calculate_payout_amounts(run, agents)
    assert payouts == {
        agents[0].id: 60,
        agents[1].id: 30,
        agents[2].id: 10,
    }

    prepared_agents = await prepare_run_payouts(run, agents)
    assert prepared_agents[0].payout_status == "pending_claim"
    assert prepared_agents[0].payout_amount_sats == 60
    assert prepared_agents[1].payout_amount_sats == 30
    assert prepared_agents[2].payout_amount_sats == 10
    assert prepared_agents[0].payout_unique_hash
    assert prepared_agents[0].payout_k1


@pytest.mark.asyncio
async def test_settle_agent_payout_marks_agent_paid(monkeypatch):
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(name="Arena Withdraw", wallet_id="wallet-1"),
    )
    run = await create_game_run(game, CreateGameRun(status="finished"))
    agent = await create_agent(
        run.id,
        CreateAgent(display_name="winner"),
        status="active",
        api_key="winner-key",
    )
    agent = await update_agent(
        agent.copy(
            update={
                "payout_amount_sats": 50,
                "payout_status": "pending_claim",
                "payout_unique_hash": "claim-1",
                "payout_k1": "secret-1",
            }
        )
    )

    async def fake_pay_invoice(**kwargs):
        assert kwargs["wallet_id"] == game.wallet_id
        assert kwargs["max_sat"] == 50
        return SimpleNamespace(payment_hash="paid-hash-1")

    monkeypatch.setattr("hexarena.services.pay_invoice", fake_pay_invoice)

    settled = await settle_agent_payout(
        "claim-1",
        k1="secret-1",
        payment_request="lnbc1testinvoice",
    )
    assert settled.payout_status == "paid"
    assert settled.payout_request == "lnbc1testinvoice"
    assert settled.payout_payment_hash == "paid-hash-1"
    assert settled.payout_settled_at is not None


@pytest.mark.asyncio
async def test_settle_run_fees_uses_house_fee_and_fixed_tribute(monkeypatch):
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Fees",
            wallet_id="wallet-1",
            fee_wallet_id="wallet-fees",
            default_config=GameConfig(house_fee_percent=5.0),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="finished", prize_pool_sats=1000))

    created_invoices: list[tuple[str, int]] = []
    paid_requests: list[dict] = []

    async def fake_create_invoice(**kwargs):
        created_invoices.append((kwargs["wallet_id"], kwargs["amount"]))
        return SimpleNamespace(bolt11="lnbc1housefee")

    async def fake_pay_invoice(**kwargs):
        paid_requests.append(kwargs)
        return SimpleNamespace(payment_hash=f"paid-{len(paid_requests)}")

    async def fake_get_pr_from_lnurl(*args, **kwargs):
        return "lnbc1tribute"

    monkeypatch.setattr("hexarena.services.create_invoice", fake_create_invoice)
    monkeypatch.setattr("hexarena.services.pay_invoice", fake_pay_invoice)
    monkeypatch.setattr("hexarena.services.get_pr_from_lnurl", fake_get_pr_from_lnurl)

    breakdown = calculate_fee_breakdown(run)
    assert breakdown == {
        "house_fee_sats": 50,
        "tribute_fee_sats": 5,
        "payouts_total_sats": 945,
    }

    settled_run = await settle_run_fees(run)
    assert settled_run.house_fee_sats == 50
    assert settled_run.tribute_fee_sats == 5
    assert settled_run.payouts_total_sats == 945
    assert settled_run.fee_status == "settled"
    assert settled_run.fees_settled_at is not None
    assert created_invoices == [("wallet-fees", 50)]
    assert paid_requests[0]["wallet_id"] == "wallet-1"
    assert paid_requests[0]["max_sat"] == 50
    assert paid_requests[1]["wallet_id"] == "wallet-1"
    assert paid_requests[1]["max_sat"] == 5


@pytest.mark.asyncio
async def test_running_run_is_not_joinable():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(name="Arena Locked", wallet_id="wallet-1"),
    )
    run = await create_game_run(game, CreateGameRun(status="running"))

    with pytest.raises(ValueError, match="Run is not accepting joins."):
        await require_joinable_run(run.id)


@pytest.mark.asyncio
async def test_finalize_run_assigns_winner_and_prepares_payouts(monkeypatch):
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(
            name="Arena Finalize",
            wallet_id="wallet-1",
            default_config=GameConfig(payout_scheme="winner_takes_all"),
        ),
    )
    run = await create_game_run(game, CreateGameRun(status="running", prize_pool_sats=100))
    agents = [
        await create_agent(run.id, CreateAgent(display_name="bot-a"), status="active", api_key="a"),
        await create_agent(run.id, CreateAgent(display_name="bot-b"), status="active", api_key="b"),
    ]
    run.current_state.status = "running"
    run.current_state.agents = [
        AgentStanding(id=agents[0].id, hex_count=5, total_power=10, eliminated=False),
        AgentStanding(id=agents[1].id, hex_count=2, total_power=5, eliminated=False),
    ]
    run.current_state.leaderboard = [
        LeaderboardEntry(agent_id=agents[0].id, hexes=5, total_power=10, rank=1),
        LeaderboardEntry(agent_id=agents[1].id, hexes=2, total_power=5, rank=2),
    ]
    from hexarena.crud import update_game_run  # type: ignore[import]

    await update_game_run(run)

    async def fake_get_pr_from_lnurl(*args, **kwargs):
        return "lnbc1tribute"

    async def fake_pay_invoice(**kwargs):
        return SimpleNamespace(payment_hash="fee-paid")

    monkeypatch.setattr("hexarena.services.get_pr_from_lnurl", fake_get_pr_from_lnurl)
    monkeypatch.setattr("hexarena.services.pay_invoice", fake_pay_invoice)

    finalized = await finalize_run(run.id)
    assert finalized.status == "finished"
    assert finalized.winner_agent_id == agents[0].id
    assert finalized.payouts_total_sats == 100
    assert finalized.fee_status == "settled"


@pytest.mark.asyncio
async def test_cancel_run_marks_state_cancelled():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(name="Arena Cancel", wallet_id="wallet-1"),
    )
    run = await create_game_run(game, CreateGameRun(status="waiting"))
    cancelled = await cancel_run(run.id)
    assert cancelled.status == "cancelled"
    assert cancelled.current_state.status == "cancelled"


@pytest.mark.asyncio
async def test_retry_run_fee_settlement_requires_finished_run():
    user_id = uuid4().hex
    game = await create_game(
        user_id,
        CreateGame(name="Arena Retry Fees", wallet_id="wallet-1"),
    )
    run = await create_game_run(game, CreateGameRun(status="running"))

    with pytest.raises(ValueError, match="Only finished runs can settle fees."):
        await retry_run_fee_settlement(run.id)
