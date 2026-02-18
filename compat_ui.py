import platform
import threading


def _is_ui_thread():
    return threading.current_thread() is threading.main_thread()


def _get_qt_app():
    try:
        from PyQt5.QtWidgets import QApplication
        return QApplication.instance()
    except Exception:
        return None


def _can_show_qt_dialog():
    return _is_ui_thread() and _get_qt_app() is not None


def _in_background_thread():
    return threading.current_thread() is not threading.main_thread()


def _should_avoid_pyautogui():
    return platform.system() == 'Darwin' and _in_background_thread()


def alert(text='', title='Alert', button='OK'):
    if _can_show_qt_dialog():
        try:
            from PyQt5.QtWidgets import QMessageBox
            message_box = QMessageBox()
            message_box.setWindowTitle(title)
            message_box.setText(text)
            message_box.setIcon(QMessageBox.Information)
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.exec_()
            return button
        except Exception:
            pass
    if _should_avoid_pyautogui():
        print('[ALERT][{}] {}'.format(title, text))
        return button
    try:
        from pyautogui import alert as pg_alert
        return pg_alert(text=text, title=title, button=button)
    except Exception:
        print('[ALERT][{}] {}'.format(title, text))
        return button


def confirm(text='', title='Confirmation', buttons=None):
    if buttons is None:
        buttons = ['OK', 'Cancel']
    if _can_show_qt_dialog():
        try:
            from PyQt5.QtWidgets import QMessageBox
            button_map = {
                'OK': QMessageBox.Ok,
                'Cancel': QMessageBox.Cancel,
                'Yes': QMessageBox.Yes,
                'No': QMessageBox.No,
                'Close': QMessageBox.Close,
            }
            standard_buttons = QMessageBox.NoButton
            for label in buttons:
                standard_buttons |= button_map.get(label, QMessageBox.NoButton)
            if standard_buttons == QMessageBox.NoButton:
                standard_buttons = QMessageBox.Ok | QMessageBox.Cancel

            message_box = QMessageBox()
            message_box.setWindowTitle(title)
            message_box.setText(text)
            message_box.setIcon(QMessageBox.Question)
            message_box.setStandardButtons(standard_buttons)
            result = message_box.exec_()

            reverse_map = {
                QMessageBox.Ok: 'OK',
                QMessageBox.Cancel: 'Cancel',
                QMessageBox.Yes: 'Yes',
                QMessageBox.No: 'No',
                QMessageBox.Close: 'Close',
            }
            return reverse_map.get(result, buttons[-1])
        except Exception:
            pass
    if _should_avoid_pyautogui():
        fallback = buttons[-1]
        print('[CONFIRM][{}] {} | default={}'.format(title, text, fallback))
        return fallback
    try:
        from pyautogui import confirm as pg_confirm
        return pg_confirm(text=text, title=title, buttons=buttons)
    except Exception:
        fallback = buttons[-1]
        print('[CONFIRM][{}] {} | default={}'.format(title, text, fallback))
        return fallback


def password(text='', title='Password', default='', mask='*'):
    if _can_show_qt_dialog():
        try:
            from PyQt5.QtWidgets import QInputDialog, QLineEdit
            value, ok = QInputDialog.getText(None, title, text, QLineEdit.Password, default)
            if ok:
                return value
            return default
        except Exception:
            pass
    if _should_avoid_pyautogui():
        print('[PASSWORD][{}] {}'.format(title, text))
        return default
    try:
        from pyautogui import password as pg_password
        return pg_password(text=text, title=title, default=default, mask=mask)
    except Exception:
        print('[PASSWORD][{}] {}'.format(title, text))
        return default
