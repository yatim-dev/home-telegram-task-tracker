import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial


class AsyncDB:
    """
    Запускает ВСЕ sqlite-операции в одном выделенном потоке.
    Это убирает блокировки event loop и ускоряет ответы бота.
    """
    def __init__(self, sync_db):
        self._db = sync_db
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sqlite-db")

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, partial(fn, *args, **kwargs))

    # -------- users / auth --------

    async def add_user(self, user_id, username):
        return await self._run(self._db.add_user, user_id, username)

    async def get_user(self, user_id):
        return await self._run(self._db.get_user, user_id)

    async def activate_user(self, user_id, role: str):
        return await self._run(self._db.activate_user, user_id, role)

    async def find_user_id_by_username(self, username: str):
        return await self._run(self._db.find_user_id_by_username, username)

    async def list_users(self):
        return await self._run(self._db.list_users)

    # -------- registration keys --------

    async def create_registration_key(self, role: str, expires_at: str) -> str:
        return await self._run(self._db.create_registration_key, role, expires_at)

    async def consume_registration_key(self, key: str):
        return await self._run(self._db.consume_registration_key, key)

    # -------- tasks --------

    async def add_task(self, **kwargs):
        return await self._run(self._db.add_task, **kwargs)

    async def get_tasks(self, user_id):
        return await self._run(self._db.get_tasks, user_id)

    async def complete_task(self, user_id, task_id):
        return await self._run(self._db.complete_task, user_id, task_id)

    async def get_task(self, task_id: int):
        return await self._run(self._db.get_task, task_id)

    async def get_tasks_until(self, user_id: int, until_due: str):
        return await self._run(self._db.get_tasks_until, user_id, until_due)

    async def update_task(self, task_id: int, task: str, next_due: str, coins: int, repeat_unit: str, repeat_every: int):
        return await self._run(self._db.update_task, task_id, task, next_due, coins, repeat_unit, repeat_every)

    async def delete_task(self, task_id: int):
        return await self._run(self._db.delete_task, task_id)

    async def get_history(self, user_id: int, limit: int = 20):
        return await self._run(self._db.get_history, user_id, limit)

    async def get_balance(self, user_id):
        return await self._run(self._db.get_balance, user_id)

    # -------- reminders --------

    async def get_tasks_to_remind(self, **kwargs):
        return await self._run(self._db.get_tasks_to_remind, **kwargs)

    async def mark_tasks_notified(self, task_ids, due_str):
        return await self._run(self._db.mark_tasks_notified, task_ids, due_str)

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
