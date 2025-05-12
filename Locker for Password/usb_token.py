import win32api
import wmi
import hashlib
import os
import json
import psutil

class USBToken:
    def __init__(self):
        self.c = wmi.WMI()
        self.authorized_tokens = set()
        self.load_authorized_tokens()

    def load_authorized_tokens(self):
        """Загружает список авторизованных токенов из файла"""
        try:
            with open('authorized_tokens.txt', 'r') as f:
                self.authorized_tokens = set(line.strip() for line in f)
        except FileNotFoundError:
            self.authorized_tokens = set()

    def save_authorized_tokens(self):
        """Сохраняет список авторизованных токенов в файл"""
        with open('authorized_tokens.txt', 'w') as f:
            for token in self.authorized_tokens:
                f.write(token + '\n')

    def get_removable_drives(self):
        """Возвращает список букв съемных дисков с двоеточием"""
        drives = []
        for disk in self.c.Win32_LogicalDisk():
            if disk.DriveType == 2:
                drives.append(f"{disk.DeviceID}\\")
        return drives

    def get_usb_token_hash(self):
        """Получает хеш подключенного USB-устройства"""
        try:
            drives = self.get_removable_drives()
            if not drives:
                return None
            
            drive_letter = drives[0]
            volume_info = win32api.GetVolumeInformation(drive_letter)
            volume_serial = str(volume_info[1])
            return hashlib.sha256(volume_serial.encode()).hexdigest()
        except Exception:
            return None

    def is_token_authorized(self):
        """Проверяет авторизованность подключенного токена"""
        token_hash = self.get_usb_token_hash()
        return token_hash in self.authorized_tokens if token_hash else False

    def register_token(self):
        """Регистрирует текущий USB-токен"""
        token_hash = self.get_usb_token_hash()
        if token_hash:
            self.authorized_tokens.add(token_hash)
            self.save_authorized_tokens()
            return True
        return False

    def is_recovery_token_present(self) -> bool:
        """Проверяет наличие загрузочного токена восстановления"""
        try:
            drives = self.get_removable_drives()
            for drive in drives:
                token_path = os.path.join(drive, "token_info.json")
                if os.path.exists(token_path):
                    with open(token_path, 'r') as f:
                        data = json.load(f)
                        if data.get('type') == 'bootable_secure_token' and 'backup' in data:
                            return True
            return False
        except Exception:
            return False

    def remove_token(self):
        """Удаляет USB-токен из списка авторизованных и физически удаляет файл"""
        token_hash = self.get_usb_token_hash()
        if token_hash and token_hash in self.authorized_tokens:
            drives = self.get_removable_drives()
            for drive in drives:
                token_path = os.path.join(drive, "secure_token.dat")
                if os.path.exists(token_path):
                    try:
                        os.remove(token_path)
                    except Exception:
                        pass
            self.authorized_tokens.remove(token_hash)
            self.save_authorized_tokens()
            return True
        return False 