import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Iterable, Sequence


class AsyncDB:
    """
    Универсальный async-слой над sqlite3:
    - все операции идут в одном выделенном потоке
    - репозитории выполняют SQL через fetchone/fetchall/execute/executemany/transaction
    """
    def __init__(self, sync_db):
        self._db = sync_db  # SQLiteDatabase (имеет .conn и .close())
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sqlite-db")

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, partial(fn, *args, **kwargs))

    async def fetchone(self, sql: str, params: Sequence[Any] = ()):
        def _fn():
            cur = self._db.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchone()
        return await self._run(_fn)

    async def fetchall(self, sql: str, params: Sequence[Any] = ()):
        def _fn():
            cur = self._db.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()
        return await self._run(_fn)

    async def execute(self, sql: str, params: Sequence[Any] = (), *, commit: bool = True) -> int:
        def _fn():
            cur = self._db.conn.cursor()
            cur.execute(sql, params)
            if commit:
                self._db.conn.commit()
            return cur.rowcount
        return await self._run(_fn)

    async def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]], *, commit: bool = True) -> int:
        def _fn():
            cur = self._db.conn.cursor()
            cur.executemany(sql, list(seq_of_params))
            if commit:
                self._db.conn.commit()
            return cur.rowcount
        return await self._run(_fn)

    async def transaction(self, fn, *, immediate: bool = True):
        """
        fn(cur) выполняется внутри транзакции.
        immediate=True => BEGIN IMMEDIATE (для покупок/баланса/конкурентных списаний).
        """
        def _tx():
            cur = self._db.conn.cursor()
            cur.execute("BEGIN IMMEDIATE;" if immediate else "BEGIN;")
            try:
                result = fn(cur)
                self._db.conn.commit()
                return result
            except Exception:
                self._db.conn.rollback()
                raise
        return await self._run(_tx)

    async def aclose(self):
        try:
            await self._run(self._db.close)
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
