from __future__ import annotations
import re
from dataclasses import dataclass

import aiohttp
import discord
import lxml.html
from discord import app_commands
from discord.ext import commands


@dataclass
class OpeningClosed:
    is_open: bool = False
    event_type: str | None = None
    remaining_minutes: int | None = None


@dataclass
class OpeningOpen:
    is_open: bool = True
    event_type: str = ""
    remaining_count: int = 0


OpeningStatus = OpeningClosed | OpeningOpen


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
            message = format_message(opening_status)
            await interaction.response.send_message(message)
        else:
            message = (
                "Sorry, both the Pound and Lost and Found are closed at the moment."
            )
            await interaction.response.send_message(message)


async def get_opening_status(
    session: aiohttp.ClientSession,
) -> OpeningStatus:
    async with session.get("/poundandlostandfound.php") as resp:
        resp.raise_for_status()
        text = await resp.text()
        dom = lxml.html.fromstring(text)
        opening_string = dom.xpath("//h2[2]/text()")
        is_open_check = dom.xpath("//h2[last()]/text()")

    if is_open_check[0] in [
        "The Pound",
        "The Lost and Found",
    ]:  # If either Pound or Lost and Found is open
        event = is_open_check[0][4:]
        if event == "Lost and Found":
            remaining_selector = dom.xpath('//div[@id="items_remaining"]/text()')
        else:
            remaining_selector = dom.xpath('//div[@id="pets_remaining"]/text()')
        remaining_text = remaining_selector[0] if remaining_selector else ""
        match = re.search(r"\d+", remaining_text)
        remaining_count = int(match.group()) if match else 0
        return OpeningOpen(
            is_open=True, event_type=event, remaining_count=remaining_count
        )

    opening_string = (
        " ".join(opening_string[0].strip().split()) if opening_string else ""
    )
    match = re.search(
        r"(Pound|Lost and Found).*?(?:in:|within)\s*(?:(\d+)\s*hours?)?\s*(?:,?\s*(\d+)\s*minutes?)?",
        opening_string,
    )
    if match:  # If either Pound or Lost and Found is closed
        event = "Pound" if match.group(1) == "pound" else "Lost and Found"
        hours = int(match.group(2)) if match.group(2) else 0
        minutes = int(match.group(3)) if match.group(3) else 0
        total_minutes = hours * 60 + minutes
        return OpeningClosed(
            is_open=False, event_type=event, remaining_minutes=total_minutes
        )

    return OpeningClosed(
        is_open=False, event_type=None, remaining_minutes=None
    )  # If both are closed


def format_message(status: OpeningStatus) -> str:
    hours, minutes = divmod(status.remaining_minutes, 60)

    message = (
        f"The {status.event_type} will open "  # The (Pound/Lost and Found) will open
    )
    if hours > 0:
        message += f"{'within' if hours > 1 else 'in:'} {hours} {'hours' if hours > 1 else 'hour'}"  # (within/in:) X hour(s)

    if minutes > 0:
        if hours > 0:
            message += f", {minutes} {'minutes' if minutes > 1 else 'minute'}."  # , X minute(s).
        else:
            message = f"in: {minutes} {'minutes' if minutes > 1 else 'minute'}."  # in: X minute(s).
    elif hours > 0:
        message += "."

    return message
