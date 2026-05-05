import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .services import (
    auto_start_waiting_runs,
    ensure_waiting_runs_for_finished_games,
    expire_stale_join_requests,
    payment_received_for_player,
    process_due_running_runs,
)

#######################################
########## RUN YOUR TASKS HERE ########
#######################################

# The usual task is to listen to invoices related to this extension


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_hexarena")
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def cleanup_pending_joins():
    while True:
        try:
            expired_count = await expire_stale_join_requests()
            if expired_count:
                logger.info(f"Expired {expired_count} stale HexArena join requests.")
        except Exception as e:
            logger.error(f"Error expiring HexArena join requests: {e}")
        await asyncio.sleep(5)


async def auto_start_runs():
    while True:
        try:
            started = await auto_start_waiting_runs()
            if started:
                logger.info(f"Started {started} HexArena runs automatically.")
        except Exception as e:
            logger.error(f"Error auto-starting HexArena runs: {e}")
        await asyncio.sleep(5)


async def maintain_waiting_runs():
    while True:
        try:
            spawned = await ensure_waiting_runs_for_finished_games()
            if spawned:
                logger.info(f"Spawned {spawned} fresh HexArena waiting runs.")
        except Exception as e:
            logger.error(f"Error spawning HexArena waiting runs: {e}")
        await asyncio.sleep(5)


async def process_running_runs():
    while True:
        try:
            processed = await process_due_running_runs()
            if processed:
                logger.info(f"Processed {processed} HexArena run turns.")
        except Exception as e:
            logger.error(f"Error processing HexArena turns: {e}")
        await asyncio.sleep(2)


# Do somethhing when an invoice related top this extension is paid


async def on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or payment.extra.get("tag") != "hexarena_join":
        return

    logger.info(f"Invoice paid for hexarena: {payment.payment_hash}")

    try:
        await payment_received_for_player(payment)
    except Exception as e:
        logger.error(f"Error processing payment for hexarena: {e}")
