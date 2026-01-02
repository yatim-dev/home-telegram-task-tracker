from telegram import Update
from telegram.ext import ContextTypes


class AuthService:
    def __init__(self, db):
        self.db = db  # AsyncDB

    async def require_active(self, update: Update) -> bool:
        user = update.effective_user
        row = await self.db.get_user(user.id)  # (user_id, username, role, is_active, balance)
        if not row or int(row[3]) != 1:
            await update.message.reply_text(
                "🔐 Доступ закрыт.\n"
                "Активируйтесь командой: /register <ключ>\n"
                "Либо: /start <ключ>"
            )
            return False
        return True

    async def require_admin(self, update: Update) -> bool:
        user = update.effective_user
        row = await self.db.get_user(user.id)
        if not row or int(row[3]) != 1:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return False
        role = row[2]
        if role != "admin":
            await update.message.reply_text("⛔ Эта команда доступна только администратору.")
            return False
        return True
