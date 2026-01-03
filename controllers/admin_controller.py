import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from parsing.add_parsing import AddCommandParser, format_repeat
from services.auth_service import AuthService
from services.tasks_service import TasksService
from services.rewards_service import RewardsService
from repos.users_repo import UsersRepo

logger = logging.getLogger(__name__)


class AdminController:
    def __init__(self, auth: AuthService, tasks_service: TasksService, rewards_service: RewardsService, users_repo: UsersRepo):
        self.auth = auth
        self.tasks_service = tasks_service
        self.rewards_service = rewards_service
        self.users_repo = users_repo

    @staticmethod
    def _parse_expires(value: str) -> str:
        v = value.strip().replace("_", " ")
        datetime.strptime(v, "%Y-%m-%d %H:%M")
        return v

    async def genkey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        if len(context.args) < 2:
            await update.message.reply_text("/genkey <user|admin> <YYYY-MM-DD_HH:MM>")
            return

        role = context.args[0].strip().lower()
        try:
            expires_at = self._parse_expires(context.args[1])
        except Exception:
            await update.message.reply_text("Неверный формат: YYYY-MM-DD_HH:MM")
            return

        key = await self.users_repo.create_registration_key(role, expires_at)
        await update.message.reply_text(
            f"✅ Ключ создан (одноразовый)\nРоль: {role}\nИстекает: {expires_at}\n\nКлюч:\n{key}"
        )

    async def users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        rows = await self.users_repo.list_users()
        if not rows:
            await update.message.reply_text("Пользователей нет.")
            return

        lines = ["👥 Пользователи:\n"]
        for uid, username, role, active, balance in rows:
            lines.append(
                f"{uid} @{username or '-'} role={role} active={'yes' if int(active)==1 else 'no'} balance={balance}"
            )
        await update.message.reply_text("\n".join(lines))

    async def addto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        text = update.message.text or ""
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text("/addto @username <... как в /add ...>")
            return

        target = parts[1].strip()
        payload = parts[2].strip()

        try:
            cmd = AddCommandParser.parse("/add " + payload)
        except Exception:
            await update.message.reply_text("Не удалось разобрать задачу.")
            return

        if cmd.repeat_unit == "once" and cmd.start_dt < datetime.now():
            await update.message.reply_text("⚠️ Дата/время уже в прошлом.")
            return

        try:
            task_id, target_id, next_due = await self.tasks_service.assign_to_username(user.id, target, cmd)
        except ValueError:
            await update.message.reply_text("❌ Пользователь не найден. Он должен хотя бы раз написать боту (/start).")
            return

        await update.message.reply_text(
            f"✅ Назначено @{target.lstrip('@')} (user_id={target_id})\n"
            f"Задача #{task_id}: {cmd.task_text}\n"
            f"⏰ {next_due}\n"
            f"🔁 {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
            f"💰 +{cmd.coins}"
        )

        try:
            await context.bot.send_message(
                chat_id=target_id,
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
            logger.warning("Failed to notify user_id=%s about task_id=%s: %s", target_id, task_id, e)

    async def delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        if not context.args:
            await update.message.reply_text("Формат: /delete <task_id>")
            return

        try:
            task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("task_id должен быть числом.")
            return

        ok = await self.tasks_service.delete_task(task_id)
        await update.message.reply_text("🗑 Удалено." if ok else "Задача не найдена.")

    async def edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        text = update.message.text or ""
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text("/edit <task_id> <... как в /add ...>")
            return

        try:
            task_id = int(parts[1])
        except ValueError:
            await update.message.reply_text("task_id должен быть числом.")
            return

        payload = parts[2].strip()
        try:
            cmd = AddCommandParser.parse("/add " + payload)
        except Exception:
            await update.message.reply_text("Не удалось разобрать формат.")
            return

        if cmd.repeat_unit == "once" and cmd.start_dt < datetime.now():
            await update.message.reply_text("⚠️ Дата/время уже в прошлом.")
            return

        try:
            next_due = await self.tasks_service.edit_task(task_id, cmd)
        except ValueError:
            await update.message.reply_text("Задача не найдена.")
            return

        await update.message.reply_text(
            f"✏️ Задача #{task_id} обновлена:\n"
            f"📝 {cmd.task_text}\n"
            f"⏰ {next_due}\n"
            f"🔁 {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
            f"💰 +{cmd.coins}"
        )

    # ---- rewards admin ----

    async def rewards(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        rows = await self.rewards_service.list_all()
        if not rows:
            await update.message.reply_text("Наград нет.")
            return

        lines = ["🛒 Награды (все):\n"]
        for rid, title, desc, price, is_active_ in rows:
            status = "✅" if int(is_active_) == 1 else "⛔"
            lines.append(f"{status} {rid}. {title} — {price} 💰" + (f" — {desc}" if desc else ""))
        await update.message.reply_text("\n".join(lines))

    async def addreward(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        text = update.message.text or ""
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text("Формат: /addreward <price> <title>")
            return

        try:
            price = int(parts[1])
            if price < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("price должен быть целым числом >= 0")
            return

        title = parts[2].strip()
        rid = await self.rewards_service.add_reward(title=title, price=price, description="")
        await update.message.reply_text(f"✅ Награда добавлена: {rid}. {title} — {price} 💰")

    async def rewarddesc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        text = update.message.text or ""
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text("Формат: /rewarddesc <id> <description>")
            return

        try:
            rid = int(parts[1])
        except ValueError:
            await update.message.reply_text("id должен быть числом")
            return

        ok = await self.rewards_service.set_desc(rid, parts[2].strip())
        await update.message.reply_text("✅ Описание обновлено." if ok else "Награда не найдена.")

    async def rewardon(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        if not context.args:
            await update.message.reply_text("Формат: /rewardon <id>")
            return
        try:
            rid = int(context.args[0])
        except ValueError:
            await update.message.reply_text("id должен быть числом")
            return

        ok = await self.rewards_service.set_active(rid, 1)
        await update.message.reply_text("✅ Включено." if ok else "Награда не найдена.")

    async def rewardoff(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, is_admin, _ = await self.auth.get_flags(user.id)
        if not (is_active and is_admin):
            await update.message.reply_text("⛔ Только админ.")
            return

        if not context.args:
            await update.message.reply_text("Формат: /rewardoff <id>")
            return
        try:
            rid = int(context.args[0])
        except ValueError:
            await update.message.reply_text("id должен быть числом")
            return

        ok = await self.rewards_service.set_active(rid, 0)
        await update.message.reply_text("⛔ Выключено." if ok else "Награда не найдена.")
