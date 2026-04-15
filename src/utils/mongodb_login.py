import logging
import os

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

logging = logging.getLogger(__name__)


async def mongodb_login() -> tuple[AsyncMongoClient, AsyncCollection]:
    logging.info("Connecting to MongoDB...")
    autoremind_client = AsyncMongoClient(os.getenv("MONGODB_URI"))
    try:
        await autoremind_client.admin.command("ping")
        logging.info("MongoDB connection successful.")
    except PyMongoError:
        logging.exception("MongoDB connection failed.")
        raise
    autoremind_collection = autoremind_client["cs_pound"]["autoremind"]

    return autoremind_client, autoremind_collection
