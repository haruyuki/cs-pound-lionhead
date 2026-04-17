import logging
import os

import aiohttp
import lxml.html

logging = logging.getLogger(__name__)


async def chickensmoothie_login(session: aiohttp.ClientSession) -> None:
    payload = {
        "username": os.getenv("CS_USERNAME"),
        "password": os.getenv("CS_PASSWORD"),
        "redirect": "index.php",
        "autologin": "on",
        "login": "Login",
    }

    logging.debug("Logging into ChickenSmoothie...")
    async with session.post("/Forum/ucp.php?mode=login", data=payload) as resp:
        resp.raise_for_status()
        text = await resp.text()
        dom = lxml.html.fromstring(text)
        login_message = dom.xpath('//div[@id="message"]//p/text()')
        if (
            login_message
            and login_message[0] == "You have been successfully logged in."
        ):
            logging.info("ChickenSmoothie login successful.")
        else:
            raise Exception("ChickenSmoothie login failed.")


async def check_chickensmoothie_status(session: aiohttp.ClientSession) -> bool:
    async with session.get("/") as resp:
        if resp.status == 200:
            text = await resp.text()
            dom = lxml.html.fromstring(text)
            logout_string = dom.xpath('//li[@class="icon-logout"]/a/text()')
            if logout_string and os.getenv("CS_USERNAME") in logout_string[0]:
                return True
        return False
