from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands


class SupportCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="support", description="Sends you a link to the CS-Pound Dev Server."
    )
    async def support(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Need help with the bot? Come join the support server here! https://support.haruyuki.moe/",
            ephemeral=True,
        )
