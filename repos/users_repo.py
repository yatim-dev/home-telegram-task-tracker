from typing import Optional, List


class UsersRepo:
    def __init__(self, adb):
        self.db = adb  # AsyncDB

    async def upsert_user(self, user_id: int, username: Optional[str]) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await self.db.execute(
            "UPDATE users SET username = ? WHERE user_id = ?",
            (username, user_id),
        )

    async def get_user(self, user_id: int):
        return await self.db.fetchone(
            "SELECT user_id, username, role, is_active, balance FROM users WHERE user_id = ?",
            (user_id,),
        )

    async def activate_user(self, user_id: int, role: str) -> None:
        # registered_at ставим в sqlite через datetime('now') чтобы не зависеть от питона
        await self.db.execute(
            "UPDATE users SET is_active = 1, role = ?, registered_at = datetime('now') WHERE user_id = ?",
            (role, user_id),
        )

    async def list_users(self):
        return await self.db.fetchall(
            "SELECT user_id, username, role, is_active, balance FROM users ORDER BY user_id"
        )

    async def find_user_id_by_username(self, username: str) -> Optional[int]:
        u = (username or "").strip()
        if u.startswith("@"):
            u = u[1:]

        row = await self.db.fetchone(
            "SELECT user_id FROM users WHERE username IS NOT NULL AND lower(username) = lower(?) LIMIT 1",
            (u,),
        )
        return row[0] if row else None

    async def list_admin_ids(self) -> List[int]:
        rows = await self.db.fetchall(
            "SELECT user_id FROM users WHERE role = 'admin' AND is_active = 1 ORDER BY user_id"
        )
        return [r[0] for r in rows]

    async def get_balance(self, user_id: int) -> int:
        row = await self.db.fetchone("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        return int(row[0]) if row else 0

    # ---- registration keys ----

    async def create_registration_key(self, role: str, expires_at: str) -> str:
        import secrets
        # expires_at валидируйте в контроллере/сервисе как сейчас
        for _ in range(10):
            key = secrets.token_urlsafe(10)
            try:
                await self.db.execute(
                    "INSERT INTO registration_keys (reg_key, role, expires_at) VALUES (?, ?, ?)",
                    (key, role, expires_at),
                )
                return key
            except Exception:
                # если поймали rare collision — пробуем ещё раз
                continue
        raise RuntimeError("Не удалось сгенерировать уникальный ключ")

    async def consume_registration_key(self, key: str):
        row = await self.db.fetchone(
            "SELECT role, expires_at FROM registration_keys WHERE reg_key = ?",
            (key,),
        )
        if not row:
            return None

        role, expires_at = row

        # удаляем если истёк
        # sqlite сравнение строк YYYY-MM-DD HH:MM работает лексикографически
        now = await self.db.fetchone("SELECT strftime('%Y-%m-%d %H:%M', 'now')")
        now_str = now[0]

        if now_str > expires_at:
            await self.db.execute("DELETE FROM registration_keys WHERE reg_key = ?", (key,))
            return None

        await self.db.execute("DELETE FROM registration_keys WHERE reg_key = ?", (key,))
        return role
