from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


HELP_MENU = "help:menu"
HELP_COMMANDS = "help:commands"
HELP_EXAMPLES = "help:examples"
HELP_REMINDERS = "help:reminders"
HELP_FAQ = "help:faq"
HELP_ABOUT = "help:about"


class HelpController:
    def _keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📌 Команды", callback_data=HELP_COMMANDS),
                    InlineKeyboardButton("🧪 Примеры", callback_data=HELP_EXAMPLES),
                ],
                [
                    InlineKeyboardButton("⏰ Напоминания", callback_data=HELP_REMINDERS),
                    InlineKeyboardButton("❓ FAQ", callback_data=HELP_FAQ),
                ],
                [
                    InlineKeyboardButton("ℹ️ О боте", callback_data=HELP_ABOUT),
                ],
            ]
        )

    def _text(self, section: str = HELP_MENU) -> str:
        if section == HELP_COMMANDS:
            return (
                "<b>📌 Команды</b>\n\n"
                "<b>/start</b> — регистрация\n\n"
                "<b>/add</b> — добавить задачу\n"
                "Форматы:\n"
                "1) <code>/add &lt;текст&gt; &lt;ЧЧ:ММ&gt; &lt;монетки&gt; [daily|weekly|every:Nd]</code>\n"
                "2) <code>/add &lt;текст&gt; &lt;YYYY-MM-DD&gt; &lt;ЧЧ:ММ&gt; &lt;монетки&gt; [once|daily|weekly|every:Nd]</code>\n\n"
                "<b>/tasks</b> — список активных задач\n"
                "<b>/done</b> — выполнить: <code>/done &lt;номер&gt;</code>\n"
                "<b>/balance</b> — баланс\n"
                "<b>/help</b> — справка"
            )

        if section == HELP_EXAMPLES:
            return (
                "<b>🧪 Примеры</b>\n\n"
                "<code>/add Помыть посуду 18:30 10</code>\n"
                "<code>/add Сдать проект 2026-01-10 12:00 50 once</code>\n"
                "<code>/add Полить цветы 2026-01-03 09:00 2 daily</code>\n"
                "<code>/add Протереть пыль 2026-01-03 18:00 5 every:3d</code>\n\n"
                "<code>/tasks</code>\n"
                "<code>/done 3</code>\n"
                "<code>/balance</code>"
            )

        if section == HELP_REMINDERS:
            return (
                "<b>⏰ Напоминания</b>\n\n"
                "Бот проверяет задачи раз в минуту.\n"
                "Разовые задачи напоминаются один раз.\n"
                "Повторяющиеся — после <code>/done</code> переносятся на следующий срок.\n\n"
                "Если время “съехало” — проверьте часовой пояс сервера."
            )

        if section == HELP_FAQ:
            return (
                "<b>❓ FAQ</b>\n\n"
                "<b>Почему /add ругается?</b>\n"
                "Проверьте формат времени <code>ЧЧ:ММ</code>, дату <code>YYYY-MM-DD</code> и монеты (число).\n\n"
                "<b>Почему задача не пропала после /done?</b>\n"
                "Потому что она повторяющаяся — бот перенёс её на следующий раз."
            )

        if section == HELP_ABOUT:
            return (
                "<b>ℹ️ О боте</b>\n\n"
                "Трекер домашних дел: задачи, напоминания, монеты.\n"
                "Начать: <code>/add ...</code> → <code>/tasks</code> → <code>/done N</code>"
            )

        return (
            "<b>📚 Справка</b>\n\n"
            "Выберите раздел кнопками ниже.\n"
            "Быстрый старт:\n"
            "<code>/add Помыть посуду 18:30 10</code>"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        section_map = {
            "menu": HELP_MENU,
            "commands": HELP_COMMANDS,
            "examples": HELP_EXAMPLES,
            "reminders": HELP_REMINDERS,
            "faq": HELP_FAQ,
            "about": HELP_ABOUT,
        }
        key = (context.args[0].lower() if context.args else "menu")
        section = section_map.get(key, HELP_MENU)

        await update.message.reply_html(
            self._text(section),
            reply_markup=self._keyboard(),
            disable_web_page_preview=True,
        )

    async def help_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        section = query.data or HELP_MENU
        await query.edit_message_text(
            text=self._text(section),
            reply_markup=self._keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
