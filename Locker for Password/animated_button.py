from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor

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