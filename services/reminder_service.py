import asyncio
import logging
from datetime import datetime
from telegram.ext import ContextTypes

from repos.tasks_repo import TasksRepo

logger = logging.getLogger(__name__)


class ReminderService:
    def __init__(self, tasks: TasksRepo):
        self.tasks = tasks
        self._lock = asyncio.Lock()

    async def tick(self, context: ContextTypes.DEFAULT_TYPE):
        if self._lock.locked():
            return

        async with self._lock:
            due_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            rows = await self.tasks.get_tasks_to_remind(due_str)
            if not rows:
                return

            notified_ids: list[int] = []
            for task_id, user_id, task_text, next_due, coins in rows:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            "⏰ Напоминание!\n"
                            f"📝 {task_text}\n"
                            f"🕒 Время: {next_due}\n"
                            f"💰 Награда: +{coins}\n\n"
                            f"Отметить выполнение: /done {task_id}\n"
                            f"Список задач: /tasks"
                        ),
                    )
                    notified_ids.append(task_id)
                except Exception as e:
                    logger.warning("Failed to send reminder to user_id=%s task_id=%s: %s", user_id, task_id, e)

            if notified_ids:
                await self.tasks.mark_tasks_notified(notified_ids, due_str)
