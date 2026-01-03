from __future__ import annotations

from typing import Optional


class ShopRepo:
    def __init__(self, adb):
        self.db = adb  # AsyncDB (с fetchone/fetchall/execute/transaction)

    # -------------------------
    # rewards (user/admin)
    # -------------------------

    async def list_rewards(self, active_only: bool = True):
        if active_only:
            return await self.db.fetchall(
                """
                SELECT id, title, description, price
                FROM rewards
                WHERE is_active = 1
                ORDER BY price, id
                """
            )
        return await self.db.fetchall(
            """
            SELECT id, title, description, price, is_active
            FROM rewards
            ORDER BY is_active DESC, price, id
            """
        )

    async def list_rewards_admin(self):
        return await self.db.fetchall(
            """
            SELECT id, title, description, price, is_active
            FROM rewards
            ORDER BY is_active DESC, price, id
            """
        )

    async def add_reward(self, title: str, description: str, price: int) -> int:
        def _fn(cur):
            cur.execute(
                """
                INSERT INTO rewards (title, description, price, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (title, description, int(price)),
            )
            return cur.lastrowid

        return await self.db.transaction(_fn, immediate=False)

    async def set_reward_description(self, reward_id: int, description: str) -> int:
        return await self.db.execute(
            "UPDATE rewards SET description = ? WHERE id = ?",
            (description, reward_id),
        )

    async def set_reward_active(self, reward_id: int, is_active: int) -> int:
        return await self.db.execute(
            "UPDATE rewards SET is_active = ? WHERE id = ?",
            (int(is_active), reward_id),
        )

    # -------------------------
    # purchases (user)
    # -------------------------

    async def buy_reward(self, user_id: int, reward_id: int):
        """
        Атомарно:
          - проверяем баланс
          - проверяем reward (active)
          - списываем
          - создаём purchase
        Возвращает: (ok, purchase_id, error_code, new_balance)
          error_code: 'not_found' | 'inactive' | 'not_enough'
        """
        def _fn(cur):
            cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            balance = int(row[0]) if row else 0

            cur.execute("SELECT id, price, is_active FROM rewards WHERE id = ?", (reward_id,))
            r = cur.fetchone()
            if not r:
                return (False, None, "not_found", balance)

            _id, price, is_active = r
            price = int(price)

            if int(is_active) != 1:
                return (False, None, "inactive", balance)

            if balance < price:
                return (False, None, "not_enough", balance)

            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))

            cur.execute(
                """
                INSERT INTO purchases (user_id, reward_id, price, status, created_at)
                VALUES (?, ?, ?, 'new', datetime('now'))
                """,
                (user_id, reward_id, price),
            )
            purchase_id = cur.lastrowid

            cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            new_balance = int(cur.fetchone()[0])

            return (True, purchase_id, None, new_balance)

        return await self.db.transaction(_fn, immediate=True)

    async def get_inventory(self, user_id: int):
        return await self.db.fetchall(
            """
            SELECT p.id, r.title, r.description, p.price, p.created_at
            FROM purchases p
            JOIN rewards r ON r.id = p.reward_id
            WHERE p.user_id = ? AND p.status = 'new'
            ORDER BY p.created_at DESC, p.id DESC
            """,
            (user_id,),
        )

    async def use_purchase_with_info(self, user_id: int, purchase_id: int):
        """
        Атомарно помечает купон used.
        Возвращает: (ok, title, price)
        """
        def _fn(cur):
            cur.execute(
                """
                SELECT p.id, p.price, r.title
                FROM purchases p
                JOIN rewards r ON r.id = p.reward_id
                WHERE p.id = ? AND p.user_id = ? AND p.status = 'new'
                """,
                (purchase_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return (False, None, None)

            _pid, price, title = row
            price = int(price)

            cur.execute(
                """
                UPDATE purchases
                SET status = 'used', used_at = datetime('now')
                WHERE id = ? AND user_id = ? AND status = 'new'
                """,
                (purchase_id, user_id),
            )

            if cur.rowcount <= 0:
                return (False, None, None)

            return (True, title, price)

        return await self.db.transaction(_fn, immediate=True)
