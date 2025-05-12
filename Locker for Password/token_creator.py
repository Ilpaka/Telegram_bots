import os
import uuid
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import datetime

class TokenCreator:
    def __init__(self):
        self.token_filename = "secure_token.dat"
        
    def generate_token_key(self):
        """Генерирует уникальный ключ для токена"""
        return str(uuid.uuid4())
    
    def create_token(self, drive_path):
        """Создает токен на указанном USB-накопителе"""
        try:
            # Генерируем уникальный ключ
            token_key = self.generate_token_key()
            
            # Создаем структуру данных токена
            token_data = {
                "token_id": token_key,
                "created_at": datetime.datetime.now().isoformat(),
                "type": "simple_secure_token",
                "version": "1.0"
            }
            
            # Шифруем данные токена
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(token_key.encode()))
            
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(json.dumps(token_data).encode())
            
            # Сохраняем на диск
            token_path = os.path.join(drive_path, self.token_filename)
            with open(token_path, 'wb') as f:
                f.write(salt + encrypted_data)
            
            return token_key
            
        except Exception as e:
            raise Exception(f"Ошибка при создании токена: {str(e)}")
    
    def verify_token(self, drive_path, token_key):
        """Проверяет валидность токена на USB-накопителе"""
        try:
            token_path = os.path.join(drive_path, self.token_filename)
            if not os.path.exists(token_path):
                return False
                
            with open(token_path, 'rb') as f:
                data = f.read()
            
            # Извлекаем соль и зашифрованные данные
            salt = data[:16]
            encrypted_data = data[16:]
            
            # Воссоздаем ключ шифрования
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(token_key.encode()))
            
            # Расшифровываем данные
            fernet = Fernet(key)
            decrypted_data = json.loads(fernet.decrypt(encrypted_data))
            
            # Проверяем token_id
            return decrypted_data['token_id'] == token_key
            
        except Exception:
            return False 