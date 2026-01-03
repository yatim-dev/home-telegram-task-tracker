import sqlite3
import time
import secrets
from datetime import datetime


class Database:
    def __init__(self, db_name="tasks.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False, timeout=30)
        self._tune_sqlite()
        self.create_tables()

    def _tune_sqlite(self):
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

        # --- миграции users ---
        cursor.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cursor.fetchall()}

        def add_user_col(name, ddl):
            if name not in user_cols:
                cursor.execute(ddl)
                self.conn.commit()

        add_user_col("role", "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        add_user_col("is_active", "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0")
        add_user_col("registered_at", "ALTER TABLE users ADD COLUMN registered_at TEXT")

        # --- миграции tasks ---
        cursor.execute("PRAGMA table_info(tasks)")
        task_cols = {row[1] for row in cursor.fetchall()}

        def add_task_col(name, ddl):
            if name not in task_cols:
                cursor.execute(ddl)
                self.conn.commit()

        add_task_col("next_due", "ALTER TABLE tasks ADD COLUMN next_due TEXT")
        add_task_col("repeat_unit", "ALTER TABLE tasks ADD COLUMN repeat_unit TEXT")
        add_task_col("repeat_every", "ALTER TABLE tasks ADD COLUMN repeat_every INTEGER")
        add_task_col("last_notified_due", "ALTER TABLE tasks ADD COLUMN last_notified_due TEXT")
        add_task_col("assigned_by", "ALTER TABLE tasks ADD COLUMN assigned_by INTEGER")

        # --- одноразовые ключи регистрации ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registration_keys (
                reg_key TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

        # --- история выполнений ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                task_text TEXT NOT NULL,
                coins INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                assigned_by INTEGER
            )
        ''')
        self.conn.commit()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reward_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new', -- new|used
                created_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY(reward_id) REFERENCES rewards(id)
            )
        ''')
        self.conn.commit()

        # --- индексы ---
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_completed_due ON tasks(user_id, completed, next_due);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_completed ON tasks(completed, next_due);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_last_notified ON tasks(last_notified_due);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_regkeys_expires ON registration_keys(expires_at);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compl_user_time ON task_completions(user_id, completed_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compl_task_time ON task_completions(task_id, completed_at);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rewards_active ON rewards(is_active, price);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchases_user_status ON purchases(user_id, status, created_at);")
        self.conn.commit()

        # --- мягкая миграция старых задач (если next_due пустой) ---
        cursor.execute('''
            SELECT id, time, completed
            FROM tasks
            WHERE next_due IS NULL AND time IS NOT NULL
        ''')
        rows = cursor.fetchall()
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
                candidate = candidate + __import__("datetime").timedelta(days=1)

            cursor.execute('''
                UPDATE tasks
                SET next_due = ?, repeat_unit = 'day', repeat_every = 1, last_notified_due = NULL
                WHERE id = ?
            ''', (candidate.strftime("%Y-%m-%d %H:%M"), task_id))

        self.conn.commit()

    # ----------------------------
    # Users / auth
    # ----------------------------

    def add_user(self, user_id, username):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username)
            VALUES (?, ?)
        ''', (user_id, username))

        cursor.execute('''
            UPDATE users SET username = ?
            WHERE user_id = ?
        ''', (username, user_id))

        self.conn.commit()

    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user_id, username, role, is_active, balance
            FROM users
            WHERE user_id = ?
        ''', (user_id,))
        return cursor.fetchone()

    def find_user_id_by_username(self, username: str):
        u = (username or "").strip()
        if u.startswith("@"):
            u = u[1:]
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user_id
            FROM users
            WHERE username IS NOT NULL AND lower(username) = lower(?)
            LIMIT 1
        ''', (u,))
        row = cursor.fetchone()
        return row[0] if row else None

    def list_users(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user_id, username, role, is_active, balance
            FROM users
            ORDER BY user_id
        ''')
        return cursor.fetchall()

    def activate_user(self, user_id: int, role: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users
            SET is_active = 1,
                role = ?,
                registered_at = ?
            WHERE user_id = ?
        ''', (role, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        self.conn.commit()

    # ----------------------------
    # Registration keys (одноразовые)
    # ----------------------------

    def create_registration_key(self, role: str, expires_at: str) -> str:
        if role not in ("user", "admin"):
            raise ValueError("role must be 'user' or 'admin'")
        datetime.strptime(expires_at, "%Y-%m-%d %H:%M")

        cursor = self.conn.cursor()
        for _ in range(10):
            key = secrets.token_urlsafe(10)
            try:
                cursor.execute('''
                    INSERT INTO registration_keys (reg_key, role, expires_at)
                    VALUES (?, ?, ?)
                ''', (key, role, expires_at))
                self.conn.commit()
                return key
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("Не удалось сгенерировать уникальный ключ")

    def consume_registration_key(self, key: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT role, expires_at
            FROM registration_keys
            WHERE reg_key = ?
        ''', (key,))
        row = cursor.fetchone()
        if not row:
            return None

        role, expires_at = row
        exp = datetime.strptime(expires_at, "%Y-%m-%d %H:%M")
        if datetime.now() > exp:
            cursor.execute("DELETE FROM registration_keys WHERE reg_key = ?", (key,))
            self.conn.commit()
            return None

        cursor.execute("DELETE FROM registration_keys WHERE reg_key = ?", (key,))
        self.conn.commit()
        return role

    # ----------------------------
    # Tasks + reminders
    # ----------------------------

    def add_task(self, user_id, task, next_due, coins, repeat_unit, repeat_every, assigned_by=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (user_id, task, next_due, coins, repeat_unit, repeat_every, completed, last_notified_due, assigned_by)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)
        ''', (user_id, task, next_due, coins, repeat_unit, repeat_every, assigned_by))
        self.conn.commit()
        return cursor.lastrowid

    def get_task(self, task_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, user_id, task, next_due, coins, repeat_unit, repeat_every, completed, assigned_by
            FROM tasks
            WHERE id = ?
        ''', (task_id,))
        return cursor.fetchone()

    def update_task(self, task_id: int, task: str, next_due: str, coins: int, repeat_unit: str, repeat_every: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE tasks
            SET task = ?,
                next_due = ?,
                coins = ?,
                repeat_unit = ?,
                repeat_every = ?,
                completed = 0,
                last_notified_due = NULL
            WHERE id = ?
        ''', (task, next_due, coins, repeat_unit, repeat_every, task_id))
        self.conn.commit()
        return cursor.rowcount

    def delete_task(self, task_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return cursor.rowcount

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

    def mark_tasks_notified(self, task_ids: list[int], due_str: str):
        if not task_ids:
            return
        cursor = self.conn.cursor()
        cursor.executemany(
            "UPDATE tasks SET last_notified_due = ? WHERE id = ?",
            [(due_str, task_id) for task_id in task_ids],
        )
        self.conn.commit()

    # ----------------------------
    # History
    # ----------------------------

    def add_completion(self, task_id: int, user_id: int, task_text: str, coins: int, assigned_by=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO task_completions (task_id, user_id, task_text, coins, completed_at, assigned_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (task_id, user_id, task_text, coins, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), assigned_by))
        self.conn.commit()

    def get_history(self, user_id: int, limit: int = 20):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, task_id, task_text, coins, completed_at, assigned_by
            FROM task_completions
            WHERE user_id = ?
            ORDER BY completed_at DESC
            LIMIT ?
        ''', (user_id, int(limit)))
        return cursor.fetchall()

    # ----------------------------
    # Complete task
    # ----------------------------

    def complete_task(self, user_id, task_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT coins, repeat_unit, repeat_every, next_due, task, assigned_by
            FROM tasks
            WHERE id = ? AND user_id = ? AND completed = 0
        ''', (task_id, user_id))
        row = cursor.fetchone()
        if not row:
            return None

        coins, repeat_unit, repeat_every, next_due, task_text, assigned_by = row

        # 1) записываем выполнение в историю (всегда)
        cursor.execute('''
            INSERT INTO task_completions (task_id, user_id, task_text, coins, completed_at, assigned_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (task_id, user_id, task_text, coins, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), assigned_by))

        # 2) начисляем монеты
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (coins, user_id))

        # 3) обновляем/закрываем задачу
        if repeat_unit == "once":
            cursor.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))
        else:
            dt = datetime.strptime(next_due, "%Y-%m-%d %H:%M")
            if repeat_unit == "day":
                delta = __import__("datetime").timedelta(days=int(repeat_every or 1))
            elif repeat_unit == "week":
                delta = __import__("datetime").timedelta(weeks=int(repeat_every or 1))
            else:
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

    def get_tasks_until(self, user_id: int, until_due: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, task, next_due, coins, repeat_unit, repeat_every
            FROM tasks
            WHERE user_id = ? AND completed = 0 AND next_due <= ?
            ORDER BY next_due
        ''', (user_id, until_due))
        return cursor.fetchall()

    def get_balance(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

    # ----------------------------
    # Shop
    # ----------------------------

    def list_rewards(self, active_only: bool = True):
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute('''
                SELECT id, title, description, price
                FROM rewards
                WHERE is_active = 1
                ORDER BY price, id
            ''')
        else:
            cursor.execute('''
                SELECT id, title, description, price, is_active
                FROM rewards
                ORDER BY is_active DESC, price, id
            ''')
        return cursor.fetchall()

    def get_reward(self, reward_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, description, price, is_active
            FROM rewards
            WHERE id = ?
        ''', (reward_id,))
        return cursor.fetchone()

    def buy_reward(self, user_id: int, reward_id: int):
        """
        Атомарная покупка:
        - проверяем, что награда активна
        - проверяем баланс
        - списываем монеты
        - создаём purchase (status=new)
        Возвращает: (ok, purchase_id, error_code, new_balance)
          error_code: 'not_found' | 'inactive' | 'not_enough'
        """
        cursor = self.conn.cursor()

        # BEGIN IMMEDIATE = забираем write-lock, чтобы баланс не “гонялся”
        cursor.execute("BEGIN IMMEDIATE;")

        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        balance = row[0] if row else 0

        cursor.execute("SELECT id, price, is_active, title FROM rewards WHERE id = ?", (reward_id,))
        r = cursor.fetchone()
        if not r:
            self.conn.rollback()
            return (False, None, "not_found", balance)

        _, price, is_active, _title = r
        if int(is_active) != 1:
            self.conn.rollback()
            return (False, None, "inactive", balance)

        if balance < int(price):
            self.conn.rollback()
            return (False, None, "not_enough", balance)

        # списание
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (int(price), user_id))

        # покупка
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO purchases (user_id, reward_id, price, status, created_at)
            VALUES (?, ?, ?, 'new', ?)
        ''', (user_id, reward_id, int(price), now))
        purchase_id = cursor.lastrowid

        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()[0]

        self.conn.commit()
        return (True, purchase_id, None, new_balance)

    def get_inventory(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.id, r.title, r.description, p.price, p.created_at
            FROM purchases p
            JOIN rewards r ON r.id = p.reward_id
            WHERE p.user_id = ? AND p.status = 'new'
            ORDER BY p.created_at DESC, p.id DESC
        ''', (user_id,))
        return cursor.fetchall()

    def use_purchase_with_info(self, user_id: int, purchase_id: int):
        """
        Помечает купон использованным и возвращает инфо о награде.
        Возвращает:
          (ok: bool, title: str|None, price: int|None)
        """
        cursor = self.conn.cursor()

        # получим информацию о купоне (только если он new и принадлежит user_id)
        cursor.execute("""
            SELECT p.id, p.price, r.title
            FROM purchases p
            JOIN rewards r ON r.id = p.reward_id
            WHERE p.id = ? AND p.user_id = ? AND p.status = 'new'
        """, (purchase_id, user_id))
        row = cursor.fetchone()
        if not row:
            return False, None, None

        _pid, price, title = row
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE purchases
            SET status = 'used', used_at = ?
            WHERE id = ? AND user_id = ? AND status = 'new'
        """, (now, purchase_id, user_id))

        self.conn.commit()
        if cursor.rowcount <= 0:
            return False, None, None

        return True, title, int(price)

    def list_admin_ids(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT user_id
            FROM users
            WHERE role = 'admin' AND is_active = 1
            ORDER BY user_id
        """)
        return [row[0] for row in cursor.fetchall()]

    def add_reward(self, title: str, description: str, price: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO rewards (title, description, price, is_active)
            VALUES (?, ?, ?, 1)
        """, (title, description, int(price)))
        self.conn.commit()
        return cursor.lastrowid

    def set_reward_description(self, reward_id: int, description: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE rewards SET description = ?
            WHERE id = ?
        """, (description, reward_id))
        self.conn.commit()
        return cursor.rowcount

    def set_reward_active(self, reward_id: int, is_active: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE rewards SET is_active = ?
            WHERE id = ?
        """, (int(is_active), reward_id))
        self.conn.commit()
        return cursor.rowcount

    def list_rewards_admin(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, title, description, price, is_active
            FROM rewards
            ORDER BY is_active DESC, price, id
        """)
        return cursor.fetchall()

db = Database()
