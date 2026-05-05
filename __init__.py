import asyncio

from fastapi import APIRouter
from lnbits.tasks import create_permanent_unique_task
from loguru import logger

from .crud import db
from .tasks import (
    auto_start_runs,
    cleanup_pending_joins,
    maintain_waiting_runs,
    process_running_runs,
    wait_for_paid_invoices,
)
from .views import hexarena_generic_router
from .views_api import hexarena_api_router
from .views_lnurl import hexarena_lnurl_router

hexarena_ext: APIRouter = APIRouter(
    prefix="/hexarena", tags=["HexArena"]
)
hexarena_ext.include_router(hexarena_generic_router)
hexarena_ext.include_router(hexarena_api_router)
hexarena_ext.include_router(hexarena_lnurl_router)


hexarena_static_files = [
    {
        "path": "/hexarena/static",
        "name": "hexarena_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def hexarena_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def hexarena_start():
    payments_task = create_permanent_unique_task(
        "ext_hexarena_payments", wait_for_paid_invoices
    )
    cleanup_task = create_permanent_unique_task(
        "ext_hexarena_join_gc", cleanup_pending_joins
    )
    autostart_task = create_permanent_unique_task(
        "ext_hexarena_autostart", auto_start_runs
    )
    respawn_task = create_permanent_unique_task(
        "ext_hexarena_respawn_waiting", maintain_waiting_runs
    )
    tick_task = create_permanent_unique_task(
        "ext_hexarena_turns", process_running_runs
    )
    scheduled_tasks.extend([payments_task, cleanup_task, autostart_task, respawn_task, tick_task])


__all__ = [
    "db",
    "hexarena_ext",
    "hexarena_start",
    "hexarena_static_files",
    "hexarena_stop",
]
