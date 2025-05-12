import sqlite3
import datetime

# Регистрируем адаптер и конвертер для datetime
def adapt_datetime(dt: datetime.datetime) -> str:
    return dt.isoformat()

def convert_datetime(s: bytes) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.decode())

sqlite3.register_adapter(datetime.datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

def init_db():
    conn = sqlite3.connect('subscriptions.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()

    # Create users table (с добавлением is_blacklisted)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_blacklisted INTEGER DEFAULT 0
    )
    ''')

    # Create invoices table с типами timestamp
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'pending',
        created_at timestamp DEFAULT CURRENT_TIMESTAMP,
        updated_at timestamp,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    # Create subscriptions table с типами timestamp
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        invoice_id TEXT UNIQUE NOT NULL,
        start_date timestamp NOT NULL,
        end_date timestamp NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
    )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
