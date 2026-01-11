from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, parse_qs

import discord
from discord import app_commands
from discord.ext import commands

database = "chickensmoothie.db"

MONTHS = {
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
}


class IdentifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="identify", description="Identify the year of a pet or item"
    )
    @app_commands.describe(link="Direct link to the pet or item to identify")
    async def identify(self, interaction: discord.Interaction, link: str) -> None:
        if not is_valid_chickensmoothie_link(link):
            await interaction.response.send_message(
                "Please provide a valid ChickenSmoothie link.", ephemeral=True
            )
            return

        if "trans" in link:  # Pet with items attached
            await interaction.response.send_message(
                "Pets with items are unable to be identified :frowning:", ephemeral=True
            )
            return

        if "item" in link:
            data = None
            async with self.bot.db_pool.acquire() as conn:
                async with conn.execute(
                    "SELECT itemName, itemEvent, itemYear, itemLink FROM Items WHERE itemLID = ? AND itemRID = ?",
                    extract_item_ids(link),
                ) as cursor:
                    data = await cursor.fetchone()

            if data is not None:
                item_name = data[0]
                item_event = data[1]
                item_year = data[2]
                item_link = data[3]

                message = (
                    prepare_message(
                        item_name, item_event, item_year, item_link, is_pet=False
                    )
                    + f" [⠀]({link})"
                )
                await interaction.response.send_message(message)
                return
            else:
                logging.error("Item not found in database for link: %s", link)
                await interaction.response.send_message(
                    "An error occurred while identifying the item. Please try a different link.",
                    ephemeral=True,
                )
            return

        if "k=" in link:  # Pet link
            data = None
            link_query = urlparse(link).query
            pet_id = parse_qs(link_query).get("k", [None])[0]
            async with self.bot.db_pool.acquire() as conn:
                async with conn.execute(
                    "SELECT petEvent, petYear, petLink, petLink FROM Pets WHERE petID = ?",
                    (pet_id,),
                ) as cursor:
                    data = await cursor.fetchone()

            if data is not None:
                pet_name = None
                pet_event = data[0]
                pet_year = data[1]
                pet_link = data[2]
                message = (
                    prepare_message(
                        pet_name, pet_event, pet_year, pet_link, is_pet=True
                    )
                    + f" [⠀]({link})"
                )
                await interaction.response.send_message(message)
                return
            else:
                logging.error("Pet not found in database for link: %s", link)
                await interaction.response.send_message(
                    "An error occurred while identifying the pet. Please try a different link.",
                    ephemeral=True,
                )

        logging.error("Could not identify pet or item from link: %s", link)
        await interaction.response.send_message(
            "Could not identify the pet or item. Please try a different link.",
            ephemeral=True,
        )


def is_valid_chickensmoothie_link(link: str) -> bool:
    hostname = urlparse(link).hostname
    return hostname in {
        "www.chickensmoothie.com",
        "chickencdn.com",
        "static.chickensmoothie.com",
    }


def extract_item_ids(link: str) -> Tuple[Optional[int], Optional[int]]:
    path = urlparse(link).path
    m = re.search(r"/item/(\d+)&p=(\d+)", path)
    if not m:
        return None, None
    left_id = int(m.group(1))
    right_id = int(m.group(2))
    return left_id, right_id


def prepare_message(
    name: Optional[str], event: str, year: int, link: str, is_pet: bool = True
) -> str:
    is_month = event in MONTHS
    entity_type = "pet" if is_pet else "item"

    name_part = f"'{name}' " if name else ""
    event_part = f"{event} {year}" if is_month else f"{year} {event}"

    return f"That {entity_type} is {name_part}from {event_part}.\nArchive Link: {link}"
