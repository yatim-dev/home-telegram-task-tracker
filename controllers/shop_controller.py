import logging
from telegram import Update
from telegram.ext import ContextTypes

from services.auth_service import AuthService
from services.shop_service import ShopService

logger = logging.getLogger(__name__)


class ShopController:
    def __init__(self, auth: AuthService, shop_service: ShopService):
        self.auth = auth
        self.shop_service = shop_service

    async def shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        rewards = await self.shop_service.list_shop()
        if not rewards:
            await update.message.reply_text("🛒 Магазин пуст.")
            return

        lines = ["🛒 <b>Магазин наград</b>\n", "Купить: <code>/buy &lt;id&gt;</code>\n"]
        for rid, title, desc, price in rewards:
            desc_part = f" — {desc}" if desc else ""
            lines.append(f"<b>{rid}.</b> {title} — <b>{price}</b> 💰{desc_part}")

        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)

    async def buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        if not context.args:
            await update.message.reply_text("Формат: /buy <id>\nПример: /buy 2")
            return

        try:
            reward_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("id должен быть числом. Пример: /buy 2")
            return

        ok, purchase_id, err, new_balance = await self.shop_service.buy(user.id, reward_id)
        if not ok:
            if err == "not_found":
                await update.message.reply_text("❌ Награда не найдена.")
            elif err == "inactive":
                await update.message.reply_text("❌ Награда сейчас недоступна.")
            elif err == "not_enough":
                await update.message.reply_text("❌ Недостаточно монет для покупки.")
            else:
                await update.message.reply_text("❌ Не удалось выполнить покупку.")
            return

        await update.message.reply_text(
            "✅ Покупка успешна!\n"
            f"🎫 Купон: #{purchase_id}\n"
            f"💎 Баланс: {new_balance} монет\n\n"
            "Купоны: /inventory\n"
            "Использовать: /use <purchase_id>"
        )

    async def inventory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        rows = await self.shop_service.inventory(user.id)
        if not rows:
            await update.message.reply_text("🎒 Купонов нет. Магазин: /shop")
            return

        lines = ["🎒 <b>Ваши купоны</b>\n", "Использовать: <code>/use &lt;purchase_id&gt;</code>\n"]
        for purchase_id, title, desc, price, created_at in rows:
            desc_part = f" — {desc}" if desc else ""
            lines.append(f"<b>#{purchase_id}</b> {title} ({price} 💰) — {created_at}{desc_part}")

        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)

    async def use(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_active, _, _ = await self.auth.get_flags(user.id)
        if not is_active:
            await update.message.reply_text("🔐 Активируйтесь: /register <ключ>")
            return

        if not context.args:
            await update.message.reply_text("Формат: /use <purchase_id>\nПример: /use 15")
            return

        try:
            purchase_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("purchase_id должен быть числом.")
            return

        ok, title, price, admin_ids = await self.shop_service.use(user.id, purchase_id)
        if not ok:
            await update.message.reply_text("❌ Купон не найден, уже использован или не принадлежит вам.")
            return

        await update.message.reply_text("✅ Купон отмечен как использованный.")

        msg = (
            "🎫 Купон использован\n"
            f"Пользователь: @{user.username or '-'} (id={user.id})\n"
            f"Купон: #{purchase_id}\n"
            f"Награда: {title}\n"
            f"Стоимость: {price} 💰"
        )

        for admin_id in admin_ids:
            if admin_id == user.id:
                continue
            try:
                await context.bot.send_message(chat_id=admin_id, text=msg)
            except Exception as e:
                logger.warning("Failed to notify admin_id=%s about purchase_id=%s: %s", admin_id, purchase_id, e)
