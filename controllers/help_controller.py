from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

HELP_MENU = "help:menu"
HELP_COMMANDS = "help:commands"
HELP_EXAMPLES = "help:examples"
HELP_REMINDERS = "help:reminders"
HELP_FAQ = "help:faq"
HELP_ABOUT = "help:about"
HELP_ADMIN = "help:admin"


class HelpController:
    def __init__(self, users_repo):
        self.users = users_repo  # UsersRepo

    async def _get_user_flags(self, update: Update):
        user = update.effective_user
        row = await self.users.get_user(user.id)  # (user_id, username, role, is_active, balance)
        if not row:
            return False, False
        role = row[2] or "user"
        is_active = int(row[3]) == 1
        is_admin = role == "admin"
        return is_active, is_admin

    def _keyboard(self, is_admin: bool) -> InlineKeyboardMarkup:
        rows = [
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
        if is_admin:
            rows.append([InlineKeyboardButton("🛠 Админ", callback_data=HELP_ADMIN)])
        return InlineKeyboardMarkup(rows)

    def _text(self, section: str, is_active: bool, is_admin: bool) -> str:
        if not is_active:
            return (
                "<b>🔐 Доступ закрыт</b>\n\n"
                "Чтобы пользоваться ботом, нужен одноразовый ключ.\n\n"
                "<b>Как активироваться:</b>\n"
                "• <code>/register &lt;ключ&gt;</code>\n"
                "• или <code>/start &lt;ключ&gt;</code>\n"
            )

        if section == HELP_COMMANDS:
            common = (
                "<b>/add</b> — добавить задачу себе\n"
                "Форматы:\n"
                "• <code>/add &lt;текст&gt; &lt;ЧЧ:ММ&gt; &lt;монетки&gt; [daily|weekly|every:Nd]</code>\n"
                "• <code>/add &lt;текст&gt; &lt;YYYY-MM-DD&gt; &lt;ЧЧ:ММ&gt; &lt;монетки&gt; "
                "[once|daily|weekly|every:Nd]</code>\n\n"
                "<b>/tasks</b> — задачи на сегодня\n"
                "<b>/tasks all</b> — все ваши задачи\n"
                "<b>/done</b> — выполнить: <code>/done &lt;task_id&gt;</code>\n"
                "<b>/balance</b> — баланс\n"
                "<b>/history</b> — история: <code>/history [N]</code>\n"
                "<b>/whoami</b> — профиль\n\n"
                "<b>Магазин:</b>\n"
                "<b>/shop</b> — список наград\n"
                "<b>/buy</b> — купить: <code>/buy &lt;reward_id&gt;</code>\n"
                "<b>/inventory</b> — купоны\n"
                "<b>/use</b> — использовать: <code>/use &lt;purchase_id&gt;</code>\n\n"
                "<b>/help</b> — справка"
            )

            if not is_admin:
                return "<b>📌 Команды</b>\n\n" + common

            return (
                "<b>📌 Команды (админ)</b>\n\n"
                "<b>Пользовательские:</b>\n"
                f"{common}\n\n"
                "<b>Админские (задачи):</b>\n"
                "<b>/addto</b> — назначить задачу пользователю:\n"
                "• <code>/addto @username &lt;... как в /add ...&gt;</code>\n"
                "<b>/edit</b> — редактировать: <code>/edit &lt;task_id&gt; ...</code>\n"
                "<b>/delete</b> — удалить: <code>/delete &lt;task_id&gt;</code>\n\n"
                "<b>Админские (пользователи):</b>\n"
                "<b>/genkey</b> — ключ: <code>/genkey user 2026-01-10_12:00</code>\n"
                "<b>/users</b> — список пользователей\n\n"
                "<b>Админские (магазин):</b>\n"
                "<b>/rewards</b> — список наград\n"
                "<b>/addreward</b> — добавить: <code>/addreward &lt;price&gt; &lt;title&gt;</code>\n"
                "<b>/rewarddesc</b> — описание: <code>/rewarddesc &lt;id&gt; &lt;text&gt;</code>\n"
                "<b>/rewardon</b> — включить: <code>/rewardon &lt;id&gt;</code>\n"
                "<b>/rewardoff</b> — выключить: <code>/rewardoff &lt;id&gt;</code>\n"
            )

        if section == HELP_EXAMPLES:
            if is_admin:
                return (
                    "<b>🧪 Примеры (админ)</b>\n\n"
                    "<code>/add Помыть посуду 18:30 10</code>\n"
                    "<code>/addto @vasya Помыть посуду 18:30 10</code>\n"
                    "<code>/edit 12 Помыть посуду 19:00 10</code>\n"
                    "<code>/delete 12</code>\n\n"
                    "<code>/shop</code>\n"
                    "<code>/buy 1</code>\n"
                    "<code>/inventory</code>\n"
                    "<code>/use 15</code>\n\n"
                    "<code>/rewards</code>\n"
                    "<code>/addreward 10 30 минут игр</code>\n"
                    "<code>/rewarddesc 1 Дополнительные 30 минут</code>\n"
                    "<code>/rewardoff 1</code>\n"
                )
            return (
                "<b>🧪 Примеры</b>\n\n"
                "<code>/add Полить цветы 09:00 2</code>\n"
                "<code>/tasks</code>\n"
                "<code>/done 3</code>\n"
                "<code>/shop</code>\n"
                "<code>/buy 1</code>\n"
                "<code>/inventory</code>\n"
                "<code>/use 15</code>\n"
            )

        if section == HELP_REMINDERS:
            return (
                "<b>⏰ Напоминания</b>\n\n"
                "Бот проверяет задачи примерно раз в минуту.\n"
                "Разовые (once) напоминаются один раз.\n"
                "Повторяющиеся — после <code>/done</code> переносятся на следующий срок.\n"
            )

        if section == HELP_FAQ:
            return (
                "<b>❓ FAQ</b>\n\n"
                "<b>Почему задача не исчезает после /done?</b>\n"
                "Повторяющиеся задачи переносятся на следующий срок.\n"
                "Чтобы исчезла — создавайте <code>once</code>.\n\n"
                "<b>Как тратить монетки?</b>\n"
                "<code>/shop</code> → <code>/buy</code> → <code>/inventory</code> → <code>/use</code>\n"
            )

        if section == HELP_ABOUT:
            return (
                "<b>ℹ️ О боте</b>\n\n"
                "Трекер задач с наградами:\n"
                "• задачи и напоминания\n"
                "• монетки и магазин\n"
                "• история выполнений\n"
            )

        if section == HELP_ADMIN:
            if not is_admin:
                return "⛔ Раздел доступен только администратору."
            return (
                "<b>🛠 Админ</b>\n\n"
                "<b>Пользователи:</b> <code>/genkey</code>, <code>/users</code>\n"
                "<b>Задачи:</b> <code>/addto</code>, <code>/edit</code>, <code>/delete</code>\n"
                "<b>Магазин:</b> <code>/rewards</code>, <code>/addreward</code>, <code>/rewarddesc</code>, "
                "<code>/rewardon</code>, <code>/rewardoff</code>\n"
            )

        # HELP_MENU
        return (
            "<b>📚 Справка</b>\n\n"
            "Выберите раздел кнопками ниже или напишите:\n"
            "• <code>/help commands</code>\n"
            "• <code>/help examples</code>\n"
            "• <code>/help reminders</code>\n"
            "• <code>/help faq</code>\n"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        section_map = {
            "menu": HELP_MENU,
            "commands": HELP_COMMANDS,
            "examples": HELP_EXAMPLES,
            "reminders": HELP_REMINDERS,
            "faq": HELP_FAQ,
            "about": HELP_ABOUT,
            "admin": HELP_ADMIN,
        }
        key = (context.args[0].lower() if context.args else "menu")
        section = section_map.get(key, HELP_MENU)

        is_active, is_admin = await self._get_user_flags(update)

        await update.message.reply_html(
            self._text(section, is_active=is_active, is_admin=is_admin),
            reply_markup=self._keyboard(is_admin=is_admin),
            disable_web_page_preview=True,
        )

    async def help_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        is_active, is_admin = await self._get_user_flags(update)
        section = query.data or HELP_MENU

        new_text = self._text(section, is_active=is_active, is_admin=is_admin)
        new_markup = self._keyboard(is_admin=is_admin)

        try:
            await query.edit_message_text(
                text=new_text,
                reply_markup=new_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                return
            raise
