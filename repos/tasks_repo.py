from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Optional, List


def add_months(dt: datetime, months: int) -> datetime:
    """
    Добавляет N месяцев к datetime.
    Если исходный день (например 31) не существует в целевом месяце,
    используется последний день целевого месяца.
    """
    y = dt.year
    m = dt.month + int(months)

    y += (m - 1) // 12
    m = (m - 1) % 12 + 1

    last_day = calendar.monthrange(y, m)[1]
    d = min(dt.day, last_day)
    return dt.replace(year=y, month=m, day=d)


class TasksRepo:
    def __init__(self, adb):
        self.db = adb  # AsyncDB (с fetchone/fetchall/execute/executemany/transaction)

    async def add_task(
        self,
        user_id: int,
        task: str,
        next_due: str,
        coins: int,
        repeat_unit: str,
        repeat_every: int,
        assigned_by: Optional[int] = None,
    ) -> int:
        def _fn(cur):
            cur.execute(
                """
                INSERT INTO tasks (user_id, task, next_due, coins, repeat_unit, repeat_every, completed, last_notified_due, assigned_by)
                VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)
                """,
                (user_id, task, next_due, int(coins), repeat_unit, int(repeat_every), assigned_by),
            )
            return cur.lastrowid

        return await self.db.transaction(_fn, immediate=False)

    async def get_task(self, task_id: int):
        return await self.db.fetchone(
            """
            SELECT id, user_id, task, next_due, coins, repeat_unit, repeat_every, completed, assigned_by
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        )

    async def update_task(
        self,
        task_id: int,
        task: str,
        next_due: str,
        coins: int,
        repeat_unit: str,
        repeat_every: int,
    ) -> int:
        return await self.db.execute(
            """
            UPDATE tasks
            SET task = ?,
                next_due = ?,
                coins = ?,
                repeat_unit = ?,
                repeat_every = ?,
                completed = 0,
                last_notified_due = NULL
            WHERE id = ?
            """,
            (task, next_due, int(coins), repeat_unit, int(repeat_every), task_id),
        )

    async def delete_task(self, task_id: int) -> int:
        return await self.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    async def list_tasks(self, user_id: int):
        return await self.db.fetchall(
            """
            SELECT id, task, next_due, coins, repeat_unit, repeat_every
            FROM tasks
            WHERE user_id = ? AND completed = 0
            ORDER BY next_due
            """,
            (user_id,),
        )

    async def list_tasks_until(self, user_id: int, until_due: str):
        return await self.db.fetchall(
            """
            SELECT id, task, next_due, coins, repeat_unit, repeat_every
            FROM tasks
            WHERE user_id = ? AND completed = 0 AND next_due <= ?
            ORDER BY next_due
            """,
            (user_id, until_due),
        )

    async def get_tasks_to_remind(self, due_str: str):
        return await self.db.fetchall(
            """
            SELECT id, user_id, task, next_due, coins
            FROM tasks
            WHERE completed = 0
              AND next_due = ?
              AND (last_notified_due IS NULL OR last_notified_due != ?)
            ORDER BY id
            """,
            (due_str, due_str),
        )

    async def mark_tasks_notified(self, task_ids: List[int], due_str: str) -> None:
        if not task_ids:
            return
        await self.db.executemany(
            "UPDATE tasks SET last_notified_due = ? WHERE id = ?",
            [(due_str, tid) for tid in task_ids],
        )

    async def complete_task(self, user_id: int, task_id: int):
        """
        Возвращает coins или None.
        Внутри транзакции:
          - проверяет задачу
          - пишет запись в task_completions
          - начисляет баланс
          - закрывает once или переносит повторяющуюся (day/week/month)
        """
        def _fn(cur):
            cur.execute(
                """
                SELECT coins, repeat_unit, repeat_every, next_due, task, assigned_by
                FROM tasks
                WHERE id = ? AND user_id = ? AND completed = 0
                """,
                (task_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None

            coins, repeat_unit, repeat_every, next_due, task_text, assigned_by = row

            # history
            cur.execute(
                """
                INSERT INTO task_completions (task_id, user_id, task_text, coins, completed_at, assigned_by)
                VALUES (?, ?, ?, ?, datetime('now'), ?)
                """,
                (task_id, user_id, task_text, int(coins), assigned_by),
            )

            # balance
            cur.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (int(coins), user_id),
            )

            # close or shift
            if repeat_unit == "once":
                cur.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,))
                return int(coins)

            dt = datetime.strptime(next_due, "%Y-%m-%d %H:%M")
            every = int(repeat_every or 1)

            if repeat_unit == "day":
                new_due = dt + timedelta(days=every)
            elif repeat_unit == "week":
                new_due = dt + timedelta(weeks=every)
            elif repeat_unit == "month":
                new_due = add_months(dt, every)
            else:
                # неизвестный repeat_unit -> закрываем
                cur.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,))
                return int(coins)

            cur.execute(
                """
                UPDATE tasks
                SET next_due = ?, last_notified_due = NULL
                WHERE id = ?
                """,
                (new_due.strftime("%Y-%m-%d %H:%M"), task_id),
            )

            return int(coins)

        return await self.db.transaction(_fn, immediate=True)
