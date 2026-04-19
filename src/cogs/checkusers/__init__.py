from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .checkusers import CheckUsersCog

    await bot.add_cog(CheckUsersCog(bot))
