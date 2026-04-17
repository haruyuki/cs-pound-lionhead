from __future__ import annotations

import tomllib
from datetime import datetime
from platform import python_version

import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    check_mongodb_status,
    check_chickensmoothie_status,
)

start_time = datetime.now()


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="stats", description="Stats about the bot.")
    async def support(self, interaction: discord.Interaction) -> None:
        bot_uptime = str(datetime.now() - start_time).split(".")[0]
        bot_version = get_bot_version()
        dpy_version = discord.__version__
        py_version = python_version()
        guild_count = len(self.bot.guilds)
        loaded_commands = len(self.bot.tree.get_commands())
        latency = round(self.bot.latency * 1000)
        autoremind_total_count = await self.bot.autoremind_collection.count_documents(
            {}
        )
        autoremind_pound_count = await self.bot.autoremind_collection.count_documents(
            {"pound": {"$gt": 0}}
        )
        autoremind_laf_count = await self.bot.autoremind_collection.count_documents(
            {"laf": {"$gt": 0}}
        )
        mongodb_login_status = (
            "Connected"
            if await check_mongodb_status(self.bot.autoremind_client)
            else "Disconnected"
        )
        chickensmoothie_login_status = (
            "Logged in"
            if await check_chickensmoothie_status(self.bot.web_client)
            else "Not logged in"
        )

        embed = discord.Embed(
            title="CS-Pound Stats",
            description="`Created by blumewmew. CS: haruyuki`",
            color=0x00AE86,
        )
        embed.add_field(name="Bot Uptime", value=bot_uptime, inline=False)

        embed.add_field(name="\u200b", value="**Bot Info**", inline=False)
        embed.add_field(name="Version", value=bot_version)
        embed.add_field(name="discord.py", value=dpy_version)
        embed.add_field(name="Python", value=py_version)
        embed.add_field(name="Guilds", value=guild_count)
        embed.add_field(name="Loaded Commands", value=loaded_commands)
        embed.add_field(name="Latency", value=f"{latency} ms")

        embed.add_field(name="\u200b", value="**AutoRemind Stats**", inline=False)
        embed.add_field(name="Total", value=autoremind_total_count)
        embed.add_field(name="Pound Count", value=autoremind_pound_count)
        embed.add_field(name="Lost and Found Count", value=autoremind_laf_count)

        embed.add_field(name="\u200b", value="**Connection Status**", inline=False)
        embed.add_field(name="MongoDB", value=mongodb_login_status)
        embed.add_field(name="ChickenSmoothie", value=chickensmoothie_login_status)

        await interaction.response.send_message(embed=embed)


def get_bot_version():
    with open("../pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]
