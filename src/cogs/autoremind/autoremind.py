from __future__ import annotations

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from tasks import autoremind_remove_handler, autoremind_add_handler


class AutoRemindCog(commands.Cog):
    autoremind = app_commands.Group(
        name="autoremind",
        description="AutoRemind related commands",
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @autoremind.command(
        name="set", description="Set AutoReminds for the Pound and Lost and Found"
    )
    @app_commands.describe(
        event="Reminder for Pound or Lost and Found?",
        minutes="How many minutes before opening to be reminded. (Between 1 and 60)",
    )
    @app_commands.choices(
        event=[
            Choice(name="Pound", value="pound"),
            Choice(name="Lost and Found", value="laf"),
        ]
    )
    async def set(
        self,
        interaction: discord.Interaction,
        event: Choice[str],
        minutes: app_commands.Range[int, 1, 60],
    ) -> None:
        user_id = int(interaction.user.id)
        channel_id = interaction.channel_id or 0
        server_id = interaction.guild_id or 0
        event_type = event.value

        set_on_insert = {
            "pound": 0,
            "laf": 0,
        }
        set_on_insert.pop(event_type)  # Remove event_type since $set will set it

        await self.bot.autoremind_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "server_id": server_id,
                    event_type: minutes,
                },
                "$setOnInsert": set_on_insert,
            },
            upsert=True,
        )

        await autoremind_add_handler(
            self.bot.autoremind_collection,
            event_type,
            minutes,
        )

        event_label = "Pound" if event_type == "pound" else "Lost and Found"
        minutes_label = "minute" if minutes == 1 else "minutes"

        await interaction.response.send_message(
            f"Your {event_label} AutoRemind has been set to {minutes} {minutes_label} in <#{channel_id}> channel.",
            ephemeral=True,
        )

    @autoremind.command(
        name="remove", description="Cancel AutoReminds for the pound and laf"
    )
    @app_commands.choices(
        event=[
            Choice(name="Pound", value="pound"),
            Choice(name="Lost and Found", value="laf"),
        ]
    )
    async def remove(
        self, interaction: discord.Interaction, event: Choice[str]
    ) -> None:
        if event.value not in ("pound", "laf"):
            await interaction.response.send_message(
                "Invalid event type. Please ensure you have selected either Pound or Lost and Found.",
                ephemeral=True,
            )
            return

        user_id = interaction.user.id

        existing = await self.bot.autoremind_collection.find_one({"user_id": user_id})
        if not existing or existing.get(event.value, 0) == 0:
            await interaction.response.send_message(
                f"No {event.name} AutoRemind was found. Are you sure you have one set up?",
                ephemeral=True,
            )
            return

        previous_autoremind = int(existing.get(event.value, 0) or 0)
        await self.bot.autoremind_collection.update_one(
            {"user_id": user_id},
            {"$set": {event.value: 0}},
        )

        await autoremind_remove_handler(
            self.bot.autoremind_collection,
            event.value,
        )

        updated = await self.bot.autoremind_collection.find_one(
            {"user_id": user_id}, projection={"pound": 1, "laf": 1}
        )
        if updated and updated.get("pound", 0) == 0 and updated.get("laf", 0) == 0:
            await self.bot.autoremind_collection.delete_one({"user_id": user_id})

        await interaction.response.send_message(
            f"Your {previous_autoremind} minute AutoRemind for the {event.name} has been removed.",
            ephemeral=True,
        )
