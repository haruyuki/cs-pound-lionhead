from __future__ import annotations

import io
import os
from collections import defaultdict

import discord
from discord import app_commands
from discord.errors import NotFound, HTTPException, Forbidden
from discord.ext import commands

GUILD_ID = int(os.getenv("DEV_GUILD_ID") or 0)


class CheckUsersCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="checkusers", description="Cleans up AutoRemind users.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def checkusers(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        users = await self.bot.autoremind_collection.find({}).to_list(length=None)

        guild_users = defaultdict(list)
        for user in users:
            server_id = user.get("server_id")
            guild_users[server_id].append(user)

        total = sum(len(lst) for lst in guild_users.values())
        checked = 0
        progress_msg = await interaction.followup.send(
            f"Checking users... 0/{total} done", ephemeral=True
        )

        missing_by_guild = {}
        missing_guilds = set()
        for server_id, user_list in guild_users.items():
            guild = self.bot.get_guild(int(server_id))
            if not guild:
                missing_guilds.add(server_id)
                checked += len(user_list)
                await progress_msg.edit(
                    content=f"Checking users... {checked}/{total} done"
                )
                continue
            missing = []
            for user in user_list:
                user_id = int(user["user_id"])
                checked += 1
                try:
                    await guild.fetch_member(user_id)
                except NotFound:
                    missing.append(user["user_id"])
                except (HTTPException, Forbidden):
                    missing.append(user["user_id"])
                if checked % 20 == 0 or checked == total:
                    await progress_msg.edit(
                        content=f"Checking users... {checked}/{total} done"
                    )
            if missing:
                missing_by_guild[server_id] = missing

        if not missing_by_guild and not missing_guilds:
            await progress_msg.edit(
                content="All AutoRemind users are still in their guilds."
            )
            return

        lines = []
        for server_id in missing_guilds:
            lines.append(f"Bot not in guild `{server_id}`.")
            lines.append("")
        for server_id, user_ids in missing_by_guild.items():
            guild = self.bot.get_guild(int(server_id))
            name = guild.name if guild else f"Unknown"
            lines.append(f"**{name} ({server_id})**")
            for uid in user_ids:
                lines.append(f"*`{uid}` is no longer in this guild.")
            lines.append("")

        result = "\n".join(lines)
        if len(result) > 1900:
            file = discord.File(
                io.BytesIO(result.encode()), filename="missing_users.txt"
            )
            await progress_msg.edit(
                content="Result too long, see attached.", attachments=[file]
            )
        else:
            await progress_msg.edit(content=result)
