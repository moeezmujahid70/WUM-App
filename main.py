global app
global GUI
global mainWindow
import datetime
from pyautogui import alert, password, confirm
import json
from threading import Thread
from time import sleep
import os
import sys
from PyQt5.QtWidgets import QFileDialog, QTableWidgetItem, QMessageBox, QButtonGroup
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from gui import Ui_MainWindow
import traceback
import encodings.idna
import pandas as pd
import webbrowser
import subprocess
import requests
print('App started....')

class StatusModel(QtCore.QAbstractListModel):

    def __init__(self, *args, status=None, **kwargs):
        super(StatusModel, self).__init__(*args, **kwargs)
        self.status = status or []

    def data(self, index, role):
        if role == Qt.DisplayRole:
            _, text = self.status[index.row()]
            return text
        if role == Qt.ForegroundRole:
            return QColor('#555')
        if role == Qt.FontRole:
            font = QFont('Arial')
            return font
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        if role == Qt.BackgroundRole:
            _status, _ = self.status[index.row()]
            if _status:
                return QColor('#DCE3ED')

    def rowCount(self, index):
        return len(self.status)

class MyGui(Ui_MainWindow, QtWidgets.QWidget):

    def __init__(self, mainWindow):
        Ui_MainWindow.__init__(self)
        QtWidgets.QWidget.__init__(self)
        self.setupUi(mainWindow)

class Report(QObject):
    s = pyqtSignal(str, int)

class Main:

    def __init__(self):
        self.sub_exp = 0
        self.try_failed = 0
        self.logger = var.logging
        self.logger.getLogger('requests').setLevel(var.logging.WARNING)
        GUI.lineEdit_subject.setText(var.compose_email_subject)
        GUI.textBrowser_body.setText(var.compose_email_body)
        GUI.signal = Report()
        GUI.signal.s.connect(self.update_report)
        GUI.model = StatusModel()
        GUI.statusView.setModel(GUI.model)
        for index in range(1, 8):
            GUI.model.status.append((False, 'Phase {}'.format(index)))
        GUI.model.layoutChanged.emit()
        GUI.cancelButton.setEnabled(False)
        GUI.cancelButton.clicked.connect(self.cancel)
        GUI.startButton.clicked.connect(self.start)
        GUI.pushButton_update_config.clicked.connect(self.update)
        layout = QVBoxLayout()
        GUI.progress_bar = CircularProgress(phase=0)
        GUI.progress_bar.setObjectName('progress_bar')
        layout.addWidget(GUI.progress_bar)
        layout.setAlignment(Qt.AlignCenter)
        GUI.progress_bar_widget.setLayout(layout)
        self.time_interval_sub_check = 3600
        Thread(target=self.check_for_subscription, daemon=True).start()
        self.mode_button_group = QButtonGroup()
        self.mode_button_group.setExclusive(True)
        self.mode_button_group.addButton(GUI.pushButton_canned_mode)
        self.mode_button_group.addButton(GUI.pushButton_ai_mode)
        GUI.pushButton_canned_mode.clicked.connect(lambda: self.set_compose_mode(False))
        GUI.pushButton_ai_mode.clicked.connect(lambda: self.set_compose_mode(True))
        GUI.stackedWidget.currentChanged.connect(self.handle_stack_change)
        self.ai_mode_enabled = None
        self.handle_stack_change(GUI.stackedWidget.currentIndex())
        self.set_compose_mode(False)

    def check_for_subscription(self):
        while True:
            try:
                url = var.api + 'verify/check_for_subscription/{}'.format(var.login_email)
                response = requests.post(url, timeout=10)
                data = response.json()
                if response.status_code == 200:
                    if data['status'] == 2:
                        self.try_failed = 0
                        print(data['end_date'])
                        date = str(data['end_date'])
                        alert(text='Subscription Expired at {}.\nSoftware will exit soon.'.format(date), title='Alert', button='OK')
                        mainWindow.close()
                    elif data['status'] == 3:
                        self.try_failed = 0
                        print('sub deactivated')
                        alert(text='Subscription deativated.\nSoftware will exit soon.', title='Alert', button='OK')
                        mainWindow.close()
                    elif data['status'] == 1:
                        self.try_failed = 0
                        print(data['days_left'])
                        if 'Phase' not in GUI.label_status.text():
                            GUI.label_status.setText('Subscription ends after {} days.'.format(data['days_left']))
                    else:
                        self.try_failed = 0
                        alert(text='Account not found', title='Alert', button='OK')
                        mainWindow.close()
                else:
                    alert(text='Error on server.\nContact Admin.', title='Alert', button='OK')
            except Exception as e:
                self.try_failed += 1
                print('error at check_for_subscription: {}'.format(traceback.format_exc()))
                GUI.label_status.setText('Check your internet connection.')
                if self.try_failed > 3:
                    alert(text='Check your internet connection.', title='Alert', button='OK')
                    mainWindow.close()
            sleep(self.time_interval_sub_check)

    def update(self):
        var.compose_email_subject = GUI.lineEdit_subject.text().strip()
        var.compose_email_body = GUI.textBrowser_body.toPlainText().strip()
        Thread(target=var.compose_saving, daemon=True).start()

    def update_report(self, text, flag):
        if flag:
            text = '<span style=" color: #96bb7c;">%s</span>' % text
        else:
            text = '<span style=" color: #ee9595;">%s</span>' % text
        GUI.textBrowser_report.append(text)

    def start(self):
        var.cancel = False
        var.compose_email_subject = GUI.lineEdit_subject.text()
        var.compose_email_body = GUI.textBrowser_body.toPlainText()
        Thread(target=smtp.main, daemon=True).start()
        GUI.startButton.setEnabled(False)
        GUI.cancelButton.setEnabled(True)

    def cancel(self):
        var.cancel = True
        GUI.startButton.setEnabled(True)
        GUI.cancelButton.setEnabled(False)

    def handle_stack_change(self, index):
        GUI.widget_compose_mode.setVisible(index == 1)

    def set_compose_mode(self, enable_ai_mode):
        if self.ai_mode_enabled == enable_ai_mode:
            return
        self.ai_mode_enabled = enable_ai_mode
        GUI.pushButton_ai_mode.blockSignals(True)
        GUI.pushButton_canned_mode.blockSignals(True)
        GUI.pushButton_ai_mode.setChecked(enable_ai_mode)
        GUI.pushButton_canned_mode.setChecked(not enable_ai_mode)
        GUI.pushButton_ai_mode.blockSignals(False)
        GUI.pushButton_canned_mode.blockSignals(False)
        GUI.lineEdit_subject.setReadOnly(enable_ai_mode)
        GUI.textBrowser_body.setReadOnly(enable_ai_mode)
        flags = Qt.TextBrowserInteraction | Qt.LinksAccessibleByKeyboard | Qt.LinksAccessibleByMouse | Qt.TextSelectableByMouse
        if not enable_ai_mode:
            flags |= Qt.TextEditable
        GUI.textBrowser_body.setTextInteractionFlags(flags)
        if enable_ai_mode:
            GUI.lineEdit_subject.setStyleSheet('color: #9AA0A6;')
            GUI.textBrowser_body.setStyleSheet('color: #9AA0A6;')
        else:
            GUI.lineEdit_subject.setStyleSheet('')
            GUI.textBrowser_body.setStyleSheet('')
        var.email_mode = 'ai' if enable_ai_mode else 'canned'


    # def smtp(self):
    #     print(len(var.group))
    #     if len(var.group)>=20:
    #         for key, item in var.settings.items():
    #             print("Phase {} starting...".format(key))
    #             GUI.label_status.setText("Phase {} starting...".format(key))
    #             row = int(key)-1
    #             status, text = GUI.model.status[row]
    #             GUI.model.status[row] = (True, text)
    #             # GUI.model.dataChanged.emit()
    #             sleep(5)
    #     else:
    #         GUI.startButton.setEnabled(True)
    #         GUI.cancelButton.setEnabled(False)
    #         alert(text="Database should contain at least 20 emails", title="Alert", button="OK")

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QPainter, QPen, QFont, QColor
from PyQt5.QtCore import Qt, QTimer, QRectF

class CircularProgress(QWidget):

    def __init__(self, phase=1):
        super().__init__()
        self.progress = 0
        self.max_value = 100
        self.phase = phase
        self.setMinimumSize(300, 300)
        self.label_status = ''

    def update_progress(self, progress):
        """Increase progress and repaint."""
        self.progress = progress
        if self.progress > self.max_value:
            self.progress = self.max_value
        self.update()

    def paintEvent(self, event):
        """Draw circular progress with labels."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(10, 10, 250, 250)
        pen = QPen(Qt.lightGray, 10)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 5760)
        pen.setColor(QColor('#3366FF'))
        painter.setPen(pen)
        angle = int(self.progress / self.max_value * 360 * 16)
        painter.drawArc(rect, 1440, -angle)
        painter.setPen(QColor('#545454'))
        painter.setFont(QFont('Arial', 30))
        painter.drawText(rect.adjusted(0, -150, 0, 0), Qt.AlignCenter, 'Phase')
        painter.setFont(QFont('Arial', 70))
        painter.drawText(rect, Qt.AlignCenter, str(self.phase))
        painter.setFont(QFont('Arial', 15))
        painter.drawText(rect.adjusted(0, 150, 0, 0), Qt.AlignCenter, self.label_status)
        painter.end()

def set_icon(obj):
    try:

        def resource_path(relative_path):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, relative_path)
            return os.path.join(os.path.abspath('.'), relative_path)
        p = resource_path('icons/icon.ico')
        obj.setWindowIcon(QtGui.QIcon(p))
    except Exception as e:
        print(e)
if __name__ == '__main__':
    print('ran from here')
else:
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = QtWidgets.QMainWindow()
    set_icon(mainWindow)
    mainWindow.setWindowFlags(mainWindow.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint | QtCore.Qt.WindowSystemMenuHint)
    GUI = MyGui(mainWindow)
    # mainWindow.showMaximized()
    mainWindow.show()
    import var
    import smtp
    try:
        print(len(var.group))
    except:
        Thread(target=var.load_db, daemon=True, args=('dialog',)).start()
    myMC = Main()
    sys.exit(app.exec_())