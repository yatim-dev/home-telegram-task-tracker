from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import AuthService
from bot.parsing import AddCommandParser, format_repeat
import logging
logger = logging.getLogger(__name__)

class AdminController:
    def __init__(self, db):
        self.db = db  # AsyncDB
        self.auth = AuthService(db)

    @staticmethod
    def _parse_expires(value: str) -> str:
        """
        Принимает "YYYY-MM-DD_HH:MM" или "YYYY-MM-DD HH:MM"
        Возвращает "YYYY-MM-DD HH:MM"
        """
        v = value.strip().replace("_", " ")
        datetime.strptime(v, "%Y-%m-%d %H:%M")
        return v

    async def genkey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_admin(update):
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Формат:\n"
                "/genkey <user|admin> <YYYY-MM-DD_HH:MM>\n"
                "Пример:\n"
                "/genkey user 2026-01-10_12:00"
            )
            return

        role = context.args[0].strip().lower()
        try:
            expires_at = self._parse_expires(context.args[1])
        except Exception:
            await update.message.reply_text("Неверный формат даты. Нужно: YYYY-MM-DD_HH:MM")
            return

        try:
            key = await self.db.create_registration_key(role, expires_at)
        except Exception as e:
            await update.message.reply_text(f"Не удалось создать ключ: {e}")
            return

        await update.message.reply_text(
            "✅ Ключ создан (одноразовый)\n"
            f"Роль: {role}\n"
            f"Истекает: {expires_at}\n\n"
            f"Ключ:\n{key}\n\n"
            "Отправьте пользователю:\n"
            f"/start {key}\n"
            f"или /register {key}"
        )

    async def users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_admin(update):
            return

        rows = await self.db.list_users()
        if not rows:
            await update.message.reply_text("Пользователей нет.")
            return

        lines = ["👥 Пользователи:\n"]
        for user_id, username, role, is_active, balance in rows:
            lines.append(
                f"{user_id}  @{username or '-'}  role={role}  active={'yes' if int(is_active)==1 else 'no'}  balance={balance}"
            )

        await update.message.reply_text("\n".join(lines))

    async def addto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /addto @username <...payload как в /add...>
        """
        if not await self.auth.require_admin(update):
            return

        text = update.message.text or ""
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text(
                "Формат:\n"
                "/addto @username <задача...>\n\n"
                "Пример:\n"
                "/addto @vasya Помыть посуду 18:30 10"
            )
            return

        target = parts[1].strip()
        payload = parts[2].strip()

        user_id = await self.db.find_user_id_by_username(target)
        if not user_id:
            await update.message.reply_text(
                "❌ Пользователь не найден.\n"
                "Важно: пользователь должен хотя бы раз написать боту (/start), "
                "чтобы его username попал в базу."
            )
            return

        try:
            cmd = AddCommandParser.parse("/add " + payload)
        except Exception:
            await update.message.reply_text(
                "Не удалось разобрать задачу.\n"
                "Примеры:\n"
                "/addto @vasya Помыть посуду 18:30 10\n"
                "/addto @vasya Сдать проект 2026-01-10 12:00 50 once"
            )
            return

        if cmd.repeat_unit == "once" and cmd.start_dt < datetime.now():
            await update.message.reply_text("⚠️ Дата/время уже в прошлом. Для разовой задачи укажите будущую дату.")
            return

        next_due = cmd.start_dt.strftime("%Y-%m-%d %H:%M")
        admin_id = update.effective_user.id

        task_id = await self.db.add_task(
            user_id=user_id,
            task=cmd.task_text,
            next_due=next_due,
            coins=cmd.coins,
            repeat_unit=cmd.repeat_unit,
            repeat_every=cmd.repeat_every,
            assigned_by=admin_id,
        )

        # 1) Ответ админу
        await update.message.reply_text(
            f"✅ Назначено @{target.lstrip('@')} (user_id={user_id})\n"
            f"Задача #{task_id}: {cmd.task_text}\n"
            f"⏰ {next_due}\n"
            f"🔁 {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
            f"💰 +{cmd.coins}"
        )

        # 2) Уведомление пользователю
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "📌 Вам назначена новая задача!\n"
                    f"📝 {cmd.task_text}\n"
                    f"⏰ Следующее напоминание: {next_due}\n"
                    f"🔁 Повтор: {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
                    f"💰 Награда: +{cmd.coins}\n\n"
                    "Посмотреть задачи: /tasks"
                ),
            )
        except Exception as e:
            logger.warning("Failed to notify user_id=%s about task_id=%s: %s", user_id, task_id, e)

    async def delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_admin(update):
            return

        if not context.args:
            await update.message.reply_text("Формат: /delete <task_id>\nПример: /delete 12")
            return

        try:
            task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("task_id должен быть числом. Пример: /delete 12")
            return

        row = await self.db.get_task(task_id)
        if not row:
            await update.message.reply_text("Задача не найдена.")
            return

        deleted = await self.db.delete_task(task_id)
        if deleted:
            await update.message.reply_text(f"🗑 Задача #{task_id} удалена.")
        else:
            await update.message.reply_text("Не удалось удалить задачу (возможно уже удалена).")

    async def edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /edit <task_id> <...payload как в /add...>
        Пример:
          /edit 12 Протереть пыль 2026-01-03 18:00 5 every:3d
        """
        if not await self.auth.require_admin(update):
            return

        text = update.message.text or ""
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text(
                "Формат:\n"
                "/edit <task_id> <задача...>\n\n"
                "Пример:\n"
                "/edit 12 Протереть пыль 2026-01-03 18:00 5 every:3d"
            )
            return

        try:
            task_id = int(parts[1])
        except ValueError:
            await update.message.reply_text("task_id должен быть числом. Пример: /edit 12 ...")
            return

        existing = await self.db.get_task(task_id)
        if not existing:
            await update.message.reply_text("Задача не найдена.")
            return

        payload = parts[2].strip()
        try:
            cmd = AddCommandParser.parse("/add " + payload)
        except Exception:
            await update.message.reply_text(
                "Не удалось разобрать формат.\n"
                "Примеры:\n"
                "/edit 12 Помыть посуду 18:30 10\n"
                "/edit 12 Сдать проект 2026-01-10 12:00 50 once"
            )
            return

        if cmd.repeat_unit == "once" and cmd.start_dt < datetime.now():
            await update.message.reply_text("⚠️ Дата/время уже в прошлом. Для разовой задачи укажите будущую дату.")
            return

        next_due = cmd.start_dt.strftime("%Y-%m-%d %H:%M")
        updated = await self.db.update_task(
            task_id=task_id,
            task=cmd.task_text,
            next_due=next_due,
            coins=cmd.coins,
            repeat_unit=cmd.repeat_unit,
            repeat_every=cmd.repeat_every,
        )

        if not updated:
            await update.message.reply_text("Не удалось обновить задачу.")
            return

        await update.message.reply_text(
            f"✏️ Задача #{task_id} обновлена:\n"
            f"📝 {cmd.task_text}\n"
            f"⏰ {next_due}\n"
            f"🔁 {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
            f"💰 +{cmd.coins}"
        )
