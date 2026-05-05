import json

from lnbits.core.services import websocket_updater

from .crud import get_agent_by_id, get_game_by_id, get_game_run, get_join_request


def get_admin_channel_id(user_id: str) -> str:
    return f"hexarena-admin-{user_id}"


def get_public_run_channel_id(run_id: str) -> str:
    return f"hexarena-public-run-{run_id}"


async def publish_admin_event_for_user(
    user_id: str,
    *,
    scope: str,
    event: str,
    entity_id: str | None = None,
) -> None:
    await websocket_updater(
        get_admin_channel_id(user_id),
        json.dumps(
            {
                "scope": scope,
                "event": event,
                "entity_id": entity_id,
            }
        ),
    )


async def publish_admin_event_for_game(
    game_id: str,
    *,
    scope: str = "games",
    event: str = "updated",
) -> None:
    game = await get_game_by_id(game_id)
    if not game:
        return
    await publish_admin_event_for_user(
        game.user_id,
        scope=scope,
        event=event,
        entity_id=game_id,
    )


async def publish_admin_event_for_run(
    run_id: str,
    *,
    scope: str = "runs",
    event: str = "updated",
) -> None:
    run = await get_game_run(run_id)
    if not run:
        return
    await publish_admin_event_for_game(run.game_id, scope=scope, event=event)


async def publish_admin_event_for_agent(
    agent_id: str,
    *,
    scope: str = "agents",
    event: str = "updated",
) -> None:
    agent = await get_agent_by_id(agent_id)
    if not agent:
        return
    await publish_admin_event_for_run(agent.run_id, scope=scope, event=event)


async def publish_admin_event_for_join_request(
    join_request_id: str,
    *,
    scope: str = "join_requests",
    event: str = "updated",
) -> None:
    join_request = await get_join_request(join_request_id)
    if not join_request:
        return
    await publish_admin_event_for_run(join_request.run_id, scope=scope, event=event)


async def publish_public_run_event(
    run_id: str,
    *,
    event: str = "updated",
) -> None:
    run = await get_game_run(run_id)
    if not run:
        return
    await websocket_updater(
        get_public_run_channel_id(run_id),
        json.dumps(
            {
                "run_id": run.id,
                "event": event,
                "status": run.status,
                "turn": run.turn,
            }
        ),
    )
