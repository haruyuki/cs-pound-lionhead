from __future__ import annotations
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands


class AutoRemindCog(commands.Cog):
    autoremind = app_commands.Group(
        name="autoremind",
        description="AutoRemind related commands",
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @autoremind.command(
        name="set", description="Set AutoReminders for the Pound and Lost and Found"
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
        self, interaction: discord.Interaction, event: Choice[str], minutes: int
    ) -> None:
        if event.value not in ("pound", "laf"):
            await interaction.response.send_message(
                "Invalid event type. Please ensure you have selected either Pound or Lost and Found.",
                ephemeral=True,
            )
            return

        if not 1 <= minutes <= 60:
            await interaction.response.send_message(
                "Invalid time. `minutes` must be between 1 and 60.", ephemeral=True
            )
            return

        user_id = int(interaction.user.id)
        channel_id = int(interaction.channel_id) if interaction.channel_id else 0
        server_id = int(interaction.guild_id) if interaction.guild_id else 0
        event_type = event.value

        async with self.bot.autoremind_db_pool.acquire() as conn:
            cur = await conn.execute(
                "SELECT userID FROM AutoRemind WHERE userID = ?", (user_id,)
            )
            existing = await cur.fetchone()
            if existing:
                await conn.execute(
                    f"UPDATE AutoRemind SET channelID = ?, serverID = ?, {event_type} = ? WHERE userID = ?",
                    (channel_id, server_id, minutes, user_id),
                )
            else:
                pound = minutes if event_type == "pound" else 0
                laf = minutes if event_type == "laf" else 0
                await conn.execute(
                    "INSERT INTO AutoRemind (userID, channelID, serverID, pound, laf) VALUES (?, ?, ?, ?, ?)",
                    (user_id, channel_id, server_id, pound, laf),
                )
            await conn.commit()

        await interaction.response.send_message(
            f"Your {'Pound' if event_type == 'pound' else 'Lost and Found'} auto remind has been set to {minutes} minute{"s" if minutes > 1 else ""} in channel <#{channel_id}>.",
            ephemeral=True,
        )

    @autoremind.command(
        name="remove", description="Cancel auto reminders for the pound and laf"
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

        user_id = int(interaction.user.id)

        async with self.bot.autoremind_db_pool.acquire() as conn:
            cur = await conn.execute(
                f"SELECT {event.value} FROM AutoRemind WHERE userID = ?",
                (user_id,),
            )
            existing = await cur.fetchone()
            if not existing or existing[0] == 0:
                await interaction.response.send_message(
                    "No reminder was found. Are you sure you have an AutoRemind set up?",
                    ephemeral=True,
                )
                return

            previous_autoremind = existing[0] or 0
            await conn.execute(
                f"UPDATE AutoRemind SET {event.value} = 0 WHERE userID = ?",
                (user_id,),
            )

            # Check if both pound and laf are now 0
            cur = await conn.execute(
                "SELECT pound, laf FROM AutoRemind WHERE userID = ?",
                (user_id,),
            )
            updated = await cur.fetchone()
            if updated and updated[0] == 0 and updated[1] == 0:
                await conn.execute(
                    "DELETE FROM AutoRemind WHERE userID = ?",
                    (user_id,),
                )

            await conn.commit()

        await interaction.response.send_message(
            f"Your {previous_autoremind} minute AutoReminder for the {event.name} has been removed.",
            ephemeral=True,
        )
