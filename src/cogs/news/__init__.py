from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .news import NewsCog

    await bot.add_cog(NewsCog(bot))
