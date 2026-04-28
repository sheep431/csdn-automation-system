from __future__ import annotations

import asyncio

from app.browser.session_manager import BrowserSessionManager
from app.publishers.csdn_publisher import CSDNPublisher


async def main() -> None:
    session = BrowserSessionManager()
    page = await session.new_page()
    publisher = CSDNPublisher(page)

    await publisher.open_editor()
    print("CSDN editor opened. Please complete login manually in the browser window.")
    print("The browser will stay open for 10 minutes. After login, return here and tell Hermes '登录好了'.")

    try:
        await asyncio.sleep(600)
    finally:
        await session.close()


if __name__ == '__main__':
    asyncio.run(main())
