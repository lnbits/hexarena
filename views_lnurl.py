import json

from fastapi import APIRouter, Request
from lnurl import (
    CallbackUrl,
    LightningInvoice,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayResponse,
    Max144Str,
    MilliSatoshi,
    UrlAction,
)
from pydantic import parse_obj_as

from .models import CreateJoinRequest
from .services import (
    create_paid_join_request,
    get_payout_agent_by_hash,
    require_joinable_run,
    settle_agent_payout,
)

hexarena_lnurl_router = APIRouter()


def _join_metadata(run_id: str) -> str:
    return json.dumps(
        [
            [
                "text/plain",
                f"HexArena paid join for run {run_id}. Complete payment to receive agent credentials.",
            ]
        ]
    )


@hexarena_lnurl_router.get(
    "/lnurl/join/{run_id}",
    name="hexarena.lnurl_join",
)
async def lnurl_join(run_id: str, request: Request) -> LnurlPayResponse | LnurlErrorResponse:
    try:
        run = await require_joinable_run(run_id)
    except ValueError as exc:
        return LnurlErrorResponse(reason=str(exc))

    if run.config.entry_fee_sats <= 0:
        return LnurlErrorResponse(reason="This run does not require payment.")

    callback_url = str(request.url_for("hexarena.lnurl_join_callback", run_id=run_id))
    display_name = request.query_params.get("display_name")
    if display_name:
        callback_url += f"?display_name={display_name}"
    callback = parse_obj_as(CallbackUrl, callback_url)
    amount_msat = MilliSatoshi(run.config.entry_fee_sats * 1000)
    return LnurlPayResponse(
        callback=callback,
        minSendable=amount_msat,
        maxSendable=amount_msat,
        metadata=_join_metadata(run_id),
        commentAllowed=64,
    )


@hexarena_lnurl_router.get(
    "/lnurl/join/cb/{run_id}",
    name="hexarena.lnurl_join_callback",
)
async def lnurl_join_callback(
    run_id: str,
    request: Request,
    amount: int,
    comment: str | None = None,
    display_name: str | None = None,
) -> LnurlPayActionResponse | LnurlErrorResponse:
    try:
        run = await require_joinable_run(run_id)
    except ValueError as exc:
        return LnurlErrorResponse(reason=str(exc))

    expected_amount = run.config.entry_fee_sats * 1000
    if amount != expected_amount:
        return LnurlErrorResponse(
            reason=f"Expected payment amount {expected_amount} msat."
        )

    if comment and len(comment) > 64:
        return LnurlErrorResponse(reason="Comment too long.")

    try:
        join_request = await create_paid_join_request(
            run_id,
            CreateJoinRequest(display_name=display_name or comment),
            memo=f"HexArena join {run_id}",
            unhashed_description=_join_metadata(run_id).encode(),
            extra={"join_comment": comment, "display_name": display_name or comment},
        )
    except ValueError as exc:
        return LnurlErrorResponse(reason=str(exc))

    invoice = parse_obj_as(
        LightningInvoice, LightningInvoice(join_request.payment_request)
    )
    status_url = parse_obj_as(
        CallbackUrl,
        (
            f"{request.base_url}hexarena/play/{run_id}"
            f"?join_request_id={join_request.id}&token={join_request.claim_token}"
        ),
    )
    description = parse_obj_as(
        Max144Str,
        "Track HexArena join status and retrieve agent credentials after settlement.",
    )
    action = UrlAction(description=description, url=status_url)
    return LnurlPayActionResponse(pr=invoice, successAction=action)


@hexarena_lnurl_router.get(
    "/lnurl/withdraw/{payout_unique_hash}",
    name="hexarena.lnurl_withdraw",
)
async def lnurl_withdraw(payout_unique_hash: str, request: Request) -> dict | LnurlErrorResponse:
    try:
        agent = await get_payout_agent_by_hash(payout_unique_hash)
    except ValueError as exc:
        return LnurlErrorResponse(reason=str(exc))

    if agent.payout_status == "paid":
        return LnurlErrorResponse(reason="Payout already claimed.")
    if not agent.payout_k1:
        return LnurlErrorResponse(reason="Payout claim is not active.")

    callback = str(
        request.url_for(
            "hexarena.lnurl_withdraw_callback",
            payout_unique_hash=payout_unique_hash,
        )
    )
    return {
        "tag": "withdrawRequest",
        "callback": callback,
        "k1": agent.payout_k1,
        "minWithdrawable": agent.payout_amount_sats * 1000,
        "maxWithdrawable": agent.payout_amount_sats * 1000,
        "defaultDescription": f"HexArena payout for run {agent.run_id}",
    }


@hexarena_lnurl_router.get(
    "/lnurl/withdraw/cb/{payout_unique_hash}",
    name="hexarena.lnurl_withdraw_callback",
)
async def lnurl_withdraw_callback(
    payout_unique_hash: str,
    pr: str,
    k1: str,
) -> dict:
    try:
        await settle_agent_payout(
            payout_unique_hash,
            k1=k1,
            payment_request=pr,
        )
    except Exception as exc:
        return {"status": "ERROR", "reason": str(exc)}
    return {"status": "OK"}
