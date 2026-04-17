from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .stats import StatsCog

    await bot.add_cog(StatsCog(bot))
