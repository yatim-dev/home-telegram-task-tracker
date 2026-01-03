class HistoryRepo:
    def __init__(self, adb):
        self.db = adb  # AsyncDB (с fetchall)

    async def get_history(self, user_id: int, limit: int = 20):
        return await self.db.fetchall(
            """
            SELECT id, task_id, task_text, coins, completed_at, assigned_by
            FROM task_completions
            WHERE user_id = ?
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (user_id, int(limit)),
        )
