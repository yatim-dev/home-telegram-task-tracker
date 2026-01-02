from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from bot.parsing import AddCommandParser, format_repeat
from bot.auth import AuthService


class TaskController:
    def __init__(self, db):
        self.db = db  # AsyncDB
        self.auth = AuthService(db)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.db.add_user(user.id, user.username)

        # Если пришли со стартом и ключом: /start <key>
        if context.args:
            key = context.args[0].strip()
            role = await self.db.consume_registration_key(key)
            if role:
                await self.db.activate_user(user.id, role)
                await update.message.reply_text(f"✅ Аккаунт активирован. Роль: {role}")
            else:
                await update.message.reply_text("❌ Ключ недействителен или истёк.")

        row = await self.db.get_user(user.id)
        is_active = int(row[3]) == 1 if row else False
        role = row[2] if row else "user"

        if is_active:
            await update.message.reply_html(
                f"Привет, <b>{user.first_name}</b>!\n"
                f"Статус: ✅ активен\n"
                f"Роль: <b>{role}</b>\n\n"
                f"Команды:\n"
                f"/tasks — список задач\n"
                f"/done <номер> — выполнить\n"
                f"/balance — баланс\n"
                f"/help — справка"
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
        await self.db.add_user(user.id, user.username)

        if not context.args:
            await update.message.reply_text("Введите ключ: /register <ключ>")
            return

        key = context.args[0].strip()
        role = await self.db.consume_registration_key(key)
        if not role:
            await update.message.reply_text("❌ Ключ недействителен или истёк.")
            return

        await self.db.activate_user(user.id, role)
        await update.message.reply_text(f"✅ Аккаунт активирован. Роль: {role}")

    async def whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.db.add_user(user.id, user.username)

        row = await self.db.get_user(user.id)
        if not row:
            await update.message.reply_text("Не удалось получить профиль.")
            return

        _, username, role, is_active, balance = row
        await update.message.reply_text(
            "👤 Профиль\n"
            f"ID: {user.id}\n"
            f"Username: @{username}\n"
            f"Роль: {role}\n"
            f"Активен: {'да' if int(is_active)==1 else 'нет'}\n"
            f"Баланс: {balance}"
        )

    async def add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Только админ
        if not await self.auth.require_admin(update):
            return

        user = update.effective_user
        text = update.message.text or ""

        try:
            cmd = AddCommandParser.parse(text)
        except Exception:
            await update.message.reply_text(
                "Форматы:\n"
                "/add <задача> <ЧЧ:ММ> <монетки> [daily|weekly|every:Nd]\n"
                "/add <задача> <YYYY-MM-DD> <ЧЧ:ММ> <монетки> [once|daily|weekly|every:Nd]\n\n"
                "Примеры:\n"
                "/add Помыть посуду 18:30 10\n"
                "/add Сдать проект 2026-01-10 12:00 50 once\n"
                "/add Полить цветы 2026-01-03 09:00 2 daily\n"
                "/add Протереть пыль 2026-01-03 18:00 5 every:3d\n\n"
                "Назначить пользователю:\n"
                "/addto @username <...>"
            )
            return

        if cmd.repeat_unit == "once" and cmd.start_dt < datetime.now():
            await update.message.reply_text("⚠️ Дата/время уже в прошлом. Для разовой задачи укажите будущую дату.")
            return

        next_due = cmd.start_dt.strftime("%Y-%m-%d %H:%M")

        task_id = await self.db.add_task(
            user_id=user.id,  # назначено админу (самому себе)
            task=cmd.task_text,
            next_due=next_due,
            coins=cmd.coins,
            repeat_unit=cmd.repeat_unit,
            repeat_every=cmd.repeat_every,
            assigned_by=user.id,  # кто назначил (для аудита)
        )

        await update.message.reply_text(
            f"✅ Задача добавлена (#{task_id})!\n"
            f"📝 {cmd.task_text}\n"
            f"⏰ Следующее напоминание: {next_due}\n"
            f"🔁 Повтор: {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
            f"💰 +{cmd.coins} монет при выполнении\n\n"
            f"Чтобы назначить задачу пользователю: /addto @username <...>"
        )

    async def show_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        user = update.effective_user
        show_all = bool(context.args) and context.args[0].lower() == "all"

        if show_all:
            tasks = await self.db.get_tasks(user.id)
        else:
            end_of_day = datetime.now().strftime("%Y-%m-%d 23:59")
            tasks = await self.db.get_tasks_until(user.id, end_of_day)

        if not tasks:
            await update.message.reply_text("🎉 У вас нет активных задач!")
            return

        lines = ["📋 Ваши задачи:\n"]
        for task_id, task_text, next_due, coins, repeat_unit, repeat_every in tasks:
            lines.append(
                f"{task_id}. {task_text}\n"
                f"   ⏰ {next_due}  🔁 {format_repeat(repeat_unit, repeat_every)}  💰 +{coins}\n"
            )
        await update.message.reply_text("\n".join(lines))

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        user = update.effective_user
        limit = 20
        if context.args:
            try:
                limit = int(context.args[0])
                limit = max(1, min(limit, 100))
            except ValueError:
                await update.message.reply_text("Формат: /history [число], например /history 20")
                return

        rows = await self.db.get_history(user.id, limit=limit)
        if not rows:
            await update.message.reply_text("История пуста.")
            return

        lines = ["📜 История выполненных задач:\n"]
        for _, task_id, task_text, coins, completed_at, assigned_by in rows:
            who = f" (назначил {assigned_by})" if assigned_by else ""
            lines.append(f"{completed_at} — #{task_id} {task_text} (+{coins}){who}")

        await update.message.reply_text("\n".join(lines))

    async def complete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        user = update.effective_user

        if not context.args:
            await update.message.reply_text("Укажите номер задачи: /done <номер>\nПример: /done 2")
            return

        try:
            task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Укажите номер задачи цифрой.\nПример: /done 2")
            return

        coins = await self.db.complete_task(user.id, task_id)
        if coins is None:
            await update.message.reply_text("Задача не найдена или уже выполнена.")
            return

        balance = await self.db.get_balance(user.id)
        await update.message.reply_text(
            f"🎉 Задача выполнена!\n"
            f"💰 Получено: +{coins} монет\n"
            f"💎 Общий баланс: {balance} монет"
        )

    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        user = update.effective_user
        balance = await self.db.get_balance(user.id)

        await update.message.reply_text(
            f"💰 Ваш баланс: {balance} монет\n\n"
            f"💡 Совет: выполняйте задачи регулярно, чтобы увеличивать баланс!"
        )
