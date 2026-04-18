from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from src.utils import get_opening_status

logger = logging.getLogger(__name__)

SUPPORTED_OPENING_TYPES = ("pound", "laf")
MIN_REMINDER_MINUTES = 1
MAX_REMINDER_MINUTES = 60
DEFAULT_POLL_MINUTES = 60
CHANNEL_STAGGER_SECONDS = 0.1


@dataclass(slots=True)
class _CountdownState:
    in_countdown: bool = False
    timeout_minutes: int = 60
    opening_type: str | None = None
    minutes_remaining: int = 0


_STATE = _CountdownState()
_AUTOREMIND_TIMES = {opening_type: set() for opening_type in SUPPORTED_OPENING_TYPES}


async def autoremind_task(bot) -> None:
    await bot.wait_until_ready()
    logger.info("AutoRemind background task started")

    while not bot.is_closed():
        try:
            _STATE.timeout_minutes = await run_task(bot)
        except asyncio.CancelledError:
            logger.info("AutoRemind background task cancelled")
            raise
        except Exception:
            logger.exception("Error in AutoRemind background task")
            _STATE.timeout_minutes = 1

        await asyncio.sleep(_STATE.timeout_minutes * 60)


async def initialize_reminder_times(collection) -> None:
    await update_autoreminds(collection)


async def autoremind_add_handler(collection, opening_type: str, minutes: int) -> None:
    if minutes in _AUTOREMIND_TIMES[opening_type]:
        return

    await update_autoreminds(collection, opening_type)


async def autoremind_remove_handler(collection, opening_type: str) -> None:
    await update_autoreminds(collection, opening_type)


async def run_task(bot) -> int:
    if not _STATE.in_countdown:
        timeout_minutes = await get_sleep_minutes(bot.web_client)
        if timeout_minutes is not None:
            return timeout_minutes

    if _STATE.minutes_remaining <= 0:
        logger.info(
            "%s has opened! Resetting timer",
            _STATE.opening_type,
        )
        await reset_state()
        return DEFAULT_POLL_MINUTES

    if _STATE.opening_type is None:
        logger.warning("Countdown missing opening type; resetting state")
        await reset_state()
        return DEFAULT_POLL_MINUTES

    await dispatch_minute_reminders(
        bot,
        _STATE.opening_type,
        _STATE.minutes_remaining,
    )
    _STATE.minutes_remaining -= 1
    _STATE.timeout_minutes = 1
    return 1


async def get_sleep_minutes(session) -> int | None:
    opening_status = await get_opening_status(session)

    if opening_status.is_open:
        logger.info("%s has opened!", opening_status.event_type)
        await reset_state()
        return DEFAULT_POLL_MINUTES

    if _STATE.opening_type is None:
        match opening_status.event_type:
            case "Pound":
                mapped_opening_type = "pound"
            case "Lost and Found":
                mapped_opening_type = "laf"
            case _:
                return DEFAULT_POLL_MINUTES

        _STATE.opening_type = mapped_opening_type

    remaining_minutes = opening_status.remaining_minutes
    if remaining_minutes is None:
        return DEFAULT_POLL_MINUTES

    _STATE.minutes_remaining = remaining_minutes
    if _STATE.minutes_remaining == 0:
        return DEFAULT_POLL_MINUTES

    if _STATE.minutes_remaining <= 61:
        _STATE.in_countdown = True
        _STATE.timeout_minutes = 1
        logger.info(
            "%s opening in %s minutes, switching to self updates",
            _STATE.opening_type,
            _STATE.minutes_remaining,
        )
        return None

    _STATE.timeout_minutes = max(1, _STATE.minutes_remaining - 61)
    logger.info(
        "%s opens in %s minutes. Sleeping %s minutes.",
        _STATE.opening_type,
        _STATE.minutes_remaining,
        _STATE.timeout_minutes,
    )
    return _STATE.timeout_minutes


async def dispatch_minute_reminders(
    bot, opening_type: str, minutes_remaining: int
) -> None:
    reminder_minutes = _AUTOREMIND_TIMES[opening_type]
    if minutes_remaining not in reminder_minutes:
        return

    logger.info("Sending %s reminders for %s minutes", opening_type, minutes_remaining)

    try:
        documents = await get_autoremind_documents(
            bot.autoremind_collection,
            minutes_remaining,
            opening_type,
        )
    except Exception:
        logger.exception("Error fetching reminder documents")
        return

    if not documents:
        return

    channel_user_ids = defaultdict(list)
    for document in documents:
        channel_user_ids[document["channel_id"]].append(document["user_id"])

    tasks = []
    for channel_index, (channel_id, user_ids) in enumerate(channel_user_ids.items()):
        delay_seconds = channel_index * CHANNEL_STAGGER_SECONDS
        tasks.append(
            asyncio.create_task(
                prepare_reminder(
                    bot,
                    channel_id,
                    minutes_remaining,
                    opening_type,
                    user_ids,
                    delay_seconds,
                )
            )
        )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failures = sum(1 for result in results if isinstance(result, Exception))
        if failures:
            logger.warning(
                "%s/%s channel reminder task(s) failed", failures, len(tasks)
            )


async def update_autoreminds(collection, opening_type: str | None = None) -> None:
    opening_types = (
        (opening_type,) if opening_type is not None else SUPPORTED_OPENING_TYPES
    )

    for opening in opening_types:
        try:
            distinct_values = await collection.distinct(opening)
        except Exception:
            logger.exception(
                "Failed to refresh %s reminder minute cache from database", opening
            )
            continue

        _AUTOREMIND_TIMES[opening] = {int(v) for v in distinct_values}
        logger.info(
            "Updated %s AutoRemind times with %s distinct values",
            opening,
            len(_AUTOREMIND_TIMES[opening]),
        )


async def prepare_reminder(
    bot,
    channel_id: int,
    minutes_left: int,
    opening_type: str,
    user_ids: Sequence[int],
    delay_seconds: float,
) -> None:
    try:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)

        await send_message(channel, minutes_left, opening_type, user_ids)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(
            "Failed to send reminder to channel %s. Reason: %s",
            channel_id,
            e,
        )


async def send_message(
    channel, minutes_left: int, opening_type: str, user_ids: Sequence[int]
) -> None:
    opening_label = "Pound" if opening_type == "pound" else "Lost and Found"
    message_prefix = f"{minutes_left} minute{'s' if minutes_left != 1 else ''} until the {opening_label} opens! "

    user_list = [f"<@{user_id}>" for user_id in user_ids]

    batches = []
    current_batch = []
    for mention in user_list:
        if len(current_batch) >= 50:  # Max mentions per message
            batches.append(current_batch)
            current_batch = []
        current_batch.append(mention)
    if current_batch:
        batches.append(current_batch)

    for index, batch in enumerate(batches):
        batch_message = message_prefix + " ".join(batch)
        try:
            await channel.send(batch_message)
        except Exception:
            logger.exception("Failed to send message batch to channel %s", channel.id)
            continue


async def get_autoremind_documents(
    collection, minutes_remaining: int, opening_type: str
) -> list[dict[str, int]]:
    cursor = collection.find(
        {opening_type: minutes_remaining}, {"user_id": 1, "channel_id": 1}
    )
    documents = await cursor.to_list(length=None)

    return [
        {"user_id": document["user_id"], "channel_id": document["channel_id"]}
        for document in documents
    ]


async def reset_state() -> None:
    _STATE.in_countdown = False
    _STATE.timeout_minutes = DEFAULT_POLL_MINUTES
    _STATE.opening_type = None
    _STATE.minutes_remaining = 0
    logger.info("AutoRemind countdown state reset complete")
