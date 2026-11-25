"""
Екрани входу: email → OTP → згода.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.mailer import MailerError, send_email
from core.ui_kit import align_center, brand_row, centered_card, divider, field
from core.otp import OtpDenied, OtpInvalid, OtpSendLimit, OtpService

logger = logging.getLogger(__name__)


class EmailScreen(QWidget):
    """Екран 1: введення корпоративної пошти."""

    def __init__(
        self,
        otp: OtpService,
        config: dict[str, Any],
        on_code_sent: Callable[[str, dict], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.otp = otp
        self.config = config
        self.on_code_sent = on_code_sent

        card, lay = centered_card(self, max_width=480)
        lay.addWidget(brand_row("logo-client.svg", 44))
        lay.addSpacing(8)

        title = align_center(QLabel("Вхід до тесту"))
        title.setObjectName("titleLabel")
        lay.addWidget(title)
        hint = align_center(QLabel("Введіть корпоративну пошту, на яку надійде одноразовий код."))
        hint.setObjectName("subtitleLabel")
        lay.addWidget(hint)
        lay.addSpacing(4)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("name@company.com")
        self.email_edit.setMinimumHeight(48)
        self.email_edit.returnPressed.connect(self._submit)
        lay.addWidget(field("Корпоративна пошта", self.email_edit))

        self.btn = QPushButton("Отримати код")
        self.btn.setObjectName("primaryButton")
        self.btn.setMinimumHeight(48)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._submit)
        lay.addWidget(self.btn)

        self.status = align_center(QLabel(""))
        self.status.setObjectName("subtitleLabel")
        lay.addWidget(self.status)
        self.email_edit.setFocus()

    def _submit(self) -> None:
        email = self.email_edit.text().strip()
        if not email:
            self.status.setText("Введіть адресу електронної пошти.")
            return

        self.btn.setEnabled(False)
        self.status.setText("Надсилаємо код…")
        try:
            code, student = self.otp.request_code(email)
        except OtpDenied as exc:
            # Нейтральне повідомлення — без деталей
            msg = str(exc)
            if "використано" in msg.lower():
                self.status.setText(msg)
            else:
                self.status.setText("Доступ не надано. Зверніться до адміністратора.")
            self.btn.setEnabled(True)
            return
        except OtpSendLimit as exc:
            self.status.setText(str(exc))
            self.btn.setEnabled(True)
            return
        except Exception as exc:
            logger.exception("Помилка генерації OTP")
            self.status.setText("Сталася помилка. Спробуйте пізніше.")
            self.btn.setEnabled(True)
            return

        # Відправка листа
        try:
            self._send_otp_email(email, code)
        except MailerError as exc:
            logger.error("Не вдалося надіслати OTP: %s", exc)
            self.status.setText(
                "Не вдалося надіслати код. Перевірте з'єднання або зверніться до адміністратора."
            )
            self.btn.setEnabled(True)
            return
        except Exception as exc:
            logger.exception("Неочікувана помилка відправки OTP")
            self.status.setText(
                "Не вдалося надіслати код. Перевірте з'єднання або зверніться до адміністратора."
            )
            self.btn.setEnabled(True)
            return

        self.btn.setEnabled(True)
        self.on_code_sent(email, student)

    def _send_otp_email(self, email: str, code: str) -> None:
        org = (self.config.get("organization") or {}).get("name") or "SecureTest"
        ttl = self.otp.ttl_minutes
        subject = f"[{org}] Код для входу до тесту"
        body = (
            f"Ваш одноразовий код для входу: {code}\n\n"
            f"Код дійсний {ttl} хв.\n"
            f"Нікому не повідомляйте цей код.\n\n"
            f"— {org}"
        )
        send_email(self.config, email, subject, body)


class CodeScreen(QWidget):
    """Екран 2: введення коду з листа."""

    def __init__(
        self,
        otp: OtpService,
        config: dict[str, Any],
        email: str,
        student: dict,
        on_success: Callable[[dict], None],
        on_back: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.otp = otp
        self.config = config
        self.email = email
        self.student = student
        self.on_success = on_success
        self.on_back = on_back

        card, lay = centered_card(self, max_width=480)
        lay.addWidget(brand_row("logo-client.svg", 44))
        lay.addSpacing(8)

        title = align_center(QLabel("Код із листа"))
        title.setObjectName("titleLabel")
        lay.addWidget(title)
        hint = align_center(QLabel(f"Код надіслано на\n{email}"))
        hint.setObjectName("subtitleLabel")
        lay.addWidget(hint)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("000000")
        self.code_edit.setMaxLength(6)
        self.code_edit.setMinimumHeight(56)
        self.code_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_edit.setObjectName("codeInput")
        self.code_edit.returnPressed.connect(self._submit)
        lay.addWidget(self.code_edit)

        self.btn_login = QPushButton("Увійти")
        self.btn_login.setObjectName("primaryButton")
        self.btn_login.setMinimumHeight(48)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self._submit)
        lay.addWidget(self.btn_login)

        # Другорядні дії в одному рядку, що ділить ширину порівну
        sec = QHBoxLayout()
        sec.setSpacing(12)
        self.btn_back = QPushButton("← Інша пошта")
        self.btn_back.setMinimumHeight(42)
        self.btn_back.clicked.connect(self.on_back)
        self.btn_resend = QPushButton("Надіслати код повторно")
        self.btn_resend.setMinimumHeight(42)
        self.btn_resend.clicked.connect(self._resend)
        sec.addWidget(self.btn_back, 1)
        sec.addWidget(self.btn_resend, 1)
        lay.addLayout(sec)

        self.status = align_center(QLabel(""))
        self.status.setObjectName("subtitleLabel")
        lay.addWidget(self.status)
        self.code_edit.setFocus()

        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.timeout.connect(self._tick_cooldown)
        self._update_resend_btn()

    def _submit(self) -> None:
        code = self.code_edit.text().strip()
        try:
            student = self.otp.verify_code(self.email, code)
        except OtpInvalid as exc:
            self.status.setText(str(exc))
            return
        except OtpDenied as exc:
            self.status.setText(str(exc))
            return
        except Exception:
            logger.exception("Помилка перевірки OTP")
            self.status.setText("Сталася помилка. Спробуйте пізніше.")
            return
        self.on_success(student)

    def _resend(self) -> None:
        left = self.otp.seconds_until_resend_allowed(self.email)
        if left > 0:
            self.status.setText(f"Повторна відправка через {left} с.")
            return
        try:
            code, student = self.otp.request_code(self.email)
            self.student = student
        except (OtpDenied, OtpSendLimit) as exc:
            self.status.setText(str(exc))
            return
        except Exception:
            logger.exception("Помилка повторної генерації OTP")
            self.status.setText("Сталася помилка.")
            return

        try:
            org = (self.config.get("organization") or {}).get("name") or "SecureTest"
            ttl = self.otp.ttl_minutes
            subject = f"[{org}] Код для входу до тесту"
            body = (
                f"Ваш одноразовий код для входу: {code}\n\n"
                f"Код дійсний {ttl} хв.\n"
                f"Нікому не повідомляйте цей код.\n\n"
                f"— {org}"
            )
            send_email(self.config, self.email, subject, body)
            self.status.setText("Новий код надіслано.")
        except Exception as exc:
            logger.error("Не вдалося надіслати OTP повторно: %s", exc)
            self.status.setText(
                "Не вдалося надіслати код. Перевірте з'єднання або зверніться до адміністратора."
            )
            return
        self._update_resend_btn()

    def _update_resend_btn(self) -> None:
        left = self.otp.seconds_until_resend_allowed(self.email)
        if left > 0:
            self.btn_resend.setEnabled(False)
            self.btn_resend.setText(f"Повторно через {left} с")
            self._cooldown_timer.start(1000)
        else:
            self.btn_resend.setEnabled(True)
            self.btn_resend.setText("Надіслати код повторно")
            self._cooldown_timer.stop()

    def _tick_cooldown(self) -> None:
        self._update_resend_btn()


class ConsentScreen(QWidget):
    """Екран згоди перед початком тесту."""

    def __init__(
        self,
        student: dict,
        test_title: str,
        on_agree: Callable[[], None],
        on_cancel: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        card, lay = centered_card(self, max_width=720, min_width=320)
        lay.setSpacing(18)
        lay.addWidget(brand_row("logo-client.svg", 40))

        title = align_center(QLabel("Перед початком"))
        title.setObjectName("titleLabel")
        lay.addWidget(title)

        # Хто і який тест — дві «плашки», що переходять в колонку на вузькому вікні
        info = QGridLayout()
        info.setSpacing(12)
        for col, (cap, val) in enumerate(
            (("Учасник", student.get("full_name", "")), ("Тест", test_title))
        ):
            box = QFrame()
            box.setObjectName("statCard")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(16, 10, 16, 10)
            bl.setSpacing(2)
            c = QLabel(cap)
            c.setObjectName("fieldLabel")
            v = QLabel(val)
            v.setObjectName("sectionLabel")
            v.setWordWrap(True)
            bl.addWidget(c)
            bl.addWidget(v)
            info.addWidget(box, 0, col)
            info.setColumnStretch(col, 1)
        lay.addLayout(info)

        # Правила — у скролі, щоб на малих екранах кнопки завжди були видимі
        intro = QLabel("Під час тесту ведеться запис екрана та журнал дій.")
        intro.setObjectName("bodyLabel")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        rules_box = QWidget()
        rl = QVBoxLayout(rules_box)
        rl.setContentsMargins(0, 0, 8, 0)
        rl.setSpacing(12)
        cap = QLabel("Заборонено")
        cap.setObjectName("sectionLabel")
        rl.addWidget(cap)
        for text in (
            "перемикатися на інші вікна та програми;",
            "використовувати сторонні засоби віддаленого доступу;",
            "фотографувати або копіювати завдання.",
        ):
            row = QHBoxLayout()
            row.setSpacing(12)
            ico = QLabel("✕")
            ico.setObjectName("ruleIcon")
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(text)
            lbl.setObjectName("bodyLabel")
            lbl.setWordWrap(True)
            row.addWidget(ico, alignment=Qt.AlignmentFlag.AlignTop)
            row.addWidget(lbl, 1)
            rl.addLayout(row)
        note = QLabel(
            "Порушення правил може призвести до блокування спроби. "
            "Натискаючи «Погоджуюсь і почати», ви підтверджуєте ознайомлення з умовами "
            "та даєте згоду на моніторинг."
        )
        note.setObjectName("subtitleLabel")
        note.setWordWrap(True)
        rl.addSpacing(4)
        rl.addWidget(note)
        rl.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(rules_box)
        lay.addWidget(scroll, 1)

        lay.addWidget(divider())
        btns = QHBoxLayout()
        btns.setSpacing(12)
        btn_cancel = QPushButton("Скасувати")
        btn_cancel.setMinimumHeight(48)
        btn_cancel.setMinimumWidth(140)
        btn_cancel.clicked.connect(on_cancel)
        btn_ok = QPushButton("Погоджуюсь і почати")
        btn_ok.setObjectName("primaryButton")
        btn_ok.setMinimumHeight(48)
        btn_ok.setMinimumWidth(220)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(on_agree)
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)
