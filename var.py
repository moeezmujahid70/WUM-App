from dateutil import parser
import logging
from queue import LifoQueue
from collections import deque
import queue
import pandas as pd
import uuid
import tempfile
import threading
import sys
import os
from json import load, dumps
from compat_ui import alert, password, confirm
global compose_email_body
global next_phase_in
global compose_email_subject
global session_track
global has_cache
global phase_completed

try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None

try:
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None


def override_where():
    """ overrides certifi.core.where to return actual location of cacert.pem"""
    # change this to match the location of cacert.pem
    return os.path.abspath(os.path.join(os.getcwd(), "data", "gmonster_config", "cacert.pem"))


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
        self.lock_name = 'wum_single_instance.lock'
        self.lock_path = os.path.join(tempfile.gettempdir(), self.lock_name)
        self.lock_file = None
        self._already_running = False
        self._lock_kind = None

        try:
            self.lock_file = open(self.lock_path, 'w')
            if os.name == 'nt' and _msvcrt is not None:
                _msvcrt.locking(self.lock_file.fileno(), _msvcrt.LK_NBLCK, 1)
                self._lock_kind = 'msvcrt'
            elif _fcntl is not None:
                _fcntl.flock(self.lock_file.fileno(),
                             _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                self._lock_kind = 'fcntl'
            else:
                self._already_running = False
        except OSError:
            self._already_running = True

    def already_running(self):
        return self._already_running

    def __del__(self):
        if not self.lock_file:
            return
        try:
            if self._lock_kind == 'msvcrt' and _msvcrt is not None:
                self.lock_file.seek(0)
                _msvcrt.locking(self.lock_file.fileno(), _msvcrt.LK_UNLCK, 1)
            elif self._lock_kind == 'fcntl' and _fcntl is not None:
                _fcntl.flock(self.lock_file.fileno(), _fcntl.LOCK_UN)
        except OSError:
            pass
        except Exception:
            pass
        finally:
            try:
                self.lock_file.close()
            except Exception:
                pass
            if not self._already_running:
                try:
                    os.remove(self.lock_path)
                except OSError:
                    pass


version = '2.2r'
logs_dir = os.path.join('data', 'logs', 'wum')
db_base_dir = os.path.join('data', 'gmonster_config')
gmonster_base_dir = os.path.join('data', 'gmonster_config')
sheets_base_dir = os.path.join('data', 'sheets')
config_base_dir = os.path.join('data', 'wum_config')
cancel = False
thread_open = 0
imap_server = 'imap.gmail.com'
imap_port = 993
smtp_server = 'smtp.gmail.com'
smtp_port = 587
try:
    if not os.path.isdir(logs_dir):
        os.makedirs(logs_dir)
except Exception as e:
    print('{} Folder not found or creation failed - {}'.format(logs_dir, e))
try:
    if not os.path.isdir(gmonster_base_dir):
        os.makedirs(gmonster_base_dir)
except Exception as e:
    print('{} Folder not found or creation failed - {}'.format(gmonster_base_dir, e))
try:
    if not os.path.isdir(sheets_base_dir):
        os.makedirs(sheets_base_dir)
except Exception as e:
    print('{} Folder not found or creation failed - {}'.format(sheets_base_dir, e))
try:
    if not os.path.isdir(config_base_dir):
        os.makedirs(config_base_dir)
except Exception as e:
    print('{} Folder not found or creation failed - {}'.format(config_base_dir, e))
# Create and configure logger
logging.basicConfig(
    filename=logs_dir + '/wum.log',
    format='%(asctime)s %(message)s',
    filemode='a',
    level=logging.INFO
)
logging.getLogger('requests').setLevel(logging.WARNING)
api = ''
# api = "http://127.0.0.1:5000/"
sign_up_label = ''
sign_in_label = ''
signed_in = False
email_mode = 'canned'
ai_prompt_subject = 'AI generated outreach'
ai_prompt_body = 'This is a predefined AI prompt. Replace with your AI-generated content.'
openai_api_key = ''
openai_model = 'gpt-4o-mini'
openai_base_url = 'https://api.openai.com/v1'
openai_timeout = 45
ai_prompt_path = os.path.join(config_base_dir, 'PROMPT1.txt')
ai_email_template_path = os.path.join(config_base_dir, 'EMAIL1.txt')
ai_reply_prompt_path = os.path.join(config_base_dir, 'PROMPT2.txt')
ai_reply_email_template_path = os.path.join(config_base_dir, 'EMAIL2.txt')
limit_of_thread = 100
login_email = ''
gmonster_desktop_id = '6296d839-9b35-4c12-830a-6c871affc3e2'
has_cache = False
cache_choice_made = False
resume_cached_run = False
session_track = {}
phase_completed = '0'
next_phase_in = ''


def _mask_secret(secret):
    if not secret:
        return '<empty>'
    secret = secret.strip()
    if len(secret) <= 8:
        return secret[0] + '***' + secret[-1]
    return '{}***{}'.format(secret[:4], secret[-4:])


def _log_ai_settings(context):
    try:
        masked_key = _mask_secret(openai_api_key)
    except Exception:
        masked_key = '<error>'
    print('[AI CONFIG][{}] api_key={} model={} base_url={} timeout={}'.format(
        context,
        masked_key,
        openai_model,
        openai_base_url,
        openai_timeout
    ))


def _normalize_config_path(path_value, default_path):
    path_text = (path_value or default_path or '').strip()
    if not path_text:
        return default_path
    normalized = os.path.normpath(
        path_text.replace('\\', os.sep).replace('/', os.sep))
    return normalized


def _normalize_api_base(url_value, default_url):
    url_text = (url_value or default_url or '').strip()
    if not url_text:
        url_text = default_url
    if url_text and not url_text.endswith('/'):
        url_text += '/'
    return url_text


def load_cache():
    global phase_completed
    global next_phase_in
    global has_cache
    global session_track
    try:
        with open(os.path.join(config_base_dir, 'cache.json'), encoding='utf-8') as json_file:
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


config_path = os.path.join(config_base_dir, 'config.json')
try:
    with open(config_path, encoding='utf-8') as json_file:
        data = load(json_file)
    config = data['config']
    settings = data['settings']
    api = _normalize_api_base(config.get('api', api), api)
    limit_of_thread = config['limit_of_thread']
    login_email = config['login_email']
    openai_api_key = (config.get('openai_api_key',
                      openai_api_key) or '').strip()
    openai_model = config.get('openai_model', openai_model)
    openai_base_url = config.get('openai_base_url', openai_base_url)
    try:
        openai_timeout = float(config.get('openai_timeout', openai_timeout))
    except (TypeError, ValueError):
        openai_timeout = 45
    ai_prompt_path = _normalize_config_path(
        config.get('ai_prompt_path', ai_prompt_path), ai_prompt_path)
    ai_email_template_path = _normalize_config_path(
        config.get('ai_email_template_path', ai_email_template_path), ai_email_template_path)
    ai_reply_prompt_path = _normalize_config_path(
        config.get('ai_reply_prompt_path', ai_reply_prompt_path), ai_reply_prompt_path)
    ai_reply_email_template_path = _normalize_config_path(
        config.get('ai_reply_email_template_path', ai_reply_email_template_path), ai_reply_email_template_path)
    _log_ai_settings('config.json')
except Exception as e:
    print("Exception occurred at config loading : {}".format(e))

# env_api_key = os.getenv('OPENAI_API_KEY')
# if env_api_key:
#     openai_api_key = env_api_key.strip()
# env_model = os.getenv('OPENAI_MODEL')
# if env_model:
#     openai_model = env_model.strip()
# env_base_url = os.getenv('OPENAI_BASE_URL')
# if env_base_url:
#     openai_base_url = env_base_url.strip()
# env_timeout = os.getenv('OPENAI_TIMEOUT')
# if env_timeout:
#     try:
#         openai_timeout = float(env_timeout)
#     except (TypeError, ValueError):
#         pass
# _log_ai_settings('env override')

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
    with open(os.path.join(gmonster_base_dir, 'gmonster_config.json'), encoding='utf-8') as json_file:
        data = load(json_file)
    config = data['config']
    mail_server = config['mail_server']
    gmonster_desktop_id = str(config.get(
        'desktop_id', gmonster_desktop_id)).strip() or gmonster_desktop_id
except Exception as e:
    print('Exception occurred at config loading : {}'.format(e))
compose_email_body = 'This is sample body text'
compose_email_subject = 'This is sample subject'


def compose_loading():
    global compose_email_subject
    global compose_email_body
    try:
        with open(os.path.join(config_base_dir, 'subject.txt'), 'r', encoding='utf-8') as f:
            compose_email_subject = f.read().strip()
        with open(os.path.join(config_base_dir, 'body.txt'), 'r', encoding='utf-8') as f:
            compose_email_body = f.read().strip()
    except Exception as e:
        print('Exception occurred at subject/body loading : {}'.format(e))


compose_loading()


def compose_saving():
    try:
        with open(os.path.join(config_base_dir, 'subject.txt'), 'w', encoding='utf-8') as f:
            f.write(compose_email_subject)
        with open(os.path.join(config_base_dir, 'body.txt'), 'w', encoding='utf-8') as f:
            f.write(compose_email_body)
    except Exception as e:
        print('Exception occurred at subject/body loading : {}'.format(e))


def load_db(parent=None):
    global group
    try:
        group_a = pd.read_excel(
            os.path.join(sheets_base_dir, 'group_a.xlsx'), engine='openpyxl')
        group_b = pd.read_excel(
            os.path.join(sheets_base_dir, 'group_b.xlsx'), engine='openpyxl')
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
            duplicate_message = 'Found {} duplicates in database file'.format(
                len_group_initial - len_group_final)
            if parent == 'dialog' or threading.current_thread() is not threading.main_thread():
                print(duplicate_message)
            else:
                alert(text=duplicate_message, title='Alert', button='OK')
        print(group.head(5))
        if parent == 'var':
            print('Database loaded')
        elif parent == 'dialog':
            print('DB loaded')
        else:
            if threading.current_thread() is threading.main_thread():
                alert(text='Database Loaded', title='Alert', button='OK')
            else:
                print('Database loaded')
    except Exception as e:
        print("Exception occurred at db loading : {}".format(e))
        error_message = "Exception occurred at db loading : {}".format(e)
        if parent == 'dialog' or threading.current_thread() is not threading.main_thread():
            print(error_message)
        else:
            alert(text=error_message, title='Alert', button='OK')


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
            is_testing_environment = int(
                os.getenv('fa414ce5-05d1-45e2-ba53-df760ad35fa0'))
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
