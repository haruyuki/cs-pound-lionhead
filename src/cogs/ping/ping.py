from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands


class PingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = self.bot.latency * 1000  # Convert to milliseconds
        await interaction.response.send_message(f"Pong! Latency: {latency:.2f} ms")
