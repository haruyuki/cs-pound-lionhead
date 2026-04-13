from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.utils import get_opening_status


class TimeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="time", description="Check how long before the pound/lost & found opens."
    )
    async def time(self, interaction: discord.Interaction) -> None:
        session = self.bot.web_client
        opening_status = await get_opening_status(session)

        if opening_status.is_open:
            message = f"The {opening_status.event_type} is currently open with {opening_status.remaining_count} {'pets' if opening_status.event_type == 'Pound' else 'items'} remaining! [Go {'adopt a pet' if opening_status.event_type == 'Pound' else 'get an item'} from the {opening_status.event_type}!](https://www.chickensmoothie.com/poundandlostandfound.php)"
            await interaction.response.send_message(message)
        elif not opening_status.is_open and opening_status.event_type is not None:
            hours, minutes = divmod(opening_status.remaining_minutes, 60)

            parts = []
            if hours:
                parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
            if minutes:
                parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")

            if not parts:
                message = f"The {opening_status.event_type} will open soon."
                await interaction.response.send_message(message)
                return

            if len(parts) == 1:
                message = f"The {opening_status.event_type} will open in {parts[0]}."
                await interaction.response.send_message(message)
            else:
                message = f"The {opening_status.event_type} will open in {parts[0]} and {parts[1]}."
                await interaction.response.send_message(message)
        else:
            message = (
                "Sorry, both the Pound and Lost and Found are closed at the moment."
            )
            await interaction.response.send_message(message)
