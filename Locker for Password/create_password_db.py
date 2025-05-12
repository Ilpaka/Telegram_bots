import sqlite3
import hashlib
from password_encryption import PasswordEncryption 
import json
from cryptography.fernet import Fernet

class PasswordDatabase:
    def __init__(self):
        self.crypto = PasswordEncryption()
        self.create_tables()
    def delete_additional_email(self, email_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_emails WHERE id=? AND is_primary=0', (email_id,))
            conn.commit()

    def delete_password_by_id(self, password_id, user_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM passwords WHERE id = ? AND user_id = ?", (password_id, user_id))
            conn.commit() 
    def create_tables(self):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            # Создаем таблицу пользователей (логин и email должны быть уникальны)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    base_password TEXT,
                    requires_token INTEGER DEFAULT 0
                )
            ''')
            # Создаем таблицу паролей с новыми столбцами website и account
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS passwords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    website TEXT NOT NULL,
                    account TEXT NOT NULL,
                    encrypted_password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            # Если таблица уже существует, проверяем наличие новых столбцов и добавляем их, если отсутствуют
            cursor.execute("PRAGMA table_info(passwords)")
            columns = [col[1] for col in cursor.fetchall()]
            if "website" not in columns:
                cursor.execute("ALTER TABLE passwords ADD COLUMN website TEXT NOT NULL DEFAULT ''")
            if "account" not in columns:
                cursor.execute("ALTER TABLE passwords ADD COLUMN account TEXT NOT NULL DEFAULT ''")
            # Создаем таблицу для дополнительных email
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    is_primary INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            # Добавляем поле base_password в таблицу users
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if "base_password" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN base_password TEXT")
            # Добавляем поле requires_token в таблицу users
            if "requires_token" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN requires_token INTEGER DEFAULT 0")
            conn.commit()

    def save_password(self, website, account, password, user_id):
        encrypted_password = self.crypto.encrypt_password(password)
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO passwords (user_id, website, account, encrypted_password)
                VALUES (?, ?, ?, ?)
            ''', (user_id, website, account, encrypted_password))
            conn.commit()

    def get_all_passwords(self, user_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT rowid, website, account, encrypted_password FROM passwords WHERE user_id = ?', (user_id,))
            rows = cursor.fetchall()
            
            passwords = []
            for row in rows:
                # row всегда будет иметь 4 элемента: (password_id, website, account, encrypted_password)
                password_id, website, account, encrypted_password = row
                decrypted_password = self.crypto.decrypt_password(encrypted_password)
                passwords.append((password_id, website, account, decrypted_password))
            return passwords

    def delete_password(self, service, user_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM passwords WHERE website = ? AND user_id = ?', (service, user_id))
            conn.commit()

    def create_user(self, username, email, password, requires_token=False):
        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            with sqlite3.connect('passwords.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password, requires_token)
                    VALUES (?, ?, ?, ?)
                ''', (username, email, hashed, 1 if requires_token else 0))
                user_id = cursor.lastrowid
                # Сохраняем основной email в user_emails c флагом is_primary=1
                cursor.execute('''
                    INSERT INTO user_emails (user_id, email, is_primary)
                    VALUES (?, ?, 1)
                ''', (user_id, email))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def login_user(self, login, password):
        hashed = hashlib.sha256(password.encode()).hexdigest()
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM users 
                WHERE (username = ? OR email = ?) AND password = ?
            ''', (login, login, hashed))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None

    def get_all_users(self):
        """Получает список всех пользователей"""
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT username, email FROM users')
            return cursor.fetchall()

    def has_users(self):
        """Проверяет, есть ли зарегистрированные пользователи"""
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            return cursor.fetchone()[0] > 0 

    def update_password(self, password_id, website, account, new_password, user_id):
        encrypted_password = self.crypto.encrypt_password(new_password)
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            if password_id is not None:
                cursor.execute('UPDATE passwords SET website=?, account=?, encrypted_password=? WHERE rowid=? AND user_id=?',
                               (website, account, encrypted_password, password_id, user_id))
            else:
                cursor.execute('UPDATE passwords SET website=?, account=?, encrypted_password=? WHERE website=? AND user_id=?',
                               (website, account, encrypted_password, website, user_id))
            conn.commit() 

    def get_user_info(self, user_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT username, email FROM users WHERE id = ?', (user_id,))
            return cursor.fetchone()

    def get_user_emails(self, user_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, email, is_primary FROM user_emails WHERE user_id = ?', (user_id,))
            return cursor.fetchall()

    def update_user_info(self, user_id, new_username, new_primary_email, new_password):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            if new_password:
                hashed = hashlib.sha256(new_password.encode()).hexdigest()
                cursor.execute('UPDATE users SET username=?, email=?, password=? WHERE id=?',
                               (new_username, new_primary_email, hashed, user_id))
            else:
                cursor.execute('UPDATE users SET username=?, email=? WHERE id=?',
                               (new_username, new_primary_email, user_id))
            # Обновляем основной email в user_emails
            cursor.execute('UPDATE user_emails SET email=? WHERE user_id=? AND is_primary=1',
                           (new_primary_email, user_id))
            conn.commit()

    def add_additional_email(self, user_id, email):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO user_emails (user_id, email, is_primary)
                    VALUES (?, ?, 0)
                ''', (user_id, email))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def delete_additional_email(self, email_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_emails WHERE id=? AND is_primary=0', (email_id,))
            conn.commit() 

    def update_base_password(self, user_id, base_password):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET base_password = ? WHERE id = ?', (base_password, user_id))
            conn.commit()

    def get_base_password(self, user_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT base_password FROM users WHERE id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None 

    def user_requires_token(self, user_id):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT requires_token FROM users WHERE id = ?', (user_id,))
            result = cursor.fetchone()
            return bool(result[0]) if result else False 

    def update_token_requirement(self, user_id, requires_token):
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET requires_token = ? WHERE id = ?', 
                          (1 if requires_token else 0, user_id))
            conn.commit() 

    def export_user_data(self, user_id: int, encryption_key: str) -> dict:
        """Экспортирует все данные пользователя в зашифрованном виде"""
        fernet = Fernet(encryption_key)
        
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            
            # Получаем данные пользователя
            user_data = {
                'user_info': cursor.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone(),
                'passwords': cursor.execute('SELECT * FROM passwords WHERE user_id=?', (user_id,)).fetchall(),
                'emails': cursor.execute('SELECT * FROM user_emails WHERE user_id=?', (user_id,)).fetchall()
            }
            
            # Шифруем данные
            encrypted_data = fernet.encrypt(json.dumps(user_data).encode())
            return {'data': encrypted_data.decode(), 'version': '1.0'} 

    def delete_user(self, user_id: int) -> bool:
        """Удаляет пользователя и все его данные"""
        try:
            with sqlite3.connect('passwords.db') as conn:
                cursor = conn.cursor()
                # Удаляем все пароли пользователя
                cursor.execute("DELETE FROM passwords WHERE user_id=?", (user_id,))
                # Удаляем дополнительные email
                cursor.execute("DELETE FROM user_emails WHERE user_id=?", (user_id,))
                # Удаляем самого пользователя
                cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
                conn.commit()
                return True
        except Exception:
            return False 