from __future__ import annotations

import asyncio
import io
import math
from urllib.parse import parse_qsl, urljoin, urlsplit

import aiohttp
import discord
from PIL import Image
from discord import app_commands
from discord.ext import commands
from lxml import html as lxml_html

ELEMENTS: dict[str, int] = {
    "earth": 1,
    "plague": 2,
    "wind": 3,
    "water": 4,
    "lightning": 5,
    "ice": 6,
    "shadow": 7,
    "light": 8,
    "arcane": 9,
    "nature": 10,
    "fire": 11,
}

ELEMENT_CHOICES = [
    app_commands.Choice(name=element_name.capitalize(), value=element_name)
    for element_name in ELEMENTS
]

PROGENY_URL = (
    "https://flightrising.com/includes/ol/scryer_progeny.php?id1={id1}&id2={id2}"
)
CUSTOM_URL = "https://www1.flightrising.com/scrying/ajax-predict"
FORESEE_COUNT = 4


class ProgenyCog(
    commands.GroupCog, name="flightrising", description="Flight Rising related commands"
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="progeny",
        description="See the possible offspring of two dragons",
    )
    @app_commands.describe(
        dragon1="First dragon ID",
        dragon2="Second dragon ID",
        element="Offspring element. Defaults to shadow",
    )
    @app_commands.choices(element=ELEMENT_CHOICES)
    async def progeny(
        self,
        interaction: discord.Interaction,
        dragon1: int,
        dragon2: int,
        element: str = "shadow",
    ) -> None:
        await interaction.response.defer(thinking=True)

        dragon1_id = str(dragon1)
        dragon2_id = str(dragon2)

        element_id = ELEMENTS[element]

        try:
            session = self.bot.web_client
            foresee_pages = await asyncio.gather(
                *[
                    get_page(session, dragon1_id, dragon2_id)
                    for _ in range(FORESEE_COUNT)
                ]
            )

            links = [link for page_links in foresee_pages for link in page_links]
            if element != "shadow":
                predict_links = await asyncio.gather(
                    *[
                        post_custom_link(session, build_payload(link, element_id))
                        for link in links
                    ]
                )
                links = [link for link in predict_links if link]

            tasks = [get_image(session, link) for link in links]
            images = await asyncio.gather(*tasks)
            if not images:
                raise RuntimeError("No images returned")

            canvas = generate_image(images)

            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG")
            buffer.seek(0)

            dragon1_url = f"https://www1.flightrising.com/dragon/{dragon1_id}"
            dragon2_url = f"https://www1.flightrising.com/dragon/{dragon2_id}"
            content = f"[{dragon1_id}]({dragon1_url}) ↔ [{dragon2_id}]({dragon2_url}) ({element.capitalize()})"

            await interaction.followup.send(
                content=content, file=discord.File(fp=buffer, filename="progeny.png")
            )
        except aiohttp.ClientError:
            await interaction.followup.send(
                "FR request failed.",
                ephemeral=True,
            )
            return
        except (ValueError, RuntimeError):
            await interaction.followup.send(
                "Could not build progeny image.",
                ephemeral=True,
            )
            return


async def get_page(
    session: aiohttp.ClientSession, dragon1_id: str, dragon2_id: str
) -> list[str]:
    url = PROGENY_URL.format(id1=dragon1_id, id2=dragon2_id)
    async with session.get(url) as resp:
        resp.raise_for_status()
        text = await resp.text()

    dom = lxml_html.fromstring(text)
    links = []
    for src in dom.xpath("//img/@src"):
        if src:
            links.append(urljoin("https://www1.flightrising.com", src))
    return links


def build_payload(link: str, element_id: int) -> dict[str, str]:
    parts = urlsplit(link)
    payload = dict(parse_qsl(parts.query, keep_blank_values=True))
    payload.pop("auth", None)
    payload.pop("dummyext", None)
    payload["age"] = "0"
    payload["element"] = str(element_id)
    return payload


async def post_custom_link(
    session: aiohttp.ClientSession, payload: dict[str, str]
) -> str:
    async with session.post(CUSTOM_URL, data=payload) as response:
        response.raise_for_status()
        data = await response.json(content_type=None)

    dragon_url = data.get("dragon_url")
    return urljoin("https://www1.flightrising.com", dragon_url)


async def get_image(session: aiohttp.ClientSession, link: str) -> Image.Image:
    async with session.get(link) as response:
        response.raise_for_status()
        image_bytes = await response.read()

    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGBA").copy()


def generate_image(images: list[Image.Image]) -> Image.Image:
    if not images:
        raise ValueError("No images to compose")

    cell_width, cell_height = images[0].size
    images_per_row = 4
    rows = math.ceil(len(images) / images_per_row)
    canvas = Image.new(
        "RGBA", (images_per_row * cell_width, rows * cell_height), "#DEDACF"
    )

    for index, image in enumerate(images):
        row, column = divmod(index, images_per_row)
        left = column * cell_width
        top = row * cell_height
        canvas.paste(image, (left, top), image)

    return canvas
