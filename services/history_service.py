from repos.history_repo import HistoryRepo


class HistoryService:
    def __init__(self, history: HistoryRepo):
        self.history = history

    async def get_user_history(self, user_id: int, limit: int):
        return await self.history.get_history(user_id, limit)
