import logging

import aiohttp
import lxml.html


async def login(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
) -> bool:
    try:
        payload = {
            "username": username,
            "password": password,
            "redirect": "index.php",
            "autologin": "on",
            "login": "Login",
        }

        logging.debug("Performing login...")
        async with session.post("/Forum/ucp.php?mode=login", data=payload) as resp:
            resp.raise_for_status()
            text = await resp.text()
            dom = lxml.html.fromstring(text)
            login_message = dom.xpath('//div[@id="message"]//p/text()')
            if (
                login_message
                and login_message[0] == "You have been successfully logged in."
            ):
                logging.debug("Login successful.")
                return True

        logging.error("Login failed: unexpected response.")
        return False

    except Exception:
        logging.exception("An error occurred during login, closing session.")
        return False
