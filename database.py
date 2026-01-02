import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_name="tasks.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self._tune_sqlite()
        self.create_tables()

    def _tune_sqlite(self):
        cur = self.conn.cursor()
        # Быстрее и стабильнее под нагрузкой
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA temp_store=MEMORY;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA busy_timeout=5000;")
        self.conn.commit()

    def create_tables(self):
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task TEXT,
                time TEXT,
                coins INTEGER,
                completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                next_due TEXT,
                repeat_unit TEXT,
                repeat_every INTEGER,
                last_notified_due TEXT
            )
        ''')
        self.conn.commit()

        # Индексы критичны для быстрых /tasks и напоминаний
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_completed_due ON tasks(user_id, completed, next_due);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_completed ON tasks(completed, next_due);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_last_notified ON tasks(last_notified_due);")
        self.conn.commit()

        # --- миграции ---
        cursor.execute("PRAGMA table_info(tasks)")
        cols = {row[1] for row in cursor.fetchall()}

        def add_col(name, ddl):
            if name not in cols:
                cursor.execute(ddl)
                self.conn.commit()

        add_col("next_due", "ALTER TABLE tasks ADD COLUMN next_due TEXT")  # "YYYY-MM-DD HH:MM"
        add_col("repeat_unit", "ALTER TABLE tasks ADD COLUMN repeat_unit TEXT")  # "once"|"day"|"week"
        add_col("repeat_every", "ALTER TABLE tasks ADD COLUMN repeat_every INTEGER")  # N
        add_col("last_notified_due", "ALTER TABLE tasks ADD COLUMN last_notified_due TEXT")  # next_due который уже напомнили

        # Мягкая миграция старых задач: если next_due пустой, считаем их daily по time
        cursor.execute('''
            SELECT id, time, completed
            FROM tasks
            WHERE next_due IS NULL AND time IS NOT NULL
        ''')
        rows = cursor.fetchall()
        now = datetime.now()

        for task_id, time_str, completed in rows:
            if completed:
                # выполненные не трогаем
                continue
            try:
                hhmm = datetime.strptime(time_str, "%H:%M").strftime("%H:%M")
            except Exception:
                continue

            candidate = datetime.strptime(now.strftime("%Y-%m-%d") + " " + hhmm, "%Y-%m-%d %H:%M")
            if candidate < now:
                # если время уже прошло — перенесём на завтра
                candidate = candidate.replace(day=candidate.day)  # no-op, оставлено для читабельности
                candidate = candidate + __import__("datetime").timedelta(days=1)

            cursor.execute('''
                UPDATE tasks
                SET next_due = ?, repeat_unit = 'day', repeat_every = 1, last_notified_due = NULL
                WHERE id = ?
            ''', (candidate.strftime("%Y-%m-%d %H:%M"), task_id))

        self.conn.commit()

    def mark_tasks_notified(self, task_ids: list[int], due_str: str):
        """Batch update одним коммитом вместо N коммитов."""
        if not task_ids:
            return
        cursor = self.conn.cursor()
        cursor.executemany(
            "UPDATE tasks SET last_notified_due = ? WHERE id = ?",
            [(due_str, task_id) for task_id in task_ids],
        )
        self.conn.commit()

    def add_user(self, user_id, username):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username)
            VALUES (?, ?)
        ''', (user_id, username))
        self.conn.commit()

    def add_task(self, user_id, task, next_due, coins, repeat_unit, repeat_every):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (user_id, task, next_due, coins, repeat_unit, repeat_every, completed, last_notified_due)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
        ''', (user_id, task, next_due, coins, repeat_unit, repeat_every))
        self.conn.commit()
        return cursor.lastrowid

    def get_tasks(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, task, next_due, coins, repeat_unit, repeat_every
            FROM tasks
            WHERE user_id = ? AND completed = 0
            ORDER BY next_due
        ''', (user_id,))
        return cursor.fetchall()

    def get_tasks_to_remind(self, due_str: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, user_id, task, next_due, coins
            FROM tasks
            WHERE completed = 0
              AND next_due = ?
              AND (last_notified_due IS NULL OR last_notified_due != ?)
            ORDER BY id
        ''', (due_str, due_str))
        return cursor.fetchall()

    def mark_task_notified(self, task_id: int, due_str: str):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE tasks SET last_notified_due = ? WHERE id = ?', (due_str, task_id))
        self.conn.commit()

    def complete_task(self, user_id, task_id):
        """
        Возвращает coins, либо None.
        Для повторяющихся задач сдвигает next_due вперёд и НЕ ставит completed=1.
        Для разовой задачи ставит completed=1.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT coins, repeat_unit, repeat_every, next_due
            FROM tasks
            WHERE id = ? AND user_id = ? AND completed = 0
        ''', (task_id, user_id))
        row = cursor.fetchone()
        if not row:
            return None

        coins, repeat_unit, repeat_every, next_due = row

        # начисление монет
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (coins, user_id))

        if repeat_unit == "once":
            cursor.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))
        else:
            # сдвигаем next_due
            dt = datetime.strptime(next_due, "%Y-%m-%d %H:%M")
            if repeat_unit == "day":
                delta = __import__("datetime").timedelta(days=int(repeat_every or 1))
            elif repeat_unit == "week":
                delta = __import__("datetime").timedelta(weeks=int(repeat_every or 1))
            else:
                # неизвестный repeat_unit -> считаем разовой
                cursor.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))
                self.conn.commit()
                return coins

            new_due = dt + delta
            cursor.execute('''
                UPDATE tasks
                SET next_due = ?, last_notified_due = NULL
                WHERE id = ?
            ''', (new_due.strftime("%Y-%m-%d %H:%M"), task_id))

        self.conn.commit()
        return coins

    def get_balance(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0


db = Database()
