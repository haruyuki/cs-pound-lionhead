from __future__ import annotations

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands
from markdownify import MarkdownConverter
from reader import make_reader

feed_url = "https://chickensmoothie.com/rss.php?feed=news"

logger = logging.getLogger(__name__)


class NewsCog(
    commands.GroupCog, name="news", description="ChickenSmoothie news related commands"
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="latest", description="Show the latest ChickenSmoothie news"
    )
    async def latest(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        reader = make_reader("../db.sqlite")
        feed = reader.get_feed(feed_url)
        logger.info("Read %s (Last changed at %s)", feed.title, feed.updated)
        latest = list(reader.get_entries(feed=feed_url, read=False))[9]
        news_title = latest.title
        news_content = md(latest.summary)
        news_link = latest.link
        embed = discord.Embed(
            title=news_title, description=news_content, color=0xE0F6B2, url=news_link
        )
        if latest_img := extract_first_img(latest.summary):
            embed.set_image(url=latest_img)
        await interaction.edit_original_response(embed=embed)


def extract_first_img(html: str) -> str | None:
    match = re.search(r'<img[^>]+src="([^"]+)"', html)
    if match:
        return match.group(1)
    return None


class CustomMarkdownConverter(MarkdownConverter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._skip_next_br = 0

    def convert_img(self, el, text, parent_tags):
        # When <img> found, set flag to skip next two <br>
        self._skip_next_br = 2
        return ""  # Strip image

    def convert_br(self, el, text, parent_tags):
        if self._skip_next_br > 0:
            self._skip_next_br -= 1
            return ""  # Skip this <br>
        return super().convert_br(el, text, parent_tags)

    def convert_span(self, el, text, parent_tags):
        style = el.attrs.get("style", None) or ""
        if "font-size: 150%" in style:
            return f"## {text}\n"
        if "font-weight: bold" in style:
            return f"**{text}**"
        return text


def md(html, **options):
    return CustomMarkdownConverter(**options).convert(html)
