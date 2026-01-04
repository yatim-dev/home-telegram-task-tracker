import os
import logging

from telegram import Update
from telegram.ext import Application

from app.container import Container
from app.routes import register_routes

logger = logging.getLogger(__name__)


class TaskTrackerBot:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_TASK_TRACKER_TOKEN")
        if not self.token:
            raise RuntimeError("Не найден TELEGRAM_TASK_TRACKER_TOKEN в переменных окружения.")

        db_path = os.environ.get("DB_PATH", "tasks.db")
        self.container = Container(db_path)

    def build(self) -> Application:
        application = Application.builder().token(self.token).build()

        async def on_error(update: object, context):
            logger.exception("Unhandled error: %s", context.error)

        application.add_error_handler(on_error)

        register_routes(application, self.container)

        if application.job_queue:
            application.job_queue.run_repeating(self.container.reminder_service.tick, interval=60, first=10)
        else:
            logger.warning('JobQueue отсутствует. Установите: pip install "python-telegram-bot[job-queue]"')

        async def _post_shutdown(app: Application):
            # корректно закрываем executor + sqlite
            await self.container.db.aclose()

        application.post_shutdown = _post_shutdown
        return application

    def run(self):
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)

        app = self.build()
        app.run_polling(allowed_updates=Update.ALL_TYPES)
