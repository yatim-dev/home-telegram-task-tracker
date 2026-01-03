import sqlite3
import time
from datetime import datetime, timedelta


class SQLiteDatabase:
    """
    Только соединение и схема/миграции.
    SQL-операции выполняются в repos через AsyncDB (fetchone/fetchall/...).
    """
    def __init__(self, db_name: str = "tasks.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False, timeout=30)
        self._tune_sqlite()
        self.create_tables()

    def _tune_sqlite(self) -> None:
        cur = self.conn.cursor()
        cur.execute("PRAGMA busy_timeout=5000;")

        for attempt in range(10):
            try:
                cur.execute("PRAGMA journal_mode=WAL;")
                break
            except sqlite3.OperationalError as e:
                if "locked" not in str(e).lower():
                    raise
                time.sleep(0.2 * (attempt + 1))
        else:
            raise sqlite3.OperationalError("database is locked: не удалось включить WAL")

        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA temp_store=MEMORY;")
        cur.execute("PRAGMA foreign_keys=ON;")
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    # -------- schema helpers --------

    def _table_columns(self, table: str) -> set[str]:
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}

    def _ensure_column(self, table: str, col: str, ddl: str) -> None:
        if col in self._table_columns(table):
            return
        cur = self.conn.cursor()
        cur.execute(ddl)
        self.conn.commit()

    def _ensure_indexes(self) -> None:
        cur = self.conn.cursor()

        cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_completed_due ON tasks(user_id, completed, next_due);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_completed ON tasks(completed, next_due);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_last_notified ON tasks(last_notified_due);")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_regkeys_expires ON registration_keys(expires_at);")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_compl_user_time ON task_completions(user_id, completed_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_compl_task_time ON task_completions(task_id, completed_at);")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_rewards_active ON rewards(is_active, price);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_purchases_user_status ON purchases(user_id, status, created_at);")

        self.conn.commit()

    def _migrate_legacy_tasks(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, time, completed
            FROM tasks
            WHERE next_due IS NULL AND time IS NOT NULL
        """)
        rows = cur.fetchall()
        now = datetime.now()

        for task_id, time_str, completed in rows:
            if completed:
                continue
            try:
                hhmm = datetime.strptime(time_str, "%H:%M").strftime("%H:%M")
            except Exception:
                continue

            candidate = datetime.strptime(now.strftime("%Y-%m-%d") + " " + hhmm, "%Y-%m-%d %H:%M")
            if candidate < now:
                candidate = candidate + timedelta(days=1)

            cur.execute("""
                UPDATE tasks
                SET next_due = ?, repeat_unit = 'day', repeat_every = 1, last_notified_due = NULL
                WHERE id = ?
            """, (candidate.strftime("%Y-%m-%d %H:%M"), task_id))

        self.conn.commit()

    def _ensure_default_rewards(self) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM rewards")
        cnt = int(cur.fetchone()[0])
        if cnt > 0:
            return

        cur.executemany("""
            INSERT INTO rewards (title, description, price, is_active)
            VALUES (?, ?, ?, 1)
        """, [
            ("30 минут игр", "Дополнительные 30 минут игр/экрана", 10),
            ("Выбор фильма", "Вы выбираете фильм/мультик вечером", 15),
            ("Скип одной мелкой задачи", "Можно пропустить одну мелкую обязанность", 25),
        ])
        self.conn.commit()

    # -------- schema --------

    def create_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute("BEGIN;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
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
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS registration_keys (
                reg_key TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                task_text TEXT NOT NULL,
                coins INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                assigned_by INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reward_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY(reward_id) REFERENCES rewards(id)
            )
        """)

        self.conn.commit()

        # migrations users
        self._ensure_column("users", "role", "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        self._ensure_column("users", "is_active", "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("users", "registered_at", "ALTER TABLE users ADD COLUMN registered_at TEXT")

        # migrations tasks
        self._ensure_column("tasks", "next_due", "ALTER TABLE tasks ADD COLUMN next_due TEXT")
        self._ensure_column("tasks", "repeat_unit", "ALTER TABLE tasks ADD COLUMN repeat_unit TEXT")
        self._ensure_column("tasks", "repeat_every", "ALTER TABLE tasks ADD COLUMN repeat_every INTEGER")
        self._ensure_column("tasks", "last_notified_due", "ALTER TABLE tasks ADD COLUMN last_notified_due TEXT")
        self._ensure_column("tasks", "assigned_by", "ALTER TABLE tasks ADD COLUMN assigned_by INTEGER")

        self._ensure_indexes()
        self._migrate_legacy_tasks()
        self._ensure_default_rewards()
