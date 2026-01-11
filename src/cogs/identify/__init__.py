async def setup(bot: commands.Bot) -> None:
    from .identify import IdentifyCog

    await bot.add_cog(IdentifyCog(bot))
