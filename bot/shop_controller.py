from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import AuthService
import logging

logger = logging.getLogger(__name__)

class ShopController:
    def __init__(self, db):
        self.db = db  # AsyncDB
        self.auth = AuthService(db)

    async def shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        rewards = await self.db.list_rewards(active_only=True)
        if not rewards:
            await update.message.reply_text("🛒 Магазин пуст.")
            return

        lines = ["🛒 <b>Магазин наград</b>\n", "Чтобы купить: <code>/buy &lt;id&gt;</code>\n"]
        for rid, title, desc, price in rewards:
            desc_part = f" — {desc}" if desc else ""
            lines.append(f"<b>{rid}.</b> {title} — <b>{price}</b> 💰{desc_part}")

        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)

    async def buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        if not context.args:
            await update.message.reply_text("Формат: /buy <id>\nПример: /buy 2")
            return

        try:
            reward_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("id должен быть числом. Пример: /buy 2")
            return

        user = update.effective_user
        ok, purchase_id, err, new_balance = await self.db.buy_reward(user.id, reward_id)

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
            "Посмотреть купоны: /inventory\n"
            "Использовать: /use <purchase_id>"
        )

    async def inventory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        user = update.effective_user
        rows = await self.db.get_inventory(user.id)
        if not rows:
            await update.message.reply_text("🎒 У вас нет купленных купонов.\nЗайдите в магазин: /shop")
            return

        lines = ["🎒 <b>Ваши купоны</b>\n", "Использовать: <code>/use &lt;purchase_id&gt;</code>\n"]
        for purchase_id, title, desc, price, created_at in rows:
            desc_part = f" — {desc}" if desc else ""
            lines.append(f"<b>#{purchase_id}</b> {title} ({price} 💰) — куплено {created_at}{desc_part}")

        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)

    async def use(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.auth.require_active(update):
            return

        if not context.args:
            await update.message.reply_text("Формат: /use <purchase_id>\nПример: /use 15")
            return

        try:
            purchase_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("purchase_id должен быть числом. Пример: /use 15")
            return

        user = update.effective_user

        ok, title, price = await self.db.use_purchase_with_info(user.id, purchase_id)
        if not ok:
            await update.message.reply_text("❌ Купон не найден, уже использован или не принадлежит вам.")
            return

        await update.message.reply_text("✅ Купон отмечен как использованный.")

        # Уведомляем всех админов
        try:
            admin_ids = await self.db.list_admin_ids()
            msg = (
                "🎫 Купон использован\n"
                f"Пользователь: @{user.username or '-'} (id={user.id})\n"
                f"Купон: #{purchase_id}\n"
                f"Награда: {title}\n"
                f"Стоимость: {price} 💰"
            )

            for admin_id in admin_ids:
                # можно не уведомлять самого себя, если админ использовал купон
                if admin_id == user.id:
                    continue
                try:
                    await context.bot.send_message(chat_id=admin_id, text=msg)
                except Exception as e:
                    logger.warning("Failed to notify admin_id=%s about purchase_id=%s: %s", admin_id, purchase_id, e)

        except Exception as e:
            logger.warning("Failed to list admins / notify about purchase_id=%s: %s", purchase_id, e)
