from PyQt5.QtWidgets import QFileDialog, QTableWidgetItem, QMessageBox
from PyQt5 import QtCore, QtGui, QtWidgets
from threading import Thread
import requests
import var
from p_gui import Ui_Dialog
import os, sys
import time
from PyQt5.QtCore import pyqtSignal, QObject

cancel = False
total_email_count = 0

class Communicate(QObject):
    s = pyqtSignal(int)

class Communicate(QObject):
    s = pyqtSignal(int, str)

class Download(Ui_Dialog):
    def __init__(self, dialog, name, link, size, path):
        Ui_Dialog.__init__(self)
        self.setupUi(dialog)
        self.dialog = dialog
        set_icon(self.dialog)
        self.signal = Communicate()
        self.signal.s.connect(self.update_gui)
        self.name = name
        self.link = link
        self.size = size
        self.size_in_kb = int(round(size/1024))
        self.file_path = path
        self.pushButton_cancel.clicked.connect(self.cancel)
        self.label_status.setText("Dowloaded  {} of {} kb".format(0, self.size_in_kb))
        Thread(target=self.download, daemon=True).start()

    def update_gui(self, dowloaded, message):
        if message != "":
            self.label_status.setText(message)
            self.pushButton_cancel.setText("Close")
        else:
            self.label_status.setText("Dowloaded  {} of {} kb".format(dowloaded, self.size_in_kb))
            value = (dowloaded/self.size_in_kb)*100
            self.progressBar.setValue(value)

    def cancel(self):
        global cancel
        cancel = True
        self.dialog.accept()

    def download(self):
        global cancel
        try:
            # ua = UserAgent()
            # userAgent = ua.random
            headers = {'user-agent': 'Wget/1.16 (linux-gnu)'}
            # headers = {'user-agent': '{}'.format(userAgent)}
            # print(headers)
            filepath = "{}/GMonster{}.zip".format(self.file_path, self.name)
            print(filepath)
            url = var.api + "verify/wum_version/download/{}".format(self.name)
            response = requests.post(url, timeout=10)
            data = response.json()
            print(data)
            url = self.link
            r = requests.get(url, stream=True, headers=headers)
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        if cancel==True:
                            break
                        downloaded+=len(chunk)
                        print("Dowloaded {}/{}".format(downloaded, self.size), end='\r')
                        self.signal.s.emit(int(round(downloaded/1024)), "")
                        f.write(chunk)
            print("download finished")
            self.signal.s.emit(int(round(downloaded/1024)), "Download Finished")
        except Exception as e:
            print("Error at download update: {}".format(e))


def set_icon(obj):
    try:
        def resource_path(relative_path):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, relative_path)
            return os.path.join(os.path.abspath("."), relative_path)

        p = resource_path('icons/icon.ico')
        obj.setWindowIcon(QtGui.QIcon(p))
    except Exception as e:
        print(e)

