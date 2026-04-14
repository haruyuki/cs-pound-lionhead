from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .progeny import ProgenyCog

    await bot.add_cog(ProgenyCog(bot))
