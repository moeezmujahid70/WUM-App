from pyautogui import alert, password, confirm
global error_list
global total_email_moved
global total_email_to_be_replied
global logger
global email_q
global spam_info
import proxy_imaplib
import socks
import email
import threading
from datetime import datetime
import time
import var
import imaplib
import queue
import re
from main import GUI
import traceback
total_email_moved = 0
total_email_to_be_replied = 0
email_q = queue.Queue()
error_list = queue.Queue()
spam_info = queue.Queue()
logger = var.logging
logger.getLogger('requests').setLevel(var.logging.WARNING)

def _extract_plain_text_body(message):
    """Return the first text/plain payload without attachments."""
    def decode_payload(payload, charset):
        if payload is None:
            return ''
        charset = charset or 'utf-8'
        try:
            return payload.decode(charset, errors='replace')
        except Exception:
            try:
                return payload.decode('utf-8', errors='replace')
            except Exception:
                return payload.decode('latin-1', errors='replace')

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = (part.get('Content-Disposition') or '').lower()
            if content_type == 'text/plain' and 'attachment' not in disposition:
                return decode_payload(part.get_payload(decode=True), part.get_content_charset()).strip()
        payload = message.get_payload(decode=True)
        return decode_payload(payload, message.get_content_charset()).strip()
    payload = message.get_payload(decode=True)
    return decode_payload(payload, message.get_content_charset()).strip()

def status_print(label_text=None, print_text=None, textbrowser=None):
    if label_text:
        GUI.label_status.setText(label_text)
    if print_text:
        print(print_text)
    if textbrowser:
        GUI.signal.s.emit(textbrowser[0], textbrowser[1])

class IMAP_(threading.Thread):

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.threadID = kwargs['threadID']
        self.name = kwargs['name']
        self.setDaemon(True)
        self.proxy_host = kwargs['proxy_host']
        self.proxy_port = kwargs['proxy_port']
        self.proxy_user = kwargs['proxy_user']
        self.proxy_pass = kwargs['proxy_pass']
        self.proxy_type = kwargs['proxy_type']
        self.imap_user = kwargs['imap_user']
        self.imap_pass = kwargs['imap_pass']
        self.FIRSTFROMNAME = kwargs['FIRSTFROMNAME']
        self.LASTFROMNAME = kwargs['LASTFROMNAME']
        self.targets = kwargs['targets']
        self.logger = logger
        try:
            regex = re.compile('(?<=@)(\\S+$)')
            mail_domain = regex.findall(self.imap_user)[0]
            mail_vendor = mail_domain.split('.')[0]
            parts = mail_domain.split('.')
            if len(parts) > 2:
                mail_vendor = '.'.join(parts[:-1])
            elif len(parts) == 2:
                mail_vendor = parts[0]
            else:
                mail_vendor = mail_domain
            self.imap_server = var.mail_server[mail_vendor]['imap']['server']
            self.imap_port = var.mail_server[mail_vendor]['imap']['port']
        except:
            logger.error(f'ImapBase error: {traceback.format_exc()}')
            raise

    def run(self):
        global total_email_moved
        global total_email_to_be_replied
        try:
            var.thread_open += 1
            if self.proxy_host != '':
                imap = proxy_imaplib.IMAP(proxy_host=self.proxy_host, proxy_port=self.proxy_port, proxy_type=self.proxy_type, proxy_user=self.proxy_user, proxy_pass=self.proxy_pass, host=self.imap_server, port=self.imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4_SSL(self.imap_server)
            imap.login(self.imap_user, self.imap_pass)
            for item in self.targets:
                if var.cancel:
                    break
                try:
                    imap.select('[Gmail]/Spam')
                    tmp, data = imap.uid('search', None, 'FROM', item['EMAIL'])
                    uids = data[0]
                    if len(uids) > 0:
                        for uid in uids.split():
                            result = imap.uid('COPY', uid, 'Inbox')
                            if result[0] == 'OK':
                                total_email_moved += 1


                        # spam_info.put(
                        #     f"""Spam Email {total_email_moved+1}:
                        #     receiver: {self.imap_user},
                        #     sender: {item["EMAIL"]},
                        #     subject: {subject}
                        #     """
                        # )

                except Exception as e:
                    text = 'Error at moving from spam {} ({}) - {}'.format(self.imap_user, e, traceback.format_exc())
                    # if 'command CLOSE illegal in state AUTH, only allowed in states SELECTED' in text:
                    #     # print(text)
                    # else:
                    #     error_list.put('At spam - {} - {}'.format(self.imap_user, e))
                        # status_print(print_text=text, textbrowser=[text, False])
                try:
                    imap.select('INBOX')
                    # tmp, data = imap.search(None, 'FROM', item["EMAIL"], "SUBJECT", item["subject"])
                    pattern = re.compile('[^\\w_ ]+', re.UNICODE)
                    filtered_subject = pattern.sub('', item['subject'])
                    tmp, data = imap.search(None, '(FROM "{}" SUBJECT "{}")'.format(item['EMAIL'], filtered_subject))
                    for num in data[0].split():
                        tmp, data = imap.fetch(num, '(UID RFC822)')
                        raw = data[0][0]
                        raw_str = raw.decode('utf-8')
                        uid = raw_str.split()[2]
                        email_message = email.message_from_string(data[0][1].decode())
                        subject = email.header.make_header(email.header.decode_header(email_message['Subject']))
                        subject = str(subject)
                        msg_id = email.utils.parseaddr(email_message['Message-ID'])[1]
                        body_text = _extract_plain_text_body(email_message)
                        email_q.put({'reciever': item['EMAIL'], 'sender': self.imap_user, 'subject': subject, 'msg_id': msg_id, 'body': body_text}.copy())
                        total_email_to_be_replied += 1
                except Exception as e:
                    text = 'Error at email collecting base {} ({})'.format(self.imap_user, e)
                    # if 'command CLOSE illegal in state AUTH, only allowed in states SELECTED' in text:
                    #     # print(text)
                    # else:
                    #     error_list.put('Error at email collecting base - {} - {}'.format(self.imap_user, e))
                        # status_print(print_text=text, textbrowser=[text, False])
            imap.close()
            imap.logout()
        except Exception as e:
            text = 'Error at email collecting final - {} - {}'.format(self.name, e)
            # self.logger.error(text)
            # if 'command CLOSE illegal in state AUTH, only allowed in states SELECTED' in text:
            #     print(text)
            # else:
            #     error_list.put('At collection main final - {} - {}'.format(self.imap_user, e))
                # status_print(print_text=text, textbrowser=[text, False])
        finally:
            var.thread_open -= 1

def main(group, session_track):
    global spam_info
    global total_email_moved
    global error_list
    global total_email_to_be_replied
    error_list = queue.Queue()
    spam_info = queue.Queue()
    count = 0
    total_email_moved = 0
    total_email_to_be_replied = 0
    var.thread_open = 0
    for key, item in session_track.items():
        records = group.loc[group['EMAIL'] == key].to_dict('records')
        if not records:
            logger.warning(f'IMAP main: session key {key} not found in provided group, skipping')
            continue
        user = records[0]
        proxy_type = socks.PROXY_TYPE_SOCKS5
        proxy_user = user['PROXY_USER']
        proxy_pass = user['PROXY_PASS']
        imap_user = user['EMAIL']
        imap_pass = user['EMAIL_PASS']
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
        IMAP_(threadID=count, name=name, proxy_type=proxy_type, proxy_host=proxy_host, proxy_port=proxy_port, proxy_user=proxy_user, proxy_pass=proxy_pass, imap_user=imap_user, imap_pass=imap_pass, FIRSTFROMNAME=FIRSTFROMNAME, LASTFROMNAME=LASTFROMNAME, targets=item['send_info']).start()
        count += 1
    while var.thread_open != 0:
        time.sleep(1)
    while not email_q.empty():
        email_info = email_q.get()
        sender = email_info.get('sender')
        if sender not in session_track:
            logger.warning(f"IMAP main: sender {sender} not in session_track, initializing entry")
            session_track[sender] = {
                "avoid": [],
                "send_info": [],
                "reply_info": []
            }
        session_track[sender]['reply_info'].append({
            'reciever': email_info['reciever'],
            'subject': email_info['subject'],
            'msg_id': email_info['msg_id'],
            'body': email_info.get('body', '')
        }.copy())
    print(total_email_moved, total_email_to_be_replied)
    return (error_list, total_email_moved)