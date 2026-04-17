import asyncio
import logging

from reader import make_reader

feed_url = "https://chickensmoothie.com/rss.php?feed=news"
logger = logging.getLogger(__name__)


async def rss_feed_task(bot):
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            logger.info("Updating RSS feed...")
            reader = make_reader("../db.sqlite")
            await asyncio.to_thread(reader.add_feed, feed_url, exist_ok=True)
            await asyncio.to_thread(reader.update_feeds)
            logger.info("RSS feed updated.")
        except Exception as e:
            logger.exception(f"Error updating news feed: {e}")
        await asyncio.sleep(3600)  # 1 hour
