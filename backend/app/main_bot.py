import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Message

from app.core.config import get_settings
from app.core.logging import configure_logging

log = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.telegram.bot_token:
        log.warning("TELEGRAM__BOT_TOKEN not set; bot will not start")
        return

    bot = Bot(
        token=settings.telegram.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = RedisStorage.from_url(settings.redis.url)
    dp = Dispatcher(storage=storage)

    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer("Scrumban bot. Link this chat in web UI to start using it.")

    log.info("bot_start", extra={"mode": settings.telegram.mode})
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
