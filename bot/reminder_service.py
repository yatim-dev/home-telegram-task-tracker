import logging
import asyncio
from datetime import datetime
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ReminderService:
    def __init__(self, db):
        self.db = db
        self._lock = asyncio.Lock()

    async def tick(self, context: ContextTypes.DEFAULT_TYPE):
        # если прошлый тик ещё работает — этот пропускаем
        if self._lock.locked():
            return

        async with self._lock:
            due_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            tasks = await self.db.get_tasks_to_remind(due_str=due_str)
            if not tasks:
                return

            notified_ids: list[int] = []

            for task_id, user_id, task_text, next_due, coins in tasks:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"⏰ Напоминание!\n"
                            f"📝 {task_text}\n"
                            f"🕒 Время: {next_due}\n"
                            f"💰 Награда: +{coins}\n\n"
                            f"Чтобы отметить выполнение:\n"
                            f"/done {task_id}\n"
                            f"Посмотреть список: /tasks"
                        ),
                    )
                    notified_ids.append(task_id)
                except Exception as e:
                    logger.warning("Failed to send reminder to user_id=%s task_id=%s: %s", user_id, task_id, e)

            # 1 коммит
            if notified_ids:
                await self.db.mark_tasks_notified(notified_ids, due_str=due_str)
