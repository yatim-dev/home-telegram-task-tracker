import os
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from database import db
from bot.async_db import AsyncDB
from bot.help_controller import HelpController
from bot.task_controller import TaskController
from bot.reminder_service import ReminderService
from bot.admin_controller import AdminController

logger = logging.getLogger(__name__)


class TaskTrackerBot:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_TASK_TRACKER_TOKEN")
        if not self.token:
            raise RuntimeError("Не найден TELEGRAM_TASK_TRACKER_TOKEN в переменных окружения.")

        self.db = AsyncDB(db)
        self.help = HelpController(self.db)
        self.tasks = TaskController(self.db)
        self.reminders = ReminderService(self.db)
        self.admin = AdminController(self.db)

    def build(self) -> Application:
        application = Application.builder().token(self.token).build()

        # Global error handler
        async def on_error(update: object, context):
            logger.exception("Unhandled error: %s", context.error)

        application.add_error_handler(on_error)

        # User commands
        application.add_handler(CommandHandler("start", self.tasks.start))
        application.add_handler(CommandHandler("register", self.tasks.register))
        application.add_handler(CommandHandler("whoami", self.tasks.whoami))

        application.add_handler(CommandHandler("tasks", self.tasks.show_tasks))
        application.add_handler(CommandHandler("done", self.tasks.complete_task))
        application.add_handler(CommandHandler("balance", self.tasks.show_balance))
        application.add_handler(CommandHandler("history", self.tasks.history))

        # Help
        application.add_handler(CommandHandler("help", self.help.help_command))
        application.add_handler(CallbackQueryHandler(self.help.help_callback, pattern=r"^help:"))

        # Admin commands
        application.add_handler(CommandHandler("add", self.tasks.add_task))
        application.add_handler(CommandHandler("genkey", self.admin.genkey))
        application.add_handler(CommandHandler("users", self.admin.users))
        application.add_handler(CommandHandler("addto", self.admin.addto))
        application.add_handler(CommandHandler("delete", self.admin.delete))
        application.add_handler(CommandHandler("edit", self.admin.edit))

        # Reminders job
        if application.job_queue:
            application.job_queue.run_repeating(self.reminders.tick, interval=60, first=10)
        else:
            logger.warning('JobQueue отсутствует. Установите: pip install "python-telegram-bot[job-queue]"')

        async def _post_shutdown(app):
            self.db.shutdown()

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
