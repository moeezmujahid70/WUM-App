from dialog import myMainClass
from proxy_smtplib import SMTP, SmtpProxy, Proxifier
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
global logger
global phase_email_list
global error_list
global session_track
global total_email_sent_count
import dateutil
import traceback
import socks
import threading
import var
import time
import utils
import smtplib
import csv
import queue
import random
from pyautogui import alert, password, confirm
from main import GUI
import imap
import json
import re
from datetime import datetime, timedelta
import server_client
import async_reply
error_list = queue.Queue()
total_email_sent_count = 0
phase_email_list = list()
session_track = {}
logger = var.logging
logger.getLogger('requests').setLevel(var.logging.WARNING)

def percent_boolean_gen(percent=50):
    return random.randrange(100) < percent

def status_print(label_text=None, print_text=None, textbrowser=None):
    if label_text:
        GUI.label_status.setText(label_text)
    if print_text:
        print(print_text)
    if textbrowser:
        GUI.signal.s.emit(textbrowser[0], textbrowser[1])

def progress_print(phase, progress, status):
    if hasattr(GUI, 'progress_bar'):
        GUI.progress_bar.phase = phase
        GUI.progress_bar.update_progress(progress)
        GUI.progress_bar.label_status = status
        GUI.progress_bar.update()

class SMTP_(threading.Thread):

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.threadID = kwargs['threadID']
        self.name = kwargs['name']
        self.setDaemon = True
        self.proxy_host = kwargs['proxy_host']
        self.proxy_port = kwargs['proxy_port']
        self.proxy_user = kwargs['proxy_user']
        self.proxy_pass = kwargs['proxy_pass']
        self.proxy = {'useproxy': True, 'server': kwargs['proxy_host'], 'port': kwargs['proxy_port'], 'type': 'SOCKS5', 'username': kwargs['proxy_user'], 'password': kwargs['proxy_pass']}
        self.user = kwargs['user']
        self.password = kwargs['password']
        self.FIRSTFROMNAME = kwargs['FIRSTFROMNAME']
        self.LASTFROMNAME = kwargs['LASTFROMNAME']
        self.targets = kwargs['targets']
        self.delay_start = kwargs['delay_start']
        self.delay_end = kwargs['delay_end']
        self.logger = logger
        self.total_email_to_be_sent = kwargs['total_email_to_be_sent']
        try:
            regex = re.compile('(?<=@)(\\S+$)')
            mail_domain = regex.findall(self.user)[0]
            mail_vendor = mail_domain.split('.')[0]
            parts = mail_domain.split('.')
            if len(parts) > 2:
                mail_vendor = '.'.join(parts[:-1])
            elif len(parts) == 2:
                mail_vendor = parts[0]
            else:
                mail_vendor = mail_domain
            new_domain_config = {'imap': {'server': 'imap.gmail.com', 'port': 993}, 'smtp': {'server': 'smtp.gmail.com', 'port': 587, 'require_ssl': False}}
            if mail_vendor not in var.mail_server:
                var.mail_server[mail_vendor] = new_domain_config
                var.data['config']['mail_server'] = var.mail_server
                with open(f'{var.db_base_dir}/gmonster_config.json', 'w', encoding='utf-8') as json_file:
                    json.dump(var.data, json_file, indent=4)
            self.smtp_server = var.mail_server[mail_vendor]['smtp']['server']
            self.smtp_port = var.mail_server[mail_vendor]['smtp']['port']
        except:
            logger.error(f'SmtpBase error: {traceback.format_exc()}')
            raise

    def login(self):
        for count in range(0, 3):
            try:
                if self.proxy_host != '':
                    server = SMTP(timeout=30)
                    server.connect_proxy(host=self.smtp_server, port=self.smtp_port, proxy_host=self.proxy_host, proxy_port=int(self.proxy_port), proxy_type=socks.PROXY_TYPE_SOCKS5, proxy_user=self.proxy_user, proxy_pass=self.proxy_pass)
                    server.set_debuglevel(0)
                else:
                    server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                    server.set_debuglevel(0)
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.user, self.password)
                break
            except Exception as e:
                if count <= 1:
                    time.sleep(50)
                    continue
                raise
        return server

    def run(self):
        global total_email_sent_count
        try:
            var.thread_open += 1
            for item in self.targets:
                if var.cancel:
                    break
                time.sleep(random.randint(self.delay_start, self.delay_end))
                server = self.login()
                msg = MIMEMultipart('alternative')
                msg['Subject'] = utils.format_email(var.compose_email_subject, self.FIRSTFROMNAME, self.LASTFROMNAME, item['FIRSTFROMNAME'])
                msg['From'] = formataddr((str(Header('{} {}'.format(self.FIRSTFROMNAME, self.LASTFROMNAME), 'utf-8')), self.user))
                msg['To'] = item['EMAIL']
                msg['Date'] = formatdate(localtime=True)
                body = utils.format_email(var.compose_email_body, self.FIRSTFROMNAME, self.LASTFROMNAME, item['FIRSTFROMNAME'])
                msg.attach(MIMEText(body, 'plain'))
                server.sendmail(self.user, item['EMAIL'], msg.as_string())
                t_dict = {'subject': msg['Subject'], 'date': dateutil.parser.parse(msg['Date']).date().strftime('%d-%b-%Y'), 'EMAIL': self.user}
                session_track[item['EMAIL']]['send_info'].append(t_dict.copy())
                total_email_sent_count += 1
                text = '{}: {}/{}'.format(GUI.label_status.text().split(':')[0], total_email_sent_count, self.total_email_to_be_sent)
                status_print(label_text=text)
                label_text = text
                match = re.match('Phase (\\d+)\\s+(\\w+)\\s*:', label_text)
                if match:
                    phase_number = int(match.group(1))
                    phase_status = match.group(2).capitalize()
                    progress_print(phase_number, total_email_sent_count * 100 / self.total_email_to_be_sent, phase_status)
                else:
                    print('Unable to match phase information in the label text.')
                server.quit()
                server.close()
        except Exception as e:
            error_list.put(self.name)
            print('error at SMTP - {} - {}'.format(self.name, e))
            self.logger.error('Error at Sending - {} - {}'.format(self.name, e))
            GUI.signal.s.emit('Error at Sending - {} - {}'.format(self.name, e), False)
        finally:
            var.thread_open -= 1


class SMTP_Centralized(SMTP_):
    """Extended SMTP class that reports sent emails to centralized server"""
    
    def __init__(self, use_centralized=False, **kwargs):
        super().__init__(**kwargs)
        self.use_centralized = use_centralized
    
    def run(self):
        global total_email_sent_count
        try:
            var.thread_open += 1
            for item in self.targets:
                if var.cancel:
                    break
                time.sleep(random.randint(self.delay_start, self.delay_end))
                server = self.login()
                msg = MIMEMultipart('alternative')
                msg['Subject'] = utils.format_email(var.compose_email_subject, self.FIRSTFROMNAME, self.LASTFROMNAME, item['FIRSTFROMNAME'])
                msg['From'] = formataddr((str(Header('{} {}'.format(self.FIRSTFROMNAME, self.LASTFROMNAME), 'utf-8')), self.user))
                msg['To'] = item['EMAIL']
                msg['Date'] = formatdate(localtime=True)
                body = utils.format_email(var.compose_email_body, self.FIRSTFROMNAME, self.LASTFROMNAME, item['FIRSTFROMNAME'])
                msg.attach(MIMEText(body, 'plain'))
                server.sendmail(self.user, item['EMAIL'], msg.as_string())
                
                # Report to centralized server if enabled
                if self.use_centralized:
                    message_id = msg.get('Message-ID', '')
                    server_client.report_email_sent(
                        sender_email=self.user,
                        target_email=item['EMAIL'],
                        subject=msg['Subject'],
                        message_id=message_id
                    )
                
                # Keep original tracking for local compatibility
                t_dict = {'subject': msg['Subject'], 'date': dateutil.parser.parse(msg['Date']).date().strftime('%d-%b-%Y'), 'EMAIL': self.user}
                session_track[item['EMAIL']]['send_info'].append(t_dict.copy())
                
                total_email_sent_count += 1
                text = '{}: {}/{}'.format(GUI.label_status.text().split(':')[0], total_email_sent_count, self.total_email_to_be_sent)
                status_print(label_text=text)
                label_text = text
                match = re.match('Phase (\\d+)\\s+(\\w+)\\s*:', label_text)
                if match:
                    phase_number = int(match.group(1))
                    phase_status = match.group(2).capitalize()
                    progress_print(phase_number, total_email_sent_count * 100 / self.total_email_to_be_sent, phase_status)
                else:
                    print('Unable to match phase information in the label text.')
                server.quit()
                server.close()
        except Exception as e:
            error_list.put(self.name)
            print('error at SMTP_Centralized - {} - {}'.format(self.name, e))
            self.logger.error('Error at Sending - {} - {}'.format(self.name, e))
            GUI.signal.s.emit('Error at Sending - {} - {}'.format(self.name, e), False)
        finally:
            var.thread_open -= 1


class Reply_SMTP(SMTP_):

    def __init__(self, **kwargs):
        super(Reply_SMTP, self).__init__(**kwargs)

    def run(self):
        global total_email_sent_count
        try:
            var.thread_open += 1
            for item in self.targets:
                reciever = var.group.loc[var.group['EMAIL'] == item['reciever']].to_dict('records')[0]
                if var.cancel:
                    break
                time.sleep(random.randint(self.delay_start, self.delay_end))
                server = self.login()
                msg = MIMEMultipart('alternative')
                msg['Subject'] = 'RE: ' + item['subject']
                msg['From'] = formataddr((str(Header('{} {}'.format(self.FIRSTFROMNAME, self.LASTFROMNAME), 'utf-8')), self.user))
                msg['To'] = item['reciever']
                if percent_boolean_gen(30):
                    msg['X-Priority'] = '2'
                msg['Date'] = formatdate(localtime=True)
                body = utils.format_email(var.compose_email_body, self.FIRSTFROMNAME, self.LASTFROMNAME, reciever['FIRSTFROMNAME'])
                msg.add_header('In-Reply-To', item['msg_id'])
                msg.add_header('References', item['msg_id'])
                msg.attach(MIMEText(body, 'plain'))
                server.sendmail(self.user, item['reciever'], msg.as_string())
                total_email_sent_count += 1
                text = '{}: {}/{}'.format(GUI.label_status.text().split(':')[0], total_email_sent_count, self.total_email_to_be_sent)
                status_print(label_text=text)
                label_text = text
                match = re.match('Phase (\\d+)\\s+(\\w+)\\s*:', label_text)
                if match:
                    phase_number = int(match.group(1))
                    phase_status = match.group(2).capitalize()
                    progress_print(phase_number, total_email_sent_count * 100 / self.total_email_to_be_sent, phase_status)
                else:
                    print('Unable to match phase information in the label text.')
                server.quit()
                server.close()
        except Exception as e:
            error_list.put(self.name)
            print('error at Replying - {} - {}'.format(self.name, e))
            self.logger.error('Error at Replying - {} - {}'.format(self.name, e))
            GUI.signal.s.emit('Error at Replying - {} - {}'.format(self.name, e), False)
        finally:
            var.thread_open -= 1

def reply(phase, total_email_to_be_replied):
    count = 0
    for key, item in session_track.items():
        count += 1
        user = var.group.loc[var.group['EMAIL'] == key].to_dict('records')[0]
        proxy_user = user['PROXY_USER']
        proxy_pass = user['PROXY_PASS']
        username = user['EMAIL']
        password = user['EMAIL_PASS']
        name = user['EMAIL']
        FIRSTFROMNAME = user['FIRSTFROMNAME']
        LASTFROMNAME = user['LASTFROMNAME']
        if user['PROXY:PORT'] != ' ':
            proxy_host = user['PROXY:PORT'].split(':')[0]
            proxy_port = int(user['PROXY:PORT'].split(':')[1])
        else:
            proxy_host = ''
            proxy_port = ''
        if var.cancel:
            break
        while var.thread_open >= var.limit_of_thread:
            time.sleep(1)
        Reply_SMTP(threadID=count, name=name, proxy_host=proxy_host, proxy_port=proxy_port, proxy_user=proxy_user, proxy_pass=proxy_pass, user=username, password=password, FIRSTFROMNAME=FIRSTFROMNAME, LASTFROMNAME=LASTFROMNAME, targets=item['reply_info'], delay_start=phase['delay_start'], delay_end=phase['delay_end'], total_email_to_be_sent=total_email_to_be_replied).start()
    while var.thread_open != 0:
        time.sleep(1)
    return True

def main():
    while not var.cancel:
        var.load_db()

        # Initialize centralized warming client
        text = "Connecting to warming orchestrator server..."
        status_print(label_text=text, print_text=text, textbrowser=[text, True])
        
        centralized_enabled = server_client.initialize_warming_client()
        if centralized_enabled:
            text = "✓ Connected to centralized warming server"
            status_print(label_text=text, print_text=text, textbrowser=[text, True])
        else:
            text = "⚠ Centralized server unavailable - using local mode"
            status_print(label_text=text, print_text=text, textbrowser=[text, False])
        
        # Start asynchronous reply monitoring
        text = "Starting asynchronous reply system..."
        status_print(label_text=text, print_text=text, textbrowser=[text, True])
        async_reply.start_async_replies(var.group)
        text = "✓ Asynchronous replies started"
        status_print(label_text=text, print_text=text, textbrowser=[text, True])

        resting_days = [str(random.randint(0, 7)), str(random.randint(0, 7))]

        while True:
            if resting_days[0] != resting_days[1]:
                break
            else:
                resting_days[1] = str(random.randint(0, 7))

        for row in range(0, 7):
            status, text = GUI.model.status[row]
            GUI.model.status[row] = (False, text)

        global session_track, total_email_sent_count, error_list

        session_track = {item: {
            "avoid": [],
            "send_info": [],
            "reply_info": []
        }.copy() for item in var.group["EMAIL"].tolist()}
        # print(session_track)
        text = "Total account - {}".format(len(var.group))
        status_print(print_text=text, textbrowser=[text, True])

        global phase_email_list

        len_group = len(var.group)
        group = var.group.copy()

        var.load_cache()
        # print(var.has_cache)
        if var.has_cache:
            result = confirm(text='Do you want to continue previous(Phase {}) run?'.format(var.phase_completed),
                             title='Confirmation Window', buttons=['Yes', 'No'])

            if result == "No":
                var.has_cache = False
            else:
                session_track = var.session_track

        if len_group >= 26 and len_group % 2 == 0:
            # try:
            for key, item in var.settings.items():

                if var.cancel:
                    text = "Session cancelled"
                    status_print(label_text=text, print_text=text,
                                 textbrowser=[text, True])
                    break

                if int(key) <= int(var.phase_completed) and var.has_cache == True:
                    print("Skiping phase {}".format(key))
                    row = int(key) - 1
                    status, text = GUI.model.status[row]
                    GUI.model.status[row] = (True, text)
                    if int(key) == int(var.phase_completed):
                        wait_(int(key) + 1, var.next_phase_in)
                    continue

                total_email_sent_count = 0
                var.thread_open = 0

                item["number_of_emails"] = item["number_of_emails"].replace(" ", "")

                number_of_emails = random.randint(
                                                int(item["number_of_emails"].split("-")[0]),
                                                int(item["number_of_emails"].split("-")[1])
                                            )

                # Update server with phase quotas for all accounts
                if server_client.is_centralized_mode():
                    text = "Phase {} - Updating server quotas...".format(key)
                    status_print(label_text=text, print_text=text, textbrowser=[text, True])
                    
                    for index, user in group.iterrows():
                        result = server_client.update_phase_on_server(
                            user['EMAIL'], 
                            int(key), 
                            number_of_emails
                        )
                        if 'error' in result:
                            print(f"Failed to update server quota for {user['EMAIL']}: {result['error']}")

                text = "Phase {} sending : 0/{}".format(
                    key, len(group) * number_of_emails)
                status_print(label_text=text)

                # NEW: Progress tracking for sending phase start
                progress_print(key, 0, "Sending")

                phase_email_list = []
                sending(item, group, len(group) * number_of_emails, number_of_emails, int(key))
                status_print(
                    textbrowser=["Total sent - {}".format(total_email_sent_count), True])
                status_print(
                    textbrowser=["*** Phase {} sending error list ***".format(int(key)), False])
                show_report(error_list)

                if var.cancel:
                    break

                # temp = []
                # for key1, item1 in session_track.items():
                #     temp.append(item1["avoid"][0])
                #     print(key1, item1["avoid"][0], type(item1["send_info"]))
                # print(set([x for x in temp if temp.count(x) > 1]))

                # Brief pause after sending phase completion
                time.sleep(15)

                if var.cancel:
                    break

                # Note: Inbox checking and replies are now handled asynchronously
                text = "Phase {} - Sending complete. Replies handled asynchronously.".format(key)
                status_print(label_text=text, print_text=text, textbrowser=[text, True])

                for item_t in var.group["EMAIL"].tolist():
                    session_track[item_t]["send_info"] = []
                    session_track[item_t]["reply_info"] = []

                next_phase_in = datetime.now(
                ) + timedelta(hours=item["wait_period"])

                if key in resting_days:
                    text = "Resting Period added for phase {}".format(key)
                    status_print(label_text=text, print_text=text,
                                 textbrowser=[text, True])
                    next_phase_in = next_phase_in + timedelta(hours=24)

                cache_dump(key, str(next_phase_in))

                row = int(key) - 1
                status, text = GUI.model.status[row]
                GUI.model.status[row] = (True, text)

                text = "Phase {} finished".format(key)
                status_print(label_text=text, print_text=text,
                             textbrowser=[text, True])

                # NEW: Progress tracking for phase completion
                progress_print(key, 100, "Finished")

                if key != "7":
                    wait_(int(key) + 1, next_phase_in)

            # except Exception as e:
            #     print("Error at smtp.main - {}".format(e))
        else:
            alert(text="Database should contain at least 26 emails and should be even in quantity",
                  title="Alert", button="OK")
            break

    # Stop async reply monitoring
    async_reply.stop_async_replies()
    
    GUI.startButton.setEnabled(True)
    GUI.cancelButton.setEnabled(False)

    text = "Session ended"
    status_print(label_text=text, print_text=text, textbrowser=[text, True])

def sending(phase, group, total_email_to_be_sent, number_of_emails, phase_number):
    # Validate and normalize phase_number to a positive integer
    try:
        phase_number = int(phase_number)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid phase_number value: {phase_number!r}. Expected a positive integer.")
    if phase_number <= 0:
        raise ValueError(f"Invalid phase_number value: {phase_number}. Expected a positive integer.")
    for index, user in group.iterrows():
        # Try centralized target selection first
        if server_client.is_centralized_mode():
            receiver_list = server_client.get_centralized_targets(user['EMAIL'], number_of_emails, phase_number)
            
            # Fallback to local if centralized fails
            if not receiver_list:
                print(f"Centralized targets failed for {user['EMAIL']}, falling back to local")
                receiver_list = prepare_list(group.loc[group['EMAIL'] != user['EMAIL']].copy(), number_of_emails, session_track[user['EMAIL']]['avoid'])
                session_track[user['EMAIL']]['avoid'] = list(set(session_track[user['EMAIL']]['avoid'] + [item['EMAIL'] for item in receiver_list]))
        else:
            # Use local target selection (original logic)
            receiver_list = prepare_list(group.loc[group['EMAIL'] != user['EMAIL']].copy(), number_of_emails, session_track[user['EMAIL']]['avoid'])
            session_track[user['EMAIL']]['avoid'] = list(set(session_track[user['EMAIL']]['avoid'] + [item['EMAIL'] for item in receiver_list]))
        
        proxy_user = user['PROXY_USER']
        proxy_pass = user['PROXY_PASS']
        username = user['EMAIL']
        password = user['EMAIL_PASS']
        name = user['EMAIL']
        FIRSTFROMNAME = user['FIRSTFROMNAME']
        LASTFROMNAME = user['LASTFROMNAME']
        if user['PROXY:PORT'] != ' ':
            proxy_host = user['PROXY:PORT'].split(':')[0]
            proxy_port = int(user['PROXY:PORT'].split(':')[1])
        else:
            proxy_host = ''
            proxy_port = ''
        if var.cancel:
            break
        while var.thread_open >= var.limit_of_thread:
            time.sleep(1)
        SMTP_Centralized(threadID=index, name=name, proxy_host=proxy_host, proxy_port=proxy_port, proxy_user=proxy_user, proxy_pass=proxy_pass, user=username, password=password, FIRSTFROMNAME=FIRSTFROMNAME, LASTFROMNAME=LASTFROMNAME, targets=receiver_list, delay_start=phase['delay_start'], delay_end=phase['delay_end'], total_email_to_be_sent=total_email_to_be_sent, use_centralized=server_client.is_centralized_mode()).start()
    while var.thread_open != 0:
        time.sleep(1)
    return True


def prepare_list(input_data, quantity, avoid):
    global phase_email_list
    avoid = list(set(phase_email_list + avoid))
    len_input_data = len(input_data)
    len_avoid = len(avoid)

    if len_input_data - len_avoid >= quantity:
        for item in avoid:
            input_data = input_data.loc[input_data["EMAIL"] != item]
    else:
        if len_input_data >= len_avoid:
            while True:
                if len(input_data) == quantity:
                    break
                input_data = input_data.loc[input_data["EMAIL"]
                                            != avoid[random.randint(0, len_avoid - 1)]]

    input_data = input_data.sample(quantity)

    phase_email_list = phase_email_list + input_data["EMAIL"].tolist()
    phase_email_list = list(set(phase_email_list))

    return input_data.to_dict('records')

def cache_dump(phase, time_str):
    try:
        data = {'phase_completed': phase, 'session_track': session_track, 'next_phase_in': time_str}
        with open('wum_config/cache.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)
        print('cache updated')
    except Exception as e:
        print('Exeception occured at cache_dump : {}'.format(e))
        alert(text='Exeception occured at cache_dump : {}'.format(e), title='Alert', button='OK')

def show_report(error_list_q):
    while not error_list_q.empty():
        GUI.signal.s.emit(error_list_q.get(), False)

def wait_(phase, next_phase_in):
    while datetime.now() < next_phase_in:
        if var.cancel == True:
            break
        difference = next_phase_in - datetime.now()
        differenceInHours = difference.total_seconds() / 3600
        GUI.label_status.setText('Phase {} in {} hours'.format(phase, round(differenceInHours, 2)))
        progress_print(phase, 0, 'In {} hours'.format(round(differenceInHours, 2)))
        time.sleep(1)

# report textbrowser true for green and false for red
# GUI.signal.s.emit("Phase {} starting...".format(key), False)
