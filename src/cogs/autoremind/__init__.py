from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .autoremind import AutoRemindCog

    await bot.add_cog(AutoRemindCog(bot))
