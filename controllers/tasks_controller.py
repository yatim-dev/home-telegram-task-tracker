from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from parsing.add_parsing import AddCommandParser, format_repeat
from services.auth_service import AuthService
from services.tasks_service import TasksService
from services.history_service import HistoryService


class TasksController:
    def __init__(self, auth: AuthService, tasks_service: TasksService, history_service: HistoryService, users_repo):
        self.auth = auth
        self.tasks_service = tasks_service
        self.history_service = history_service
        self.users_repo = users_repo

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.users_repo.upsert_user(user.id, user.username)

        if context.args:
            key = context.args[0].strip()
            role = await self.tasks_service.activate_by_key(user.id, key)
            if role:
                await update.message.reply_text(f"✅ Аккаунт активирован. Роль: {role}")
            else:
                await update.message.reply_text("❌ Ключ недействителен или истёк.")

        is_active, _, row = await self.auth.get_flags(user.id)
        role = row[2] if row else "user"

        if is_active:
            await update.message.reply_html(
                f"Привет, <b>{user.first_name}</b>!\n"
                f"Статус: ✅ активен\n"
                f"Роль: <b>{role}</b>\n\n"
                f"Команды:\n"
                f"<code>/add</code> — добавить задачу себе\n"
                f"<code>/tasks</code> — задачи на сегодня\n"
                f"<code>/tasks all</code> — все задачи\n"
                f"<code>/done &lt;номер&gt;</code> — выполнить\n"
                f"<code>/balance</code> — баланс\n"
                f"<code>/shop</code> — магазин\n"
                f"<code>/help</code> — справка"
            )
        else:
            await update.message.reply_html(
                f"Привет, <b>{user.first_name}</b>!\n\n"
                f"🔐 Для доступа нужен ключ.\n"
                f"Активируйтесь командой:\n"
                f"<code>/register &lt;ключ&gt;</code>\n"
                f"или:\n"
                f"<code>/start &lt;ключ&gt;</code>"
            )

    async def register(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.users_repo.upsert_user(user.id, user.username)

        if not context.args:
            await update.message.reply_text("Введите ключ: /register <ключ>")
            return

        role = await self.tasks_service.activate_by_key(user.id, context.args[0].strip())
        if not role:
            await update.message.reply_text("❌ Ключ недействителен или истёк.")
            return

        await update.message.reply_text(f"✅ Аккаунт активирован. Роль: {role}")

    async def whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.users_repo.upsert_user(user.id, user.username)

        is_active, _, row = await self.auth.get_flags(user.id)
        if not row:
            await update.message.reply_text("Не удалось получить профиль.")
            return

        _, username, role, active, balance = row
        await update.message.reply_text(
            "👤 Профиль\n"
            f"ID: {user.id}\n"
            f"Username: @{username}\n"
            f"Роль: {role}\n"
            f"Активен: {'да' if int(active)==1 else 'нет'}\n"
            f"Баланс: {balance}"
        )

    async def add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        text = update.message.text or ""
        try:
            cmd = AddCommandParser.parse(text)
        except Exception:
            await update.message.reply_text(
                "Форматы:\n"
                "/add <задача> <ЧЧ:ММ> <монетки> [daily|weekly|every:Nd]\n"
                "/add <задача> <YYYY-MM-DD> <ЧЧ:ММ> <монетки> [once|daily|weekly|every:Nd]"
            )
            return

        if cmd.repeat_unit == "once" and cmd.start_dt < datetime.now():
            await update.message.reply_text("⚠️ Дата/время уже в прошлом. Для once укажите будущую дату.")
            return

        task_id, next_due = await self.tasks_service.add_self_task(user.id, cmd)
        await update.message.reply_text(
            f"✅ Задача добавлена (#{task_id})!\n"
            f"📝 {cmd.task_text}\n"
            f"⏰ Следующее напоминание: {next_due}\n"
            f"🔁 Повтор: {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
            f"💰 +{cmd.coins} монет при выполнении"
        )

    async def tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        show_all = bool(context.args) and context.args[0].lower() == "all"
        rows = await self.tasks_service.list_tasks(user.id, show_all=show_all)

        if not rows:
            await update.message.reply_text("🎉 Нет задач!" if show_all else "🎉 Нет задач на сегодня!")
            return

        lines = ["📋 Ваши задачи:\n"]
        for task_id, task_text, next_due, coins, repeat_unit, repeat_every in rows:
            lines.append(
                f"{task_id}. {task_text}\n"
                f"   ⏰ {next_due}  🔁 {format_repeat(repeat_unit, repeat_every)}  💰 +{coins}\n"
            )
        await update.message.reply_text("\n".join(lines))

    async def done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        if not context.args:
            await update.message.reply_text("Формат: /done <task_id>")
            return

        try:
            task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("task_id должен быть числом.")
            return

        coins, balance = await self.tasks_service.complete(user.id, task_id)
        if coins is None:
            await update.message.reply_text("Задача не найдена или уже выполнена.")
            return

        await update.message.reply_text(
            f"🎉 Задача выполнена!\n"
            f"💰 Получено: +{coins} монет\n"
            f"💎 Общий баланс: {balance} монет"
        )

    async def balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, row = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return
        await update.message.reply_text(f"💰 Ваш баланс: {row[4]} монет")

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        limit = 20
        if context.args:
            try:
                limit = max(1, min(int(context.args[0]), 100))
            except ValueError:
                await update.message.reply_text("Формат: /history [N]")
                return

        rows = await self.history_service.get_user_history(user.id, limit)
        if not rows:
            await update.message.reply_text("История пуста.")
            return

        lines = ["📜 История выполненных задач:\n"]
        for _, task_id, task_text, coins, completed_at, assigned_by in rows:
            who = f" (назначил {assigned_by})" if assigned_by else ""
            lines.append(f"{completed_at} — #{task_id} {task_text} (+{coins}){who}")
        await update.message.reply_text("\n".join(lines))
