from __future__ import annotations

import asyncio
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class RemindMeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._pending_tasks: set[asyncio.Task[None]] = set()

    @app_commands.command(
        name="remindme", description="Set a short-term reminder in this channel."
    )
    @app_commands.describe(time="Examples: '30' (minutes), '1h20m', '45s', '2h5m10s'")
    async def remindme(self, interaction: discord.Interaction, time: str) -> None:
        parsed_time = parse_time_string(time)
        if parsed_time is None:
            await interaction.response.send_message(
                "Invalid time format. Use `30`, `1h20m`, `45s`, or `2h5m10s`.",
                ephemeral=True,
            )
            return

        hours, minutes, seconds = parsed_time
        total_seconds = hours * 3600 + minutes * 60 + seconds
        if total_seconds <= 0:
            await interaction.response.send_message(
                "Reminder time must be greater than 0 seconds.",
                ephemeral=True,
            )
            return

        amount = format_duration(hours, minutes, seconds)

        await interaction.response.send_message(
            f"A reminder has been set for you in {amount}.", ephemeral=True
        )

        channel_id = interaction.channel_id
        if channel_id is None:
            logger.warning("Interaction has no channel ID, cannot set reminder")
            return

        task = asyncio.create_task(
            self.send_reminder(
                delay_seconds=total_seconds,
                channel_id=channel_id,
                user_mention=interaction.user.mention,
                amount=amount,
            )
        )
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def send_reminder(
        self, delay_seconds: int, channel_id: int, user_mention: str, amount: str
    ) -> None:
        await asyncio.sleep(delay_seconds)

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return

        await channel.send(f"{user_mention}, this is your {amount} reminder!")


def parse_time_string(value: str) -> tuple[int, int, int] | None:
    text = value.strip().lower()
    if not text:
        return None

    if text.isdigit():
        return normalise(0, int(text), 0)

    time_pattern = re.compile(r"^(?:\d+[hms])+$")
    if not time_pattern.fullmatch(text):
        return None

    hours = 0
    minutes = 0
    seconds = 0

    token_pattern = re.compile(r"(\d+)([hms])")
    for amount_text, unit in token_pattern.findall(text):
        amount = int(amount_text)
        if unit == "h":
            hours += amount
        elif unit == "m":
            minutes += amount
        else:
            seconds += amount

    return normalise(hours, minutes, seconds)


def normalise(hours: int, minutes: int, seconds: int) -> tuple[int, int, int]:
    total_seconds = hours * 3600 + minutes * 60 + seconds
    norm_hours, remainder = divmod(total_seconds, 3600)
    norm_minutes, norm_seconds = divmod(remainder, 60)
    return norm_hours, norm_minutes, norm_seconds


def format_duration(hours: int, minutes: int, seconds: int) -> str:
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
    if minutes:
        parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
    if seconds:
        parts.append(f"{seconds} {'second' if seconds == 1 else 'seconds'}")

    if not parts:
        return "0 seconds"
    if len(parts) == 1:
        return parts[0]

    return f"{', '.join(parts[:-1])} and {parts[-1]}"
