from cryptography.fernet import Fernet
import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel, QLineEdit, QHBoxLayout, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor, QFont
from animated_button import AnimatedButton

class PasswordEncryption:
    def __init__(self):
        self.load_key()

    def load_key(self):
        if not os.path.exists('key.key'):
            self.key = Fernet.generate_key()
            with open('key.key', 'wb') as key_file:
                key_file.write(self.key)
        else:
            with open('key.key', 'rb') as key_file:
                self.key = key_file.read()
        self.fernet = Fernet(self.key)

    def encrypt_password(self, password):
        return self.fernet.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted_password):
        return self.fernet.decrypt(encrypted_password.encode()).decode()

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

    def showEvent(self, event):
        # Центрируем диалог относительно родительского окна, активного окна или экрана
        parent = self.parent() if self.parent() is not None else QApplication.activeWindow()
        if parent:
            parent_center = parent.frameGeometry().center()
            self.move(parent_center.x() - self.width() // 2, parent_center.y() - self.height() // 2)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            center_point = screen.center()
            self.move(center_point.x() - self.width() // 2, center_point.y() - self.height() // 2)
        super().showEvent(event) 