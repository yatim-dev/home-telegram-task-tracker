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
    def __init__(self, db):
        self.db = db  # AsyncDB

    async def _get_user_flags(self, update: Update):
        user = update.effective_user
        row = await self.db.get_user(user.id)
        # row: (user_id, username, role, is_active, balance)
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
        # Если не активирован — показываем только активацию
        if not is_active:
            return (
                "<b>🔐 Доступ закрыт</b>\n\n"
                "Чтобы пользоваться ботом, нужен одноразовый ключ.\n\n"
                "<b>Как активироваться:</b>\n"
                "• <code>/register &lt;ключ&gt;</code>\n"
                "• или <code>/start &lt;ключ&gt;</code>\n\n"
                "<b>После активации будут доступны:</b>\n"
                "• <code>/add</code> — добавить задачу себе\n"
                "• <code>/tasks</code> — список задач\n"
                "• <code>/done N</code> — выполнить\n"
                "• <code>/balance</code> — баланс\n"
                "• <code>/history</code> — история выполнений\n"
                "• <code>/shop</code> — магазин наград\n"
            )

        # -------------------------
        # Активирован: разделы help
        # -------------------------

        if section == HELP_COMMANDS:
            common_user_commands = (
                "<b>/add</b> — добавить задачу себе\n"
                "Форматы:\n"
                "• <code>/add &lt;текст&gt; &lt;ЧЧ:ММ&gt; &lt;монетки&gt; [daily|weekly|every:Nd]</code>\n"
                "• <code>/add &lt;текст&gt; &lt;YYYY-MM-DD&gt; &lt;ЧЧ:ММ&gt; &lt;монетки&gt; "
                "[once|daily|weekly|every:Nd]</code>\n\n"
                "<b>/tasks</b> — задачи на сегодня\n"
                "<b>/tasks all</b> — все ваши задачи\n"
                "<b>/done</b> — выполнить: <code>/done &lt;task_id&gt;</code>\n"
                "<b>/balance</b> — баланс\n"
                "<b>/history</b> — история выполнений: <code>/history [N]</code>\n"
                "<b>/whoami</b> — профиль\n\n"
                "<b>Магазин:</b>\n"
                "<b>/shop</b> — список наград\n"
                "<b>/buy</b> — купить награду: <code>/buy &lt;reward_id&gt;</code>\n"
                "<b>/inventory</b> — ваши купоны\n"
                "<b>/use</b> — использовать купон: <code>/use &lt;purchase_id&gt;</code>\n\n"
                "<b>/help</b> — справка"
            )

            if is_admin:
                return (
                    "<b>📌 Команды (админ)</b>\n\n"
                    "<b>Пользовательские:</b>\n"
                    f"{common_user_commands}\n\n"
                    "<b>Админские (задачи):</b>\n"
                    "<b>/addto</b> — назначить задачу пользователю:\n"
                    "• <code>/addto @username &lt;... как в /add ...&gt;</code>\n\n"
                    "<b>/edit</b> — редактировать задачу:\n"
                    "• <code>/edit &lt;task_id&gt; &lt;... как в /add ...&gt;</code>\n\n"
                    "<b>/delete</b> — удалить задачу:\n"
                    "• <code>/delete &lt;task_id&gt;</code>\n"
                    "Где взять task_id: в <code>/tasks</code> это первая цифра строки\n\n"
                    "<b>Админские (пользователи):</b>\n"
                    "<b>/genkey</b> — создать одноразовый ключ:\n"
                    "• <code>/genkey user 2026-01-10_12:00</code>\n"
                    "• <code>/genkey admin 2026-01-10_12:00</code>\n"
                    "<b>/users</b> — список пользователей\n\n"
                    "<b>Админские (магазин):</b>\n"
                    "<b>/rewards</b> — список всех наград (вкл/выкл)\n"
                    "<b>/addreward</b> — добавить награду: <code>/addreward &lt;price&gt; &lt;title&gt;</code>\n"
                    "<b>/rewarddesc</b> — описание: <code>/rewarddesc &lt;id&gt; &lt;description&gt;</code>\n"
                    "<b>/rewardon</b> — включить: <code>/rewardon &lt;id&gt;</code>\n"
                    "<b>/rewardoff</b> — выключить: <code>/rewardoff &lt;id&gt;</code>"
                )

            return (
                "<b>📌 Команды</b>\n\n"
                f"{common_user_commands}\n\n"
                "Примечание: назначать задачи другим пользователям может только администратор (команда /addto)."
            )

        if section == HELP_EXAMPLES:
            if is_admin:
                return (
                    "<b>🧪 Примеры (админ)</b>\n\n"
                    "<b>Задачи себе:</b>\n"
                    "<code>/add Помыть посуду 18:30 10</code>\n"
                    "<code>/add Сдать проект 2026-01-10 12:00 50 once</code>\n\n"
                    "<b>Назначить пользователю:</b>\n"
                    "<code>/addto @vasya Помыть посуду 18:30 10</code>\n\n"
                    "<b>Редактировать задачу:</b>\n"
                    "<code>/edit 12 Протереть пыль 2026-01-05 18:00 7 every:3d</code>\n\n"
                    "<b>Удалить задачу:</b>\n"
                    "<code>/delete 12</code>\n\n"
                    "<b>История:</b>\n"
                    "<code>/history 30</code>\n\n"
                    "<b>Магазин (пользователь):</b>\n"
                    "<code>/shop</code>\n"
                    "<code>/buy 2</code>\n"
                    "<code>/inventory</code>\n"
                    "<code>/use 15</code>\n\n"
                    "<b>Магазин (админ-управление):</b>\n"
                    "<code>/rewards</code>\n"
                    "<code>/addreward 10 30 минут игр</code>\n"
                    "<code>/rewarddesc 1 Дополнительные 30 минут</code>\n"
                    "<code>/rewardoff 1</code>\n"
                    "<code>/rewardon 1</code>\n\n"
                    "<b>Ключи:</b>\n"
                    "<code>/genkey user 2026-01-10_12:00</code>\n"
                    "<code>/genkey admin 2026-01-10_12:00</code>"
                )

            return (
                "<b>🧪 Примеры</b>\n\n"
                "<b>Добавить задачу:</b>\n"
                "<code>/add Полить цветы 09:00 2</code>\n"
                "<code>/add Сдать проект 2026-01-10 12:00 50 once</code>\n\n"
                "<b>Посмотреть задачи:</b>\n"
                "<code>/tasks</code>\n"
                "<code>/tasks all</code>\n\n"
                "<b>Выполнить:</b>\n"
                "<code>/done 3</code>\n\n"
                "<b>История:</b>\n"
                "<code>/history 20</code>\n\n"
                "<b>Магазин:</b>\n"
                "<code>/shop</code>\n"
                "<code>/buy 1</code>\n"
                "<code>/inventory</code>\n"
                "<code>/use 15</code>"
            )

        if section == HELP_REMINDERS:
            return (
                "<b>⏰ Напоминания</b>\n\n"
                "Бот проверяет задачи примерно раз в минуту.\n"
                "Разовые задачи (once) напоминаются один раз.\n"
                "Повторяющиеся — после <code>/done</code> переносятся на следующий срок.\n\n"
                "Если напоминания приходят “не в то время” — проверьте часовой пояс сервера."
            )

        if section == HELP_FAQ:
            return (
                "<b>❓ FAQ</b>\n\n"
                "<b>Почему задача не исчезает после /done?</b>\n"
                "Если задача повторяющаяся (daily/weekly/every:Nd), она переносится на следующий срок.\n"
                "Чтобы задача исчезла после выполнения — создавайте её как <code>once</code>.\n\n"
                "<b>Почему /tasks пусто?</b>\n"
                "Значит у вас нет задач на сегодня (или вы всё выполнили). Попробуйте <code>/tasks all</code>.\n\n"
                "<b>Как посмотреть историю выполнений?</b>\n"
                "<code>/history</code> или <code>/history 50</code>\n\n"
                "<b>Как тратить монетки?</b>\n"
                "<code>/shop</code> → <code>/buy id</code> → <code>/inventory</code> → <code>/use purchase_id</code>\n\n"
                "<b>Как админ добавляет товары в магазин?</b>\n"
                "<code>/addreward</code>, <code>/rewarddesc</code>, <code>/rewardon</code>, <code>/rewardoff</code>, "
                "список — <code>/rewards</code>\n"
            )

        if section == HELP_ABOUT:
            return (
                "<b>ℹ️ О боте</b>\n\n"
                "Трекер домашних дел с наградами:\n"
                "• пользователи могут добавлять задачи себе\n"
                "• админ может назначать задачи другим и управлять ими\n"
                "• за выполнение начисляются монетки\n"
                "• монетки можно тратить в магазине (купоны)\n"
                "• сохраняется история выполнений\n"
            )

        if section == HELP_ADMIN:
            if not is_admin:
                return "⛔ Раздел доступен только администратору."
            return (
                "<b>🛠 Админ</b>\n\n"
                "<b>Ключи:</b>\n"
                "• <code>/genkey user YYYY-MM-DD_HH:MM</code>\n"
                "• <code>/genkey admin YYYY-MM-DD_HH:MM</code>\n\n"
                "<b>Задачи:</b>\n"
                "• <code>/addto @username ...</code>\n"
                "• <code>/edit &lt;task_id&gt; ...</code>\n"
                "• <code>/delete &lt;task_id&gt;</code>\n\n"
                "<b>Пользователи:</b>\n"
                "• <code>/users</code>\n\n"
                "<b>Магазин:</b>\n"
                "• <code>/rewards</code>\n"
                "• <code>/addreward &lt;price&gt; &lt;title&gt;</code>\n"
                "• <code>/rewarddesc &lt;id&gt; &lt;description&gt;</code>\n"
                "• <code>/rewardon &lt;id&gt;</code>\n"
                "• <code>/rewardoff &lt;id&gt;</code>\n"
            )

        # HELP_MENU (по умолчанию)
        if is_admin:
            return (
                "<b>📚 Справка</b>\n\n"
                "Вы администратор.\n\n"
                "Быстрые команды:\n"
                "<code>/users</code>\n"
                "<code>/genkey user 2026-01-10_12:00</code>\n"
                "<code>/addto @username Помыть посуду 18:30 10</code>\n"
                "<code>/rewards</code>\n"
                "<code>/addreward 10 30 минут игр</code>\n"
                "<code>/shop</code>\n"
            )

        return (
            "<b>📚 Справка</b>\n\n"
            "Быстрые команды:\n"
            "<code>/add Помыть посуду 18:30 10</code>\n"
            "<code>/tasks</code>\n"
            "<code>/tasks all</code>\n"
            "<code>/done 1</code>\n"
            "<code>/balance</code>\n"
            "<code>/history</code>\n"
            "<code>/shop</code>\n"
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
