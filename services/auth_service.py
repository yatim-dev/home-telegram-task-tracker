from repos.users_repo import UsersRepo


class AuthService:
    def __init__(self, users: UsersRepo):
        self.users = users

    async def get_flags(self, user_id: int) -> tuple[bool, bool, tuple | None]:
        row = await self.users.get_user(user_id)  # (user_id, username, role, is_active, balance)
        if not row:
            return False, False, None
        role = row[2] or "user"
        is_active = int(row[3]) == 1
        is_admin = role == "admin"
        return is_active, is_admin, row
