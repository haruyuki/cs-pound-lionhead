from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    from .updatedb import UpdateDbCog

    await bot.add_cog(UpdateDbCog(bot))
