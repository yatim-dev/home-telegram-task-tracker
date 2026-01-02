from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from bot.parsing import AddCommandParser, format_repeat


class TaskController:
    def __init__(self, db):
        self.db = db

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.db.add_user(user.id, user.username)

        await update.message.reply_html(
            f"Привет, <b>{user.first_name}</b>!\n"
            f"Добро пожаловать в систему домашних дел.\n\n"
            f"🎯 Добавляй задачи, получай уведомления\n"
            f"💰 Зарабатывай монетки за выполнение\n"
            f"📊 Следи за прогрессом\n\n"
            f"Напиши /help для списка команд."
        )

    async def add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                "/add Протереть пыль 2026-01-03 18:00 5 every:3d"
            )
            return

        if cmd.repeat_unit == "once" and cmd.start_dt < datetime.now():
            await update.message.reply_text(
                "⚠️ Дата/время уже в прошлом. Для разовой задачи укажите будущую дату."
            )
            return

        next_due = cmd.start_dt.strftime("%Y-%m-%d %H:%M")
        task_id = await self.db.add_task(
            user_id=user.id,
            task=cmd.task_text,
            next_due=next_due,
            coins=cmd.coins,
            repeat_unit=cmd.repeat_unit,
            repeat_every=cmd.repeat_every,
        )

        await update.message.reply_text(
            f"✅ Задача добавлена (#{task_id})!\n"
            f"📝 {cmd.task_text}\n"
            f"⏰ Следующее напоминание: {next_due}\n"
            f"🔁 Повтор: {format_repeat(cmd.repeat_unit, cmd.repeat_every)}\n"
            f"💰 +{cmd.coins} монет при выполнении"
        )

    async def show_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        tasks = await self.db.get_tasks(user.id)

        if not tasks:
            await update.message.reply_text("🎉 У вас нет активных задач! Добавьте первую с помощью /add")
            return

        lines = ["📋 Ваши задачи:\n"]
        for task_id, task_text, next_due, coins, repeat_unit, repeat_every in tasks:
            lines.append(
                f"{task_id}. {task_text}\n"
                f"   ⏰ {next_due}  🔁 {format_repeat(repeat_unit, repeat_every)}  💰 +{coins}\n"
            )

        await update.message.reply_text("\n".join(lines))

    async def complete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        user = update.effective_user
        balance = await self.db.get_balance(user.id)

        await update.message.reply_text(
            f"💰 Ваш баланс: {balance} монет\n\n"
            f"💡 Совет: выполняйте задачи регулярно, чтобы увеличивать баланс!"
        )
