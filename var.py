from json import load, dumps
from pyautogui import alert, password, confirm
global compose_email_body
global next_phase_in
global compose_email_subject
global session_track
global has_cache
global phase_completed
import os
import sys
import pandas as pd
import queue
from collections import deque
from queue import LifoQueue
from win32event import CreateMutex
from win32api import CloseHandle, GetLastError
from winerror import ERROR_ALREADY_EXISTS
import logging
from dateutil import parser

def override_where():
    """ overrides certifi.core.where to return actual location of cacert.pem"""
    # change this to match the location of cacert.pem
    return os.path.abspath(os.path.join(os.getcwd(), "database", "cacert.pem"))


# is the program compiled?
if hasattr(sys, "frozen"):
    import certifi.core
    os.environ['REQUESTS_CA_BUNDLE'] = override_where()
    certifi.core.where = override_where

    # delay importing until after where() has been replaced
    import requests
    import requests.utils
    import requests.adapters

    # replace these variables in case these modules were
    # imported before we replaced certifi.core.where
    requests.utils.DEFAULT_CA_BUNDLE_PATH = override_where()
    requests.adapters.DEFAULT_CA_BUNDLE_PATH = override_where()
else:
    import requests

class SingleInstance:
    """ Limits application to single instance """

    def __init__(self):
        self.mutexname = 'testmutex_{D0E858DF-985E-4907-B7FB-8D732C3FC3B90}'
        self.mutex = CreateMutex(None, False, self.mutexname)
        self.lasterror = GetLastError()

    def already_running(self):
        return self.lasterror == ERROR_ALREADY_EXISTS

    def __del__(self):
        if self.mutex:
            CloseHandle(self.mutex)
version = '1.1r'
logs_dir = 'logs'
db_base_dir = 'database'
cancel = False
thread_open = 0
imap_server = 'imap.gmail.com'
imap_port = 993
smtp_server = 'smtp.gmail.com'
smtp_port = 587
try:
    if not os.path.isdir(logs_dir):
        os.mkdir(logs_dir)
except Exception as e:
    print('{} Folder not found or creation failed - {}'.format(logs_dir, e))
try:
    if not os.path.isdir(db_base_dir):
        os.mkdir(db_base_dir)
except Exception as e:
    print('{} Folder not found or creation failed - {}'.format(db_base_dir, e))
# Create and configure logger    
logging.basicConfig(filename=logs_dir + '/wum.log', format='%(asctime)s %(message)s', filemode='a')
logging.getLogger('requests').setLevel(logging.WARNING)
api = 'https://enzim.pythonanywhere.com/'
# api = "http://127.0.0.1:5000/"
sign_up_label = ''
sign_in_label = ''
signed_in = False
limit_of_thread = 100
login_email = ''
has_cache = False
session_track = {}
phase_completed = '0'
next_phase_in = ''

def load_cache():
    global phase_completed
    global next_phase_in
    global has_cache
    global session_track
    try:
        with open('wum_config/cache.json', encoding='utf-8') as json_file:
            data = load(json_file)
        if int(data['phase_completed']) < 7:
            has_cache = True
        else:
            has_cache = False
        phase_completed = data['phase_completed']
        session_track = data['session_track']
        next_phase_in = parser.parse(data['next_phase_in'])
    except Exception as e:
        print('Exception occurred at cache loading : {}'.format(e))
config_path = 'wum_config/config.json'
try:
    with open(config_path, encoding='utf-8') as json_file:
        data = load(json_file)
    config = data['config']
    settings = data['settings']
    limit_of_thread = config['limit_of_thread']
    login_email = config['login_email']
except Exception as e:
    print("Exception occurred at config loading : {}".format(e))

mail_server = {
            "gmail": {
                "imap": {
                    "server": "imap.gmail.com",
                    "port": 993
                },
                "smtp": {
                    "server": "smtp.gmail.com",
                    "port": 587,
                    "require_ssl": False
                }
            },
            "outlook": {
                "imap": {
                    "server": "outlook.office365.com",
                    "port": 993
                },
                "smtp": {
                    "server": "smtp.office365.com",
                    "port": 587,
                    "require_ssl": False
                }
            }
        }

try:
    with open(f'{db_base_dir}/gmonster_config.json', encoding='utf-8') as json_file:
        data = load(json_file)
    config = data['config']
    mail_server = config['mail_server']
except Exception as e:
    print('Exception occurred at config loading : {}'.format(e))
compose_email_body = 'This is sample body text'
compose_email_subject = 'This is sample subject'

def compose_loading():
    global compose_email_subject
    global compose_email_body
    try:
        with open('wum_config/subject.txt', 'r', encoding='utf-8') as f:
            compose_email_subject = f.read().strip()
        with open('wum_config/body.txt', 'r', encoding='utf-8') as f:
            compose_email_body = f.read().strip()
    except Exception as e:
        print('Exception occurred at subject/body loading : {}'.format(e))
compose_loading()

def compose_saving():
    try:
        with open('database/subject.txt', 'w', encoding='utf-8') as f:
            f.write(compose_email_subject)
        with open('database/body.txt', 'w', encoding='utf-8') as f:
            f.write(compose_email_body)
    except Exception as e:
        print('Exception occurred at subject/body loading : {}'.format(e))

def load_db(parent=None):
    global group
    try:
        group_a = pd.read_excel(f'{db_base_dir}/group_a.xlsx', engine='openpyxl')
        group_b = pd.read_excel(f'{db_base_dir}/group_b.xlsx', engine='openpyxl')
        group = [group_a, group_b]
        group = pd.concat(group)
        group = group.reset_index(drop=True)
        group.fillna(' ', inplace=True)
        group = group.astype(str)
        group = group.loc[group['PROXY:PORT'] != ' ']
        len_group_initial = len(group)
        group = group.drop_duplicates(subset='EMAIL')
        len_group_final = len(group)
        if len_group_final != len_group_initial:
            alert(text='Found {} duplicates in database file'.format(len_group_initial - len_group_final), title='Alert', button='OK')
        print(group.head(5))
        if parent == 'var':
            print('Database loaded')
        elif parent == 'dialog':
            print('DB loaded')
        else:
            alert(text='Database Loaded', title='Alert', button='OK')
    except Exception as e:
        print("Exception occurred at db loading : {}".format(e))
        alert(text="Exception occurred at db loading : {}".format(
            e), title='Alert', button='OK')


if __name__ == "__main__":
    # do this at beginning of your application
    myapp = SingleInstance()

    # check is another instance of same program running
    if myapp.already_running():
        alert(text='Another instance of this program is already running')
        logging.info('Another instance of this program is already running')
        sys.exit(1)
    is_testing_environment = 0
    try:
        if os.getenv('fa414ce5-05d1-45e2-ba53-df760ad35fa0'):
            is_testing_environment = int(os.getenv('fa414ce5-05d1-45e2-ba53-df760ad35fa0'))
    except:
        pass
    if is_testing_environment:
        import main
    else:
        import dialog

# pyinstaller --onedir --icon=icons/icon.ico --name=WUM --noconsole --noconfirm var.py
# pyinstaller --onedir --icon=icons/icon.ico --name=WUM --noconfirm var.py
# pyi-makespec --onefile --icon=icons/icon.ico --name=WUM --noconsole var.py
# pyinstaller WUM.spec
