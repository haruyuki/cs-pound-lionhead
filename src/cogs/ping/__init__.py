async def setup(bot: commands.Bot) -> None:
    from .ping import PingCog

    await bot.add_cog(PingCog(bot))
