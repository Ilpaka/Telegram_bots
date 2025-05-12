"""
Password Manager Application
Provides secure password storage with optional USB token authentication.
Features:
- User account management
- Password generation and storage
- USB token security
- Email management
"""

# Standard library imports
import sys
import string
import random
import sqlite3
import re
import hashlib  # Добавляем импорт hashlib
from typing import Optional, Tuple
import os

# PyQt imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QAbstractItemView,
    QHBoxLayout, QLineEdit, QLabel, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QStyle, QDialog, QGroupBox, 
    QCheckBox, QPushButton, QGraphicsDropShadowEffect, QGraphicsBlurEffect,
    QGraphicsOpacityEffect, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer, 
    QPoint, QRect
)
from PyQt6.QtGui import (
    QFont, QIcon, QColor
)

# Local imports
from create_password_db import PasswordDatabase
from usb_token import USBToken
from animated_button import AnimatedButton
from bootable_token_creator import BootableTokenCreator

# Constants
MIN_PASSWORD_LENGTH = 16
PASSWORD_MASK = '•' * 12
TOKEN_CHECK_INTERVAL = 1000  # milliseconds
DEFAULT_WINDOW_SIZE = (800, 600)
DEFAULT_DIALOG_SIZE = (400, 300)

# Styles
BUTTON_STYLE = """
    QPushButton {
        background-color: #4f8ef7;
        border: none;
        border-radius: 8px;
        padding: 8px;
        color: white;
    }
    QPushButton:hover {
        background-color: #1e90ff;
    }
"""

DIALOG_STYLE = """
    QDialog {
        background-color: white;
        border-radius: 10px;
    }
"""

class AnimatedButton(QPushButton):
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(5)
        self.shadow.setOffset(0, 2)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.shadow)

    def enterEvent(self, event):
        animation = QPropertyAnimation(self.shadow, b"blurRadius", self)
        animation.setDuration(200)
        animation.setStartValue(self.shadow.blurRadius())
        animation.setEndValue(15)
        animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        animation.start()
        self._animation = animation  # предотвращаем сборку мусора
        super().enterEvent(event)

    def leaveEvent(self, event):
        animation = QPropertyAnimation(self.shadow, b"blurRadius", self)
        animation.setDuration(200)
        animation.setStartValue(self.shadow.blurRadius())
        animation.setEndValue(5)
        animation.setEasingCurve(QEasingCurve.Type.InQuad)
        animation.start()
        self._animation = animation
        super().leaveEvent(event)

class LoginWindow(QMainWindow):
    """
    Main login window for the application.
    Handles user authentication and registration.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Account Login")
        self.setMinimumSize(400, 300)
        
        # Initialize database and USB token
        self.db = PasswordDatabase()
        self.usb_token = USBToken()
        
        # Setup UI
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        self.refresh_ui()

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_accounts_list(self):
        """Показывает список существующих аккаунтов"""
        self.clear_layout()
        
        # Заголовок
        title_label = QLabel("Выберите аккаунт")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        
        # Контейнер для списка аккаунтов
        accounts_widget = QWidget()
        accounts_layout = QVBoxLayout(accounts_widget)
        accounts_layout.setSpacing(10)
        
        # Получаем список пользователей
        users = self.db.get_all_users()
        
        for username, email in users:
            # Создаем карточку для каждого аккаунта
            account_card = QWidget()
            account_card.setObjectName("accountCard")
            card_layout = QHBoxLayout(account_card)
            
            # Иконка пользователя
            icon_label = QLabel("👤")
            icon_label.setFont(QFont("Segoe UI", 20))
            
            # Информация об аккаунте
            info_widget = QWidget()
            info_layout = QVBoxLayout(info_widget)
            username_label = QLabel(username)
            email_label = QLabel(email)
            email_label.setStyleSheet("color: #666;")
            info_layout.addWidget(username_label)
            info_layout.addWidget(email_label)
            
            # Кнопка входа
            login_btn = AnimatedButton("Login")
            login_btn.clicked.connect(lambda checked, u=username: self.show_login_form(u))
            
            card_layout.addWidget(icon_label)
            card_layout.addWidget(info_widget, 1)
            card_layout.addWidget(login_btn)
            
            accounts_layout.addWidget(account_card)
        
        # Кнопка создания нового аккаунта
        new_account_btn = AnimatedButton("Create New Account")
        new_account_btn.clicked.connect(lambda: self.show_registration_form())
        
        # Добавляем все элементы на форму
        self.layout.addWidget(title_label)
        self.layout.addWidget(accounts_widget)
        self.layout.addWidget(new_account_btn)

    def show_login_form(self, prefill_username=None):
        self.clear_layout()
        title_label = QLabel("Welcome to Password Manager")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Username or Email")
        if prefill_username:
            self.login_edit.setText(prefill_username)

        self.login_password_edit = QLineEdit()
        self.login_password_edit.setPlaceholderText("Password")
        self.login_password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        login_btn = AnimatedButton("Login")
        back_btn = AnimatedButton("Back")

        login_btn.clicked.connect(self.login)
        back_btn.clicked.connect(self.show_accounts_list)

        self.layout.addWidget(title_label)
        self.layout.addWidget(self.login_edit)
        self.layout.addWidget(self.login_password_edit)
        self.layout.addWidget(login_btn)
        self.layout.addWidget(back_btn)

    def show_registration_form(self):
        """Показывает форму регистрации нового аккаунта"""
        self.clear_layout()
        
        # Заголовок
        title = QLabel("Создать новый аккаунт")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)
        
        # Поля ввода
        self.reg_username_edit = QLineEdit()
        self.reg_username_edit.setPlaceholderText("Имя пользователя")
        
        self.reg_email_edit = QLineEdit()
        self.reg_email_edit.setPlaceholderText("Email")
        
        self.reg_password_edit = QLineEdit()
        self.reg_password_edit.setPlaceholderText("Password")
        self.reg_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.reg_confirm_edit = QLineEdit()
        self.reg_confirm_edit.setPlaceholderText("Confirm Password")
        self.reg_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Кнопка регистрации
        register_btn = AnimatedButton("Register")
        register_btn.clicked.connect(self.register)
        
        # Добавляем элементы на форму
        self.layout.addWidget(self.reg_username_edit)
        self.layout.addWidget(self.reg_email_edit)
        self.layout.addWidget(self.reg_password_edit)
        self.layout.addWidget(self.reg_confirm_edit)
        self.layout.addWidget(register_btn)

    def login(self):
        login_text = self.login_edit.text()
        password = self.login_password_edit.text()
        
        user_id = self.db.login_user(login_text, password)
        if not user_id:
            QMessageBox.warning(self, "Error", "Invalid credentials!")
            return
        
        # Проверяем, требуется ли токен для этого пользователя
        if self.db.user_requires_token(user_id):
            if not self.usb_token.is_token_authorized():
                QMessageBox.warning(self, "Error", "USB-токен не обнаружен или не авторизован!")
                return
        
        # Проверяем наличие загрузочного токена для восстановления
        if self.usb_token.is_recovery_token_present():
            from recovery_ui import RecoveryWindow  # Добавляем импорт
            self.recovery_window = RecoveryWindow()
            self.recovery_window.show()
            return  # Прерываем обычный вход
        
        # Обычный вход
        self.pm = PasswordManager(user_id)
        self.pm.show()
        self.close()

    def register(self):
        username = self.reg_username_edit.text()
        email = self.reg_email_edit.text()
        password = self.reg_password_edit.text()
        confirm_password = self.reg_confirm_edit.text()
        
        if not username or not email or not password or not confirm_password:
            QMessageBox.warning(self, "Error", "Please fill in all fields!")
            return
        
        if not validate_email(email):
            QMessageBox.warning(self, "Error", "Please enter a valid email address!")
            return
        
        if password != confirm_password:
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return
        
        # Спрашиваем пользователя о регистрации USB-токена
        reply = QMessageBox.question(self, 'USB Token Registration',
                                   'Would you like to register a USB token for additional security?',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        requires_token = False
        if reply == QMessageBox.StandardButton.Yes:
            requires_token = True
        
        # Создаем пользователя один раз
        success = self.db.create_user(username, email, password, requires_token)
        if not success:
            QMessageBox.warning(self, "Error", 
                "Account creation failed. Username or Email may already exist.")
            return
        
        # Если требуется токен, показываем диалог регистрации
        if requires_token:
            user_id = self.db.login_user(username, password)
            token_dialog = USBTokenRegistrationDialog(self, self.db, user_id)
            if token_dialog.exec() == QDialog.DialogCode.Accepted:
                self.usb_token.register_token()
                QMessageBox.information(self, "Success", 
                    "Account created and USB token registered!")
            else:
                # Если отменили регистрацию токена, удаляем пользователя
                self.db.delete_user(user_id)
                return
        else:
            QMessageBox.information(self, "Success", 
                "Account created!")
        
        # Показываем окно выбора аккаунта вместо окна входа
        self.show_accounts_list()

    def check_token(self):
        """Проверяет наличие USB-токена (устаревший метод)"""
        # Заменяем на актуальный метод проверки
        if not self.usb_token.is_token_authorized():
            QMessageBox.warning(self, "Ошибка", "USB-токен не обнаружен!")
            self.close()

    def refresh_ui(self):
        """Обновляет интерфейс в зависимости от наличия пользователей"""
        if not self.db.has_users():
            self.show_registration_form()
        else:
            self.show_accounts_list()

class PasswordManager(QMainWindow):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.db = PasswordDatabase()
        self.usb_token = USBToken()
        self.login_window = None  # Добавляем атрибут для хранения окна входа
        
        # Запускаем таймер для проверки наличия токена только если он требуется
        if self.db.user_requires_token(self.user_id):
            self.token_check_timer = QTimer(self)
            self.token_check_timer.timeout.connect(self.check_token)
            self.token_check_timer.start(1000)  # Проверка каждую секунду
        
        self.setWindowTitle("Password Manager")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.update_password_table()
        self.password_table.cellClicked.connect(self.handle_password_cell_clicked)

    def check_token(self):
        if not self.usb_token.is_token_authorized():
            # Останавливаем таймер перед закрытием окна
            self.token_check_timer.stop()
            QMessageBox.critical(self, "Ошибка", "USB-токен отключен! Приложение будет закрыто.")
            
            # Создаем новое окно входа перед закрытием текущего
            self.login_window = LoginWindow()
            self.login_window.show()
            
            # Закрываем текущее окно
            self.close()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Верхняя панель с иконками
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(20, 10, 20, 10)

        # Левая часть с заголовком
        title_label = QLabel("Password Manager")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        top_bar_layout.addWidget(title_label)

        # Правая часть с иконками
        icons_widget = QWidget()
        icons_layout = QHBoxLayout(icons_widget)
        icons_layout.setSpacing(15)

        # Кнопка импорта паролей
        import_btn = AnimatedButton()
        import_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
        import_btn.setIconSize(QSize(24, 24))
        import_btn.setObjectName("iconButton")
        import_btn.setToolTip("Импорт паролей")
        import_btn.clicked.connect(self.import_passwords)

        # Кнопка экспорта паролей
        export_btn = AnimatedButton()
        export_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
        export_btn.setIconSize(QSize(24, 24))
        export_btn.setObjectName("iconButton")
        export_btn.setToolTip("Экспорт паролей")
        export_btn.clicked.connect(self.export_passwords)

        # Кнопка добавления пароля
        add_btn = AnimatedButton()
        add_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        add_btn.setIconSize(QSize(24, 24))
        add_btn.setObjectName("iconButton")
        add_btn.setToolTip("Добавить новый пароль")
        add_btn.clicked.connect(self.show_password_window)

        # Кнопка настроек аккаунта
        account_btn = AnimatedButton()
        account_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        account_btn.setIconSize(QSize(24, 24))
        account_btn.setObjectName("iconButton")
        account_btn.setToolTip("Настройки аккаунта")
        account_btn.clicked.connect(self.open_account_page)

        # Кнопка выхода
        logout_btn = AnimatedButton()
        logout_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        logout_btn.setIconSize(QSize(24, 24))
        logout_btn.clicked.connect(self.logout)

        # Добавляем все кнопки в layout в нужном порядке
        icons_layout.addWidget(import_btn)
        icons_layout.addWidget(export_btn)
        icons_layout.addWidget(add_btn)
        icons_layout.addWidget(account_btn)
        icons_layout.addWidget(logout_btn)
        top_bar_layout.addWidget(icons_widget, alignment=Qt.AlignmentFlag.AlignRight)

        # Таблица паролей
        self.password_table = QTableWidget()
        self.password_table.setObjectName("passwordTable")
        self.password_table.setColumnCount(4)  # site, account, password, actions
        self.password_table.setHorizontalHeaderLabels(["Сайт", "Аккаунт", "Пароль", "Действия"])
        self.password_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.password_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.password_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.password_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.password_table.setColumnWidth(3, 200)
        self.password_table.verticalHeader().setVisible(False)
        self.password_table.setShowGrid(False)
        self.password_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.password_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        layout.addWidget(top_bar)
        layout.addWidget(self.password_table)

    def update_password_table(self):
        passwords = self.db.get_all_passwords(self.user_id)
        self.password_table.setRowCount(len(passwords))
        
        for row, (password_id, website, account, decrypted_password) in enumerate(passwords):
            # Создаем элементы таблицы
            service_item = QTableWidgetItem(website)
            account_item = QTableWidgetItem(account)
            # Отображаем пароль скрытым точками (по 12 символов, как в toggle-функции)
            password_item = QTableWidgetItem('•' * 12)
            password_item.setData(Qt.ItemDataRole.UserRole, decrypted_password)
            
            # Создаем виджет с кнопками действий
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 0, 5, 0)
            actions_layout.setSpacing(5)
            
            # Кнопки действий
            show_btn = AnimatedButton()
            show_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton))
            show_btn.setObjectName("tableButton")
            show_btn.setToolTip("Show/Hide password")
            show_btn.clicked.connect(lambda checked, r=row, p=decrypted_password, b=show_btn: self.toggle_password_visibility(r, p, b))

            edit_btn = AnimatedButton()
            edit_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            edit_btn.setObjectName("tableButton")
            edit_btn.setToolTip("Edit password")
            edit_btn.clicked.connect(lambda checked, pid=password_id, w=website, a=account, p=decrypted_password: self.edit_password(pid, w, a, p))

            delete_btn = AnimatedButton()
            delete_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
            delete_btn.setObjectName("tableButton")
            delete_btn.setToolTip("Delete password")
            delete_btn.clicked.connect(lambda checked, pid=password_id: self.delete_password_prompt(pid))

            actions_layout.addWidget(show_btn)
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            
            # Добавляем элементы в таблицу
            self.password_table.setItem(row, 0, service_item)
            self.password_table.setItem(row, 1, account_item)
            self.password_table.setItem(row, 2, password_item)
            self.password_table.setCellWidget(row, 3, actions_widget)
            self.password_table.setRowHeight(row, 60)

    def toggle_password_visibility(self, row, password, button):
        current_text = self.password_table.item(row, 2).text()
        if current_text.startswith('•'):
            self.password_table.item(row, 2).setText(password)
            button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton))
        else:
            self.password_table.item(row, 2).setText('•' * 12)
            button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton))

    def copy_password(self, password):
        clipboard = QApplication.clipboard()
        clipboard.setText(password)
        
    def show_password_window(self, is_edit=False, password_id=None, website="", account="", password=""):
        # Применяем блюр к центральному виджету, чтобы заблокировать взаимодействие
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(10)
        self.centralWidget().setGraphicsEffect(blur_effect)
        
        pw_window = PasswordWindow(self.user_id, self.db, self, is_edit, password_id, website, account, password)
        pw_window.show()

    def edit_password(self, password_id, website, account, password):
        # Применяем блюр к центральному виджету, чтобы заблокировать взаимодействие
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(10)
        self.centralWidget().setGraphicsEffect(blur_effect)
        
        pw_window = PasswordWindow(self.user_id, self.db, self, is_edit=True, password_id=password_id, website=website, account=account, password=password)
        pw_window.show()

    def open_account_page(self):
        cabinet = UserCabinetWindow(self.user_id, self.db, self)
        cabinet.show()

    def logout(self):
        self.close()
        self.login_window = LoginWindow()
        self.login_window.show()

    def delete_password_prompt(self, password_id):
        input_pwd, ok = QInputDialog.getText(self, 
            "Подтверждение удаления", 
            "Введите пароль от учетной записи для подтверждения удаления:", 
            QLineEdit.EchoMode.Password)
        if ok:
            hashed = hashlib.sha256(input_pwd.encode()).hexdigest()
            with sqlite3.connect('passwords.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password FROM users WHERE id=?", (self.user_id,))
                row = cursor.fetchone()
            if not row or row[0] != hashed:
                QMessageBox.warning(self, "Ошибка", "Неверный пароль учетной записи.")
                return
            # Если подтверждено, вызываем метод удаления по id
            self.db.delete_password_by_id(password_id, self.user_id)
            self.update_password_table()
            QMessageBox.information(self, "Успех", "Пароль удален.")

    def handle_password_cell_clicked(self, row, column):
        if column == 2:  # колонка с паролем
            item = self.password_table.item(row, column)
            if item:
                real_password = item.data(Qt.ItemDataRole.UserRole)
                if real_password:
                    self.copy_password(real_password)
                    from PyQt6.QtWidgets import QToolTip
                    # Отобразим кратковременное уведомление
                    rect = self.password_table.visualItemRect(item)
                    global_pos = self.password_table.viewport().mapToGlobal(rect.center())
                    QToolTip.showText(global_pos, "Пароль скопирован!")

    def closeEvent(self, event):
        # Останавливаем таймер при закрытии окна
        if hasattr(self, 'token_check_timer'):
            self.token_check_timer.stop()
        event.accept()

    def import_passwords(self):
        """Импортирует пароли из CSV файла"""
        from PyQt6.QtWidgets import QFileDialog
        import csv
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите CSV файл для импорта",
            "",
            "CSV files (*.csv)"
        )
        
        if not file_path:
            return
            
        try:
            imported = 0
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Пропускаем заголовки
                
                for row in reader:
                    if len(row) >= 3:  # Проверяем наличие минимум 3 колонок
                        website = row[0]
                        account = row[1]
                        password = row[2]
                        
                        # Сохраняем пароль в базу
                        self.db.save_password(website, account, password, self.user_id)
                        imported += 1
            
            # Обновляем таблицу
            self.update_password_table()
            
            QMessageBox.information(
                self,
                "Успех",
                f"Импортировано {imported} паролей"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось импортировать пароли: {str(e)}"
            )
    
    def export_passwords(self):
        """Экспортирует пароли в CSV файл"""
        from PyQt6.QtWidgets import QFileDialog
        import csv
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить пароли",
            "passwords.csv",
            "CSV files (*.csv)"
        )
        
        if not file_path:
            return
            
        try:
            # Получаем все пароли пользователя
            passwords = self.db.get_all_passwords(self.user_id)
            
            with open(file_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                # Записываем заголовки
                writer.writerow(['url', 'username', 'password'])
                
                # Записываем пароли
                for password in passwords:
                    writer.writerow([
                        password[1],  # website
                        password[2],  # account
                        password[3]   # password
                    ])
            
            QMessageBox.information(
                self,
                "Успех",
                f"Пароли экспортированы в {file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось экспортировать пароли: {str(e)}"
            )

class PasswordDialog(QDialog):
    def __init__(self, parent=None, is_edit=False):
        super().__init__(parent)
        self.dragging = False
        self.drag_position = None
        self.setWindowTitle("Edit Password" if is_edit else "Add Password")
        self.setFixedSize(400, 300)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Основной layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Создаем белый фон с закругленными углами
        self.content = QWidget()
        self.content.setObjectName("dialogContent")
        content_shadow = QGraphicsDropShadowEffect(self.content)
        content_shadow.setBlurRadius(20)
        content_shadow.setOffset(0, 0)
        content_shadow.setColor(QColor(0, 0, 0, 80))
        self.content.setGraphicsEffect(content_shadow)
        content_layout = QVBoxLayout(self.content)
        
        # Заголовок
        title = QLabel("Edit Password" if is_edit else "Add New Password")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("dialogTitle")
        
        # Поля ввода
        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("Account")
        # Добавляем автодополнение для поля аккаунта с использованием ранее сохранённых значений и email
        parent_obj = self.parent()
        if parent_obj and hasattr(parent_obj, 'db') and hasattr(parent_obj, 'user_id'):
            # Получаем список сервисов из таблицы паролей
            accounts = [entry[1] for entry in parent_obj.db.get_all_passwords(parent_obj.user_id)]
            # Получаем список email из таблицы user_emails
            emails = [entry[1] for entry in parent_obj.db.get_user_emails(parent_obj.user_id)]
            # Объединяем оба списка и убираем дубликаты
            suggestions = list(set(accounts + emails))
            from PyQt6.QtWidgets import QCompleter
            completer = QCompleter(suggestions)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.account_edit.setCompleter(completer)
        
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        
        # Кнопка генерации пароля
        generate_btn = AnimatedButton("Generate")
        generate_btn.clicked.connect(self.generate_password)
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        save_btn = AnimatedButton("Save")
        cancel_btn = AnimatedButton("Cancel")
        
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        # Добавляем все элементы
        content_layout.addWidget(title)
        content_layout.addWidget(self.account_edit)
        content_layout.addWidget(self.password_edit)
        content_layout.addWidget(generate_btn)
        content_layout.addStretch()
        content_layout.addLayout(buttons_layout)
        
        layout.addWidget(self.content)

    def generate_password(self):
        """Генерирует пароль длиной минимум 16 символов с увеличенным количеством букв"""
        import string
        import random
        
        # Получаем базовый пароль пользователя
        base_password = self.db.get_base_password(self.user_id)
        
        # Определяем наборы символов
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = string.punctuation
        
        # Если есть базовый пароль, используем его как основу
        if base_password:
            password = base_password[:8]
            remaining_length = 16 - len(password)
        else:
            password = ""
            remaining_length = 16
        
        # Добавляем обязательные символы
        # Увеличиваем количество букв (по 3 каждого типа)
        for _ in range(3):
            password += random.choice(lowercase)
            password += random.choice(uppercase)
        
        # Добавляем как минимум 2 цифры
        password += random.choice(digits)
        password += random.choice(digits)
        
        # Добавляем как минимум 2 спецсимвола
        password += random.choice(special)
        password += random.choice(special)
        
        # Добавляем оставшиеся символы
        remaining = remaining_length - (len(password) - (8 if base_password else 0))
        if remaining > 0:
            all_chars = lowercase + uppercase + digits + special
            password += ''.join(random.choice(all_chars) for _ in range(remaining))
        
        # Перемешиваем все символы
        password_list = list(password)
        random.shuffle(password_list)
        password = ''.join(password_list)
        
        self.password_edit.setText(password)

    def get_values(self):
        return self.account_edit.text(), self.password_edit.text()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.drag_position = None
            event.accept()

    def center_in_parent(self):
        # Центрируем диалог относительно client area родительского окна, если оно задано
        parent = self.parentWidget()
        if parent:
            parent_center = parent.geometry().center()
        else:
            parent_center = QApplication.primaryScreen().availableGeometry().center()
        self_rect = self.frameGeometry()
        self_rect.moveCenter(parent_center)
        self.move(self_rect.topLeft())

    def exec(self):
        self.center_in_parent()
        return super().exec()

class AccountDialog(QDialog):
    def __init__(self, user_id, db, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.db = db
        self.setWindowTitle("Account Settings")
        self.setFixedSize(500, 400)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Контейнер с белым фоном и тенью
        self.content = QWidget()
        self.content.setObjectName("dialogContent")
        content_shadow = QGraphicsDropShadowEffect(self.content)
        content_shadow.setBlurRadius(20)
        content_shadow.setOffset(0, 0)
        content_shadow.setColor(QColor(0, 0, 0, 80))
        self.content.setGraphicsEffect(content_shadow)
        content_layout = QVBoxLayout(self.content)

        # Заголовок
        title_label = QLabel("Account Settings")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setObjectName("dialogTitle")

        # Поля редактирования: имя пользователя, основной email, новый пароль
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")

        self.primary_email_edit = QLineEdit()
        self.primary_email_edit.setPlaceholderText("Primary Email")

        self.new_password_edit = QLineEdit()
        self.new_password_edit.setPlaceholderText("New Password (leave empty to keep unchanged)")
        self.new_password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        # Таблица для дополнительных email
        self.additional_emails_list = QTableWidget()
        self.additional_emails_list.setColumnCount(2)
        self.additional_emails_list.setHorizontalHeaderLabels(["Email", "Action"])
        self.additional_emails_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.additional_emails_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.additional_emails_list.verticalHeader().setVisible(False)
        self.additional_emails_list.setShowGrid(False)
        self.additional_emails_list.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        # Поле ввода и кнопка для добавления нового дополнительного email
        self.new_additional_email_edit = QLineEdit()
        self.new_additional_email_edit.setPlaceholderText("Add additional email")
        add_email_btn = AnimatedButton("Add Email")
        add_email_btn.clicked.connect(self.add_email)

        add_email_layout = QHBoxLayout()
        add_email_layout.addWidget(self.new_additional_email_edit)
        add_email_layout.addWidget(add_email_btn)

        # Добавляем поле для базового пароля
        base_password_group = QGroupBox("Базовый пароль для генерации")
        base_password_layout = QVBoxLayout(base_password_group)
        
        self.base_password_edit = QLineEdit()
        self.base_password_edit.setPlaceholderText("Введите базовый пароль для генерации")
        self.base_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        base_password_info = QLabel("Этот пароль будет использоваться как основа для генерации новых паролей")
        base_password_info.setWordWrap(True)
        base_password_info.setStyleSheet("color: gray;")
        
        base_password_layout.addWidget(self.base_password_edit)
        base_password_layout.addWidget(base_password_info)
        
        content_layout.addWidget(base_password_group)

        # Загружаем информацию об аккаунте
        self.load_user_info()

        # Кнопки действий
        buttons_layout = QHBoxLayout()
        save_btn = AnimatedButton("Save")
        cancel_btn = AnimatedButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)

        # Собираем все элементы
        content_layout.addWidget(title_label)
        content_layout.addWidget(QLabel("Username:"))
        content_layout.addWidget(self.username_edit)
        content_layout.addWidget(QLabel("Primary Email:"))
        content_layout.addWidget(self.primary_email_edit)
        content_layout.addWidget(QLabel("New Password:"))
        content_layout.addWidget(self.new_password_edit)
        content_layout.addWidget(QLabel("Additional Emails:"))
        content_layout.addWidget(self.additional_emails_list)
        content_layout.addLayout(add_email_layout)

        ## Добавляем раздел для удаления аккаунта
        delete_group = QGroupBox("Удалить аккаунт")
        delete_group.setStyleSheet("QGroupBox { font-weight: bold; color: red; }")
        delete_layout = QVBoxLayout(delete_group)

        warning_label = QLabel("Внимание: учётная запись и все пароли будут удалены безвозвратно!")
        warning_label.setStyleSheet("color: red;")
        delete_layout.addWidget(warning_label)

        pwd_label = QLabel("Введите пароль для подтверждения:")
        self.delete_password_edit = QLineEdit()
        self.delete_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        delete_layout.addWidget(pwd_label)
        delete_layout.addWidget(self.delete_password_edit)

        delete_btn = AnimatedButton("Удалить аккаунт")
        delete_btn.setStyleSheet("background-color: red; color: white;")
        delete_btn.clicked.connect(self.delete_account_with_timer)
        delete_layout.addWidget(delete_btn)

        content_layout.addWidget(delete_group)

        layout.addWidget(self.content)

    def load_user_info(self):
        info = self.db.get_user_info(self.user_id)
        if info:
            username, email = info
            self.username_edit.setText(username)
            self.primary_email_edit.setText(email)
        # Загружаем дополнительные email (отличные от основного)
        emails = self.db.get_user_emails(self.user_id)
        additional = [e for e in emails if e[2] == 0]  # e[2] == 0 означает не основной email
        self.additional_emails_list.setRowCount(len(additional))
        for row, (email_id, email, is_primary) in enumerate(additional):
            email_item = QTableWidgetItem(email)
            self.additional_emails_list.setItem(row, 0, email_item)
            # Кнопка удаления для каждого email
            del_btn = AnimatedButton("Delete")
            del_btn.clicked.connect(lambda checked, eid=email_id: self.delete_email(eid))
            self.additional_emails_list.setCellWidget(row, 1, del_btn)
        base_password = self.db.get_base_password(self.user_id)
        if base_password:
            self.base_password_edit.setText(base_password)

    def add_email(self):
        email = self.new_additional_email_edit.text().strip()
        if email:
            success = self.db.add_additional_email(self.user_id, email)
            if success:
                self.load_user_info()
                self.new_additional_email_edit.clear()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Cannot add this email (it might already exist).")

    def delete_email(self, email_id):
        self.db.delete_additional_email(email_id)
        self.load_user_info()

    def accept(self):
        new_username = self.username_edit.text().strip()
        new_primary_email = self.primary_email_edit.text().strip()
        new_password = self.new_password_edit.text().strip()
        base_password = self.base_password_edit.text().strip()
        self.db.update_user_info(self.user_id, new_username, new_primary_email, new_password)
        self.db.update_base_password(self.user_id, base_password)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Success", "Account updated!")
        self.close()

    def delete_account_with_timer(self):
        from PyQt6.QtWidgets import QMessageBox
        import hashlib, sqlite3
        pwd = self.delete_password_edit.text().strip()
        if not pwd:
            QMessageBox.warning(self, "Ошибка", "Введите пароль для подтверждения удаления аккаунта.")
            return
        hashed = hashlib.sha256(pwd.encode()).hexdigest()
        with sqlite3.connect('passwords.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password FROM users WHERE id=?", (self.user_id,))
            row = cursor.fetchone()
        if not row or row[0] != hashed:
            QMessageBox.warning(self, "Ошибка", "Неверный пароль.")
            return

        # Открываем диалоговое окно с отсчетом времени для отмены удаления
        confirm_dialog = DeleteAccountConfirmDialog(self, countdown=10)
        result = confirm_dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            with sqlite3.connect('passwords.db') as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id=?", (self.user_id,))
                cursor.execute("DELETE FROM user_emails WHERE user_id=?", (self.user_id,))
                cursor.execute("DELETE FROM passwords WHERE user_id=?", (self.user_id,))
                conn.commit()
            QMessageBox.information(self, "Аккаунт удалён", "Ваш аккаунт и все данные удалены безвозвратно.")
            self.close()
            if self.parent():
                self.parent().close()
        else:
            QMessageBox.information(self, "Отмена", "Удаление аккаунта отменено.")

    def showEvent(self, event):
        # Центрируем окно относительно родителя
        if self.parent():
            parent_rect = self.parent().frameGeometry()
            self_rect = self.frameGeometry()
            self_rect.moveCenter(parent_rect.center())
            self.move(self_rect.topLeft())
        super().showEvent(event)

class UserCabinetWindow(QMainWindow):
    def __init__(self, user_id, db, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.db = db
        self.usb_token = USBToken()
        self.setWindowTitle("User Cabinet")
        self.setMinimumSize(600, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Заголовок страницы
        title_label = QLabel("User Cabinet")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Форма редактирования: имя, основной email, новый пароль
        form_layout = QVBoxLayout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")

        self.primary_email_edit = QLineEdit()
        self.primary_email_edit.setPlaceholderText("Primary Email")

        self.new_password_edit = QLineEdit()
        self.new_password_edit.setPlaceholderText("New Password (leave empty to keep unchanged)")
        self.new_password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form_layout.addWidget(QLabel("Username:"))
        form_layout.addWidget(self.username_edit)
        form_layout.addWidget(QLabel("Primary Email:"))
        form_layout.addWidget(self.primary_email_edit)
        form_layout.addWidget(QLabel("New Password:"))
        form_layout.addWidget(self.new_password_edit)

        # Добавляем поле для базового пароля
        base_password_group = QGroupBox("Базовый пароль для генерации")
        base_password_layout = QVBoxLayout(base_password_group)
        
        self.base_password_edit = QLineEdit()
        self.base_password_edit.setPlaceholderText("Введите базовый пароль для генерации")
        self.base_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        base_password_info = QLabel("Этот пароль будет использоваться как основа для генерации новых паролей")
        base_password_info.setWordWrap(True)
        base_password_info.setStyleSheet("color: gray;")
        
        base_password_layout.addWidget(self.base_password_edit)
        base_password_layout.addWidget(base_password_info)
        
        form_layout.addWidget(base_password_group)

        # Таблица для дополнительных email
        self.additional_emails_table = QTableWidget()
        self.additional_emails_table.setColumnCount(2)
        self.additional_emails_table.setHorizontalHeaderLabels(["Email", "Action"])
        self.additional_emails_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.additional_emails_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.additional_emails_table.verticalHeader().setVisible(False)
        self.additional_emails_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        form_layout.addWidget(QLabel("Additional Emails:"))
        form_layout.addWidget(self.additional_emails_table)

        # Поле для добавления нового дополнительного email
        add_email_layout = QHBoxLayout()
        self.new_additional_email_edit = QLineEdit()
        self.new_additional_email_edit.setPlaceholderText("Add additional email")
        add_email_btn = AnimatedButton("Add Email")
        add_email_btn.clicked.connect(self.add_email)
        add_email_layout.addWidget(self.new_additional_email_edit)
        add_email_layout.addWidget(add_email_btn)
        form_layout.addLayout(add_email_layout)

        layout.addLayout(form_layout)

        # Добавляем группу для управления USB-токеном
        token_group = QGroupBox("USB Token Management")
        token_layout = QVBoxLayout(token_group)
        
        # Статус токена
        self.token_status_label = QLabel()
        self.token_status_label.setWordWrap(True)
        
        # Кнопки управления токеном
        token_buttons_layout = QHBoxLayout()
        
        self.toggle_token_btn = AnimatedButton()
        self.toggle_token_btn.clicked.connect(self.toggle_token)
        
        self.register_new_token_btn = AnimatedButton("Register New Token")
        self.register_new_token_btn.clicked.connect(self.register_new_token)
        self.register_new_token_btn.setVisible(False)  # Показываем только если токен уже включен
        
        token_buttons_layout.addWidget(self.toggle_token_btn)
        token_buttons_layout.addWidget(self.register_new_token_btn)
        
        token_layout.addWidget(self.token_status_label)
        token_layout.addLayout(token_buttons_layout)
        
        layout.addWidget(token_group)

        # Добавляем кнопку удаления аккаунта
        delete_account_btn = AnimatedButton("Удалить аккаунт")
        delete_account_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f8ef7;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #1e90ff;
            }
        """)
        delete_account_btn.clicked.connect(self.delete_account)
        layout.addWidget(delete_account_btn)

        # Кнопки действий
        buttons_layout = QHBoxLayout()
        save_btn = AnimatedButton("Save")
        cancel_btn = AnimatedButton("Cancel")
        save_btn.clicked.connect(self.save_info)
        cancel_btn.clicked.connect(self.close)
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

        self.load_user_info()

    def load_user_info(self):
        info = self.db.get_user_info(self.user_id)
        if info:
            username, email = info
            self.username_edit.setText(username)
            self.primary_email_edit.setText(email)
        emails = self.db.get_user_emails(self.user_id)
        additional = [e for e in emails if e[2] == 0]  # is_primary==0 означает дополнительные email
        self.additional_emails_table.setRowCount(len(additional))
        for row, (email_id, email, is_primary) in enumerate(additional):
            email_item = QTableWidgetItem(email)
            self.additional_emails_table.setItem(row, 0, email_item)
            del_btn = AnimatedButton("Delete")
            del_btn.clicked.connect(lambda checked, eid=email_id: self.delete_email(eid))
            self.additional_emails_table.setCellWidget(row, 1, del_btn)
        base_password = self.db.get_base_password(self.user_id)
        if base_password:
            self.base_password_edit.setText(base_password)
        
        # Обновляем информацию о токене
        self.update_token_status()

    def update_token_status(self):
        requires_token = self.db.user_requires_token(self.user_id)
        if requires_token:
            self.token_status_label.setText(
                "USB Token protection is enabled.\n"
                "Token is required to access your account."
            )
            self.toggle_token_btn.setText("Disable Token")
            self.register_new_token_btn.setVisible(True)
        else:
            self.token_status_label.setText(
                "USB Token protection is disabled.\n"
                "Enable it to add an extra layer of security."
            )
            self.toggle_token_btn.setText("Enable Token")
            self.register_new_token_btn.setVisible(False)

    def toggle_token(self):
        requires_token = self.db.user_requires_token(self.user_id)
        
        if requires_token:
            # Отключаем токен
            reply = QMessageBox.warning(
                self,
                "Disable Token",
                "Are you sure you want to disable USB token protection?\n"
                "This will make your account less secure.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Удаляем токен из списка авторизованных
                self.usb_token.remove_token()
                # Обновляем статус в БД
                self.db.update_token_requirement(self.user_id, False)
                QMessageBox.information(self, "Success", "USB token protection disabled.")
        else:
            # Включаем токен
            if not self.usb_token.get_usb_token_hash():
                QMessageBox.warning(self, "Error", "No USB device detected! Please insert a USB drive.")
                return
            
            token_dialog = USBTokenRegistrationDialog(self, self.db, self.user_id)
            if token_dialog.exec() == QDialog.DialogCode.Accepted:
                # Регистрируем токен
                self.usb_token.register_token()
                # Обновляем статус в БД
                self.db.update_token_requirement(self.user_id, True)
                QMessageBox.information(self, "Success", "USB token protection enabled.")
        
        self.update_token_status()

    def register_new_token(self):
        if not self.usb_token.get_usb_token_hash():
            QMessageBox.warning(self, "Error", "No USB device detected! Please insert a USB drive.")
            return
        
        reply = QMessageBox.question(
            self,
            "Register New Token",
            "Are you sure you want to register a new token?\n"
            "The old token will be deactivated.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            token_dialog = USBTokenRegistrationDialog(self, self.db, self.user_id)
            if token_dialog.exec() == QDialog.DialogCode.Accepted:
                # Удаляем старый токен и регистрируем новый
                self.usb_token.remove_token()
                self.usb_token.register_token()
                QMessageBox.information(self, "Success", "New USB token registered successfully.")

    def add_email(self):
        email = self.new_additional_email_edit.text().strip()
        if email:
            success = self.db.add_additional_email(self.user_id, email)
            if success:
                self.load_user_info()
                self.new_additional_email_edit.clear()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Cannot add this email (it might already exist).")

    def delete_email(self, email_id):
        self.db.delete_additional_email(email_id)
        self.load_user_info()

    def save_info(self):
        new_username = self.username_edit.text().strip()
        new_primary_email = self.primary_email_edit.text().strip()
        new_password = self.new_password_edit.text().strip()
        base_password = self.base_password_edit.text().strip()
        
        if not validate_email(new_primary_email):
            QMessageBox.warning(self, "Error", "Please enter a valid primary email address!")
            return
        
        self.db.update_user_info(self.user_id, new_username, new_primary_email, new_password)
        self.db.update_base_password(self.user_id, base_password)
        QMessageBox.information(self, "Success", "Account updated!")
        self.close()

    def delete_account(self):
        # Запрашиваем подтверждение
        reply = QMessageBox.warning(
            self,
            "Удаление аккаунта",
            "Вы уверены, что хотите удалить аккаунт?\nЭто действие нельзя отменить!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Запрашиваем пароль
            password, ok = QInputDialog.getText(
                self,
                "Подтверждение",
                "Введите пароль для подтверждения удаления:",
                QLineEdit.EchoMode.Password
            )
            
            if ok and password:
                # Проверяем пароль
                hashed = hashlib.sha256(password.encode()).hexdigest()
                with sqlite3.connect('passwords.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT password FROM users WHERE id=?", (self.user_id,))
                    row = cursor.fetchone()
                
                if not row or row[0] != hashed:
                    QMessageBox.warning(self, "Ошибка", "Неверный пароль!")
                    return
                
                # Показываем диалог с обратным отсчетом
                confirm_dialog = DeleteAccountConfirmDialog(self)
                if confirm_dialog.exec() == QDialog.DialogCode.Accepted:
                    try:
                        # Удаляем токен и аккаунт
                        if self.db.user_requires_token(self.user_id):
                            self.usb_token.remove_token()
                        self.db.delete_user(self.user_id)
                        
                        QMessageBox.information(self, "Успех", "Аккаунт успешно удален")
                        
                        # Закрываем все окна
                        QApplication.closeAllWindows()
                        
                        # Создаем новое окно входа
                        login_window = LoginWindow()
                        login_window.show()
                        
                    except Exception as e:
                        QMessageBox.critical(self, "Ошибка", f"Не удалось удалить аккаунт: {str(e)}")

    def closeEvent(self, event):
        # Останавливаем таймер при закрытии окна
        if hasattr(self, 'token_check_timer'):
            self.token_check_timer.stop()
        event.accept()

class PasswordWindow(QWidget):
    def __init__(self, user_id, db, parent=None, is_edit=False, password_id=None, website="", account="", password=""):
        super().__init__(parent, flags=Qt.WindowType.Window)
        self.user_id = user_id
        self.db = db
        self.is_edit = is_edit
        self.password_id = password_id
        self.setWindowTitle("Edit Password" if is_edit else "Add New Password")
        self.setFixedSize(400, 350)
        self.setup_ui(website, account, password)
    
    def setup_ui(self, website, account, password):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Поле для ввода ссылки на сайт
        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("Website")
        if website:
            self.website_edit.setText(website)
        
        # Поле ввода аккаунта с автодополнением
        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("Account")
        if account:
            self.account_edit.setText(account)
        # Автодополнение: объединяем значения из таблицы паролей и дополнительные email
        parent_obj = self.parent()
        if parent_obj and hasattr(parent_obj, 'db') and hasattr(parent_obj, 'user_id'):
            accounts = [entry[1] for entry in parent_obj.db.get_all_passwords(parent_obj.user_id)]
            emails = [entry[1] for entry in parent_obj.db.get_user_emails(parent_obj.user_id)]
            suggestions = list(set(accounts + emails))
            from PyQt6.QtWidgets import QCompleter
            completer = QCompleter(suggestions)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.account_edit.setCompleter(completer)
        
        # Поле ввода пароля
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        if password:
            self.password_edit.setText(password)
        
        # Кнопка генерации пароля
        generate_btn = AnimatedButton("Generate")
        generate_btn.clicked.connect(self.generate_password)
        
        # Кнопки Save и Cancel
        buttons_layout = QHBoxLayout()
        save_btn = AnimatedButton("Save")
        cancel_btn = AnimatedButton("Cancel")
        save_btn.clicked.connect(self.save_password)
        cancel_btn.clicked.connect(self.close)
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        # Собираем элементы в layout
        layout.addWidget(QLabel("Website:"))
        layout.addWidget(self.website_edit)
        layout.addWidget(QLabel("Account:"))
        layout.addWidget(self.account_edit)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self.password_edit)
        layout.addWidget(generate_btn)
        layout.addStretch()
        layout.addLayout(buttons_layout)
        
        self.center_in_parent()
    
    def center_in_parent(self):
        parent = self.parentWidget()
        if parent:
            center = parent.geometry().center()
        else:
            center = QApplication.primaryScreen().availableGeometry().center()
        rect = self.frameGeometry()
        rect.moveCenter(center)
        self.move(rect.topLeft())
    
    def generate_password(self):
        """Генерирует пароль длиной минимум 16 символов с увеличенным количеством букв"""
        import string
        import random
        
        # Получаем базовый пароль пользователя
        base_password = self.db.get_base_password(self.user_id)
        
        # Определяем наборы символов
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = string.punctuation
        
        # Если есть базовый пароль, используем его как основу
        if base_password:
            password = base_password[:8]
            remaining_length = 16 - len(password)
        else:
            password = ""
            remaining_length = 16
        
        # Добавляем обязательные символы
        # Увеличиваем количество букв (по 3 каждого типа)
        for _ in range(3):
            password += random.choice(lowercase)
            password += random.choice(uppercase)
        
        # Добавляем как минимум 2 цифры
        password += random.choice(digits)
        password += random.choice(digits)
        
        # Добавляем как минимум 2 спецсимвола
        password += random.choice(special)
        password += random.choice(special)
        
        # Добавляем оставшиеся символы
        remaining = remaining_length - (len(password) - (8 if base_password else 0))
        if remaining > 0:
            all_chars = lowercase + uppercase + digits + special
            password += ''.join(random.choice(all_chars) for _ in range(remaining))
        
        # Перемешиваем все символы
        password_list = list(password)
        random.shuffle(password_list)
        password = ''.join(password_list)
        
        self.password_edit.setText(password)
    
    def save_password(self):
        website = self.website_edit.text().strip()
        account = self.account_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not website or not account or not password:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "All fields are required.")
            return
        
        if len(password) < 16:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Password must be at least 16 characters long.")
            return
        
        if self.is_edit:
            self.db.update_password(self.password_id, website, account, password, self.user_id)
        else:
            self.db.save_password(website, account, password, self.user_id)
        
        # Копируем пароль в буфер обмена
        QApplication.clipboard().setText(password)
        
        # Показываем уведомление
        self.show_notification()
    
    def show_notification(self):
        # Создаем накладывающуюся метку для уведомления
        self.notification_label = QLabel("Пароль скопирован!", self)
        self.notification_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_label.setStyleSheet("background-color: rgba(0, 0, 0, 0.6); color: white; padding: 5px; border-radius: 5px;")
        # Располагаем метку по центру окна
        w = self.width()
        h = self.height()
        label_width = 200
        label_height = 40
        self.notification_label.setGeometry((w - label_width) // 2, (h - label_height) // 2, label_width, label_height)
        self.notification_label.show()
        
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        from PyQt6.QtCore import QPropertyAnimation
        effect = QGraphicsOpacityEffect(self.notification_label)
        self.notification_label.setGraphicsEffect(effect)
        self._notification_animation = QPropertyAnimation(effect, b"opacity")
        self._notification_animation.setDuration(1500)  # Длительность анимации 1.5 сек.
        self._notification_animation.setStartValue(1)
        self._notification_animation.setEndValue(0)
        self._notification_animation.finished.connect(self.cleanup_notification)
        self._notification_animation.start()
    
    def cleanup_notification(self):
        if self.parent():
            self.parent().update_password_table()
        self.close()

    def closeEvent(self, event):
        if self.parent():
            self.parent().centralWidget().setGraphicsEffect(None)
        event.accept()

class DeleteAccountConfirmDialog(QDialog):
    def __init__(self, parent=None, countdown=10):
        super().__init__(parent)
        self.countdown = countdown
        self.setWindowTitle("Подтверждение удаления аккаунта")
        self.setFixedSize(300, 150)
        layout = QVBoxLayout(self)
        self.label = QLabel(f"Учётная запись будет удалена через {self.countdown} секунд.\nНажмите 'Отменить', чтобы остановить удаление.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.cancel_button = AnimatedButton("Отменить удаление")
        self.cancel_button.clicked.connect(self.cancel)
        layout.addWidget(self.cancel_button)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

    def tick(self):
        self.countdown -= 1
        if self.countdown <= 0:
            self.timer.stop()
            self.accept()
        else:
            self.label.setText(f"Учётная запись будет удалена через {self.countdown} секунд.\nНажмите 'Отменить', чтобы остановить удаление.")

    def cancel(self):
        self.timer.stop()
        self.reject()

class USBTokenRegistrationDialog(QDialog):
    def __init__(self, parent, db, user_id):
        super().__init__(parent)
        self.db = db
        self.user_id = user_id
        self.setWindowTitle("USB Token Registration")
        self.setFixedSize(400, 300)
        self.token_manager = None  # Добавляем атрибут для хранения окна управления токеном
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Иконка USB
        icon_label = QLabel("🔒")
        icon_label.setFont(QFont("Segoe UI", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Информационный текст
        info_text = QLabel(
            "You are about to register a USB device as a security token.\n\n"
            "This USB drive will be required to:\n"
            "• Log into your account\n"
            "• Access your passwords\n"
            "• Perform security-sensitive operations\n\n"
            "Please make sure to:\n"
            "• Keep this USB drive safe\n"
            "• Create a backup token\n"
            "• Don't use it for other purposes"
        )
        info_text.setWordWrap(True)
        info_text.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Чекбокс подтверждения
        self.confirm_checkbox = QCheckBox(
            "I understand that losing this USB token will prevent access to my account"
        )
        
        # Кнопки
        button_layout = QHBoxLayout()
        self.register_btn = AnimatedButton("Register Token")
        self.register_btn.clicked.connect(self.show_token_manager)  # Меняем обработчик
        self.register_btn.setEnabled(False)
        cancel_btn = AnimatedButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.register_btn)
        button_layout.addWidget(cancel_btn)
        
        # Подключаем чекбокс к кнопке регистрации
        self.confirm_checkbox.stateChanged.connect(
            lambda state: self.register_btn.setEnabled(state == Qt.CheckState.Checked.value)
        )
        
        # Добавляем все элементы в layout
        layout.addWidget(icon_label)
        layout.addWidget(info_text)
        layout.addWidget(self.confirm_checkbox)
        layout.addLayout(button_layout)

    def show_token_manager(self):
        """Открывает окно управления токеном"""
        from manage_token import TokenManagerWindow
        self.token_manager = TokenManagerWindow(self.db, self.user_id)
        if self.token_manager.exec() == QDialog.DialogCode.Accepted:
            self.accept()
            # Находим главное окно
            main_window = self.parent()
            while not isinstance(main_window, LoginWindow) and main_window is not None:
                main_window = main_window.parent()
            
            # Если нашли главное окно, показываем список аккаунтов
            if main_window is not None:
                main_window.show_accounts_list()
        else:
            self.reject()

def validate_email(email: str) -> bool:
    """
    Validates email address format.
    Args:
        email: Email address to validate
    Returns:
        bool: True if email is valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def generate_secure_password(base_password: Optional[str] = None) -> str:
    """
    Generates a secure password with specified requirements.
    Args:
        base_password: Optional base password to use as a starting point
    Returns:
        str: Generated password
    """
    password = base_password[:8] if base_password else ""
    remaining_length = MIN_PASSWORD_LENGTH - len(password)
    
    # Add required character types
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = string.punctuation
    
    # Add multiple letters for better readability
    for _ in range(3):
        password += random.choice(lowercase)
        password += random.choice(uppercase)
    
    # Add numbers and special characters
    password += random.choice(digits) * 2
    password += random.choice(special) * 2
    
    # Fill remaining length with random characters
    all_chars = lowercase + uppercase + digits + special
    remaining = remaining_length - (len(password) - (8 if base_password else 0))
    if remaining > 0:
        password += ''.join(random.choice(all_chars) for _ in range(remaining))
    
    # Shuffle the password
    password_list = list(password)
    random.shuffle(password_list)
    return ''.join(password_list)

if __name__ == '__main__':
    import sys
    
    app = QApplication(sys.argv)
    
    # Проверяем, запущены ли мы для создания токена
    if len(sys.argv) > 1 and sys.argv[1] == '--create-token':
        try:
            # Загружаем сохраненные параметры
            import pickle
            with open('token_params.tmp', 'rb') as f:
                drive_letter, backup_data = pickle.load(f)
            os.remove('token_params.tmp')  # Удаляем временный файл
            
            # Создаем токен
            creator = BootableTokenCreator()
            creator.create_bootable_token(drive_letter, backup_data)
            
            # Показываем сообщение об успехе
            QMessageBox.information(None, "Успех", "Загрузочный токен успешно создан!")
            
        except Exception as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось создать токен: {str(e)}")
        finally:
            sys.exit(0)
    
    # Обычный запуск программы
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
