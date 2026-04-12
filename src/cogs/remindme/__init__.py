from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .remindme import RemindMeCog

    await bot.add_cog(RemindMeCog(bot))

