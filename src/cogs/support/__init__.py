from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .support import SupportCog

    await bot.add_cog(SupportCog(bot))
