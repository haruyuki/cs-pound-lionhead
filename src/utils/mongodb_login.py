import logging
import os

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

logging = logging.getLogger(__name__)


async def mongodb_login() -> tuple[AsyncMongoClient, AsyncCollection]:
    logging.info("Connecting to MongoDB...")
    autoremind_client = AsyncMongoClient(os.getenv("MONGODB_URI"))
    if not await check_mongodb_status(autoremind_client):
        raise Exception("MongoDB connection failed.")
    logging.info("MongoDB connection successful.")
    autoremind_collection = autoremind_client["cs_pound"]["autoremind"]

    return autoremind_client, autoremind_collection


async def check_mongodb_status(autoremind_client: AsyncMongoClient) -> bool:
    try:
        await autoremind_client.admin.command("ping")
        return True
    except PyMongoError:
        return False
