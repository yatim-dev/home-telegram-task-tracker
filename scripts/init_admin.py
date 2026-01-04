import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/data/tasks.db")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

if not ADMIN_USER_ID:
    print("ADMIN_USER_ID not set, skip admin init")
    raise SystemExit(0)

user_id = int(ADMIN_USER_ID)

con = sqlite3.connect(DB_PATH)
con.execute("PRAGMA busy_timeout = 5000;")  # на всякий случай
cur = con.cursor()

cur.execute("""
UPDATE users
SET is_active = 1,
    role = 'admin',
    registered_at = datetime('now')
WHERE user_id = ?;
""", (user_id,))
con.commit()

print("Admin init: updated rows =", cur.rowcount)
con.close()
