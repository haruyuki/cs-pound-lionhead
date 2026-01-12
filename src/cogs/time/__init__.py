from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .time import TimeCog

    await bot.add_cog(TimeCog(bot))
