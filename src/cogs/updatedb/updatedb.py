from __future__ import annotations

import asyncio
import datetime
import logging
from urllib.parse import unquote, urljoin

import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal

from src.cogs.updatedb.update_archive import (
    ArchiveEvent,
    get_category,
    fetch_event_links,
    process_event,
    get_event_title,
)

CATEGORY_NAMES = {
    "monthly": "Monthly Events",
    "special": "Special Events",
}

CATEGORY_DATA = {
    "monthly": (0, CATEGORY_NAMES["monthly"]),
    "special": (1, CATEGORY_NAMES["special"]),
}


class UpdateDbCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="updatedb", description="Update the database with the latest data"
    )
    @app_commands.describe(year="The year to update", table="Pets or Items database")
    @app_commands.choices(
        table=[
            app_commands.Choice(name="Pets", value="pets"),
            app_commands.Choice(name="Items", value="items"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def updatedb(
        self,
        interaction: discord.Interaction,
        year: app_commands.Range[int, 2008, datetime.datetime.now().year],
        table: Literal["pets", "items"],
    ) -> None:
        await interaction.response.send_message(
            f"Preparing updating {table} database for year {year}..."
        )

        event_links = await fetch_event_links(self.bot.web_client, year, table)

        events: list[ArchiveEvent] = []
        monthly_events: list[ArchiveEvent] = []
        special_events: list[ArchiveEvent] = []
        processing_status: dict[str, str] = {}
        embed_bucket: dict[str, tuple[list[ArchiveEvent], int, str]] = {}
        for event in event_links:
            clean_link = unquote(event.split("?")[0])

            event_title = get_event_title(clean_link)
            event_link = urljoin("https://www.chickensmoothie.com", clean_link)
            new_event = ArchiveEvent(
                title=event_title,
                link=event_link,
            )
            events.append(new_event)

            category = get_category(event_title)
            event_type = monthly_events if category == "monthly" else special_events
            event_type.append(new_event)

            category_index, category_name = CATEGORY_DATA[category]
            embed_bucket[event_link] = (event_type, category_index, category_name)

        embed = discord.Embed(
            color=0x00AE86,
            title=f"Updating {table} database for year {year}",
            description=f"Processing events...",
        )
        embed.add_field(
            name=CATEGORY_NAMES["monthly"],
            value=format_embed_value(monthly_events, processing_status),
            inline=False,
        )
        embed.add_field(
            name=CATEGORY_NAMES["special"],
            value=format_embed_value(special_events, processing_status),
            inline=False,
        )
        embed.timestamp = discord.utils.utcnow()

        await interaction.edit_original_response(
            content=None,
            embeds=[embed],
        )

        total_added = 0
        async with self.bot.archive_db_pool.acquire() as conn:
            for event in events:
                bucket_info = embed_bucket.get(event.link)

                event_type, category_index, category_name = bucket_info

                processing_status[event.link] = "🔄 Processing..."
                update_embed_field(
                    embed,
                    event_type,
                    category_index,
                    category_name,
                    processing_status,
                )
                await interaction.edit_original_response(embeds=[embed])

                event_result = await process_event(
                    self.bot.web_client,
                    conn,
                    event,
                    table,
                    year,
                )

                group_count, added_stats = event_result
                await conn.commit()
                total_added += added_stats

                processing_status[event.link] = (
                    f"✅ Added {group_count} group{'s' if group_count > 1 else ''} (+{added_stats} {table})"
                )
                update_embed_field(
                    embed,
                    event_type,
                    category_index,
                    category_name,
                    processing_status,
                )
                await interaction.edit_original_response(embeds=[embed])

                await asyncio.sleep(1)

        embed.description = f"Update complete. Total {total_added} {table} added"
        embed.colour = discord.Color.green()
        await interaction.edit_original_response(embeds=[embed])

    @updatedb.error
    async def updatedb_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        namespace = getattr(interaction, "namespace", None)
        table = getattr(namespace, "table", "unknown")
        year = getattr(namespace, "year", "unknown")

        try:
            raise error
        except Exception:
            logging.exception(
                "Error in /updatedb command for table=%s year=%s", table, year
            )

        if interaction.response.is_done():
            await interaction.edit_original_response(
                content="An error occurred while updating the database.",
                embeds=[],
            )
        else:
            await interaction.response.send_message(
                "An error occurred while updating the database."
            )


def format_embed_value(
    events: list[ArchiveEvent],
    processing_status: dict[str, str],
) -> str:
    return "\n".join(
        f"{event.title}: {processing_status.get(event.link, "⏳ Waiting")}"
        for event in events
    )


def update_embed_field(
    embed: discord.Embed,
    events: list[ArchiveEvent],
    field_index: int,
    field_name: str,
    status_by_link: dict[str, str],
) -> None:
    value = format_embed_value(events, status_by_link)
    embed.set_field_at(field_index, name=field_name, value=value, inline=False)
