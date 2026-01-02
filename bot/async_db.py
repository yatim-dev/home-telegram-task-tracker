import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial


class AsyncDB:
    """
    Запускает ВСЕ sqlite-операции в одном выделенном потоке.
    Это убирает блокировки event loop и сильно ускоряет ответы бота.
    """
    def __init__(self, sync_db):
        self._db = sync_db
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sqlite-db")

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, partial(fn, *args, **kwargs))

    async def add_user(self, user_id, username):
        return await self._run(self._db.add_user, user_id, username)

    async def add_task(self, **kwargs):
        return await self._run(self._db.add_task, **kwargs)

    async def get_tasks(self, user_id):
        return await self._run(self._db.get_tasks, user_id)

    async def complete_task(self, user_id, task_id):
        return await self._run(self._db.complete_task, user_id, task_id)

    async def get_balance(self, user_id):
        return await self._run(self._db.get_balance, user_id)

    async def get_tasks_to_remind(self, **kwargs):
        return await self._run(self._db.get_tasks_to_remind, **kwargs)

    async def mark_tasks_notified(self, task_ids, due_str):
        return await self._run(self._db.mark_tasks_notified, task_ids, due_str)

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
