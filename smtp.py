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
import os
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
import requests
from pyautogui import alert, password, confirm
from main import GUI
import imap
import json
import re
from datetime import datetime, timedelta
error_list = queue.Queue()
total_email_sent_count = 0
phase_email_list = list()
session_track = {}
logger = var.logging
logger.getLogger('requests').setLevel(var.logging.WARNING)

AI_TEMPLATE_PLACEHOLDER = '__WUM_GPT_BODY__'
REPLY_TEMPLATE_PLACEHOLDER = '__WUM_GPT_REPLY_BODY__'
REPLY_PROMPT_PLACEHOLDER = 'THE INCOMING EMAIL SHOULD BE HERE'
REPLY_EMAIL_PLACEHOLDER = 'GPT MESSAGE OF PROMPT2 COMES HERE'
AI_EMAIL_PLACEHOLDER = 'GPT MESSAGE COMES HERE'

_prompt_template_cache = None
_email_template_cache = None
_reply_prompt_template_cache = None
_reply_email_template_cache = None

def _resolve_prompt_template():
    global _prompt_template_cache
    if _prompt_template_cache is None:
        prompt_path = getattr(var, 'ai_prompt_path', '') or os.path.join(var.db_base_dir, 'PROMPT1.txt')
        try:
            _prompt_template_cache = Path(prompt_path).read_text(encoding='utf-8')
        except Exception as exc:
            raise RuntimeError('Unable to load AI prompt template: {}'.format(exc))
    return _prompt_template_cache

def _resolve_email_template():
    global _email_template_cache
    if _email_template_cache is None:
        template_path = getattr(var, 'ai_email_template_path', '') or os.path.join(var.db_base_dir, 'EMAIL1.txt')
        try:
            _email_template_cache = Path(template_path).read_text(encoding='utf-8')
        except Exception as exc:
            raise RuntimeError('Unable to load AI email wrapper template: {}'.format(exc))
    return _email_template_cache

def _resolve_reply_prompt_template():
    global _reply_prompt_template_cache
    if _reply_prompt_template_cache is None:
        prompt_path = getattr(var, 'ai_reply_prompt_path', '') or os.path.join(var.db_base_dir, 'PROMPT2.txt')
        try:
            _reply_prompt_template_cache = Path(prompt_path).read_text(encoding='utf-8')
        except Exception as exc:
            raise RuntimeError('Unable to load AI reply prompt template: {}'.format(exc))
    return _reply_prompt_template_cache

def _resolve_reply_email_template():
    global _reply_email_template_cache
    if _reply_email_template_cache is None:
        template_path = getattr(var, 'ai_reply_email_template_path', '') or os.path.join(var.db_base_dir, 'EMAIL2.txt')
        try:
            _reply_email_template_cache = Path(template_path).read_text(encoding='utf-8')
        except Exception as exc:
            raise RuntimeError('Unable to load AI reply wrapper template: {}'.format(exc))
    return _reply_email_template_cache

def _render_prompt(first_name, last_name, to_name):
    template = _resolve_prompt_template()
    return utils.format_email(template, first_name or '', last_name or '', to_name or '')

def _render_reply_prompt(incoming_email, first_name, last_name, to_name):
    template = _resolve_reply_prompt_template()
    prompt = utils.format_email(template, first_name or '', last_name or '', to_name or '')
    incoming = (incoming_email or '').strip() or 'No incoming email body was provided.'
    return prompt.replace(REPLY_PROMPT_PLACEHOLDER, incoming)

def _call_openai(prompt_text, system_prompt=None):
    api_key = getattr(var, 'openai_api_key', '')
    if not api_key:
        raise RuntimeError('OpenAI API key is missing. Set OPENAI_API_KEY or update config.')
    base_url = getattr(var, 'openai_base_url', 'https://api.openai.com/v1').rstrip('/')
    model = getattr(var, 'openai_model', 'gpt-4o-mini')
    timeout = getattr(var, 'openai_timeout', 55.0)
    url = f'{base_url}/chat/completions'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if not system_prompt:
        system_prompt = 'You craft outreach emails. Return ONLY two parts: the first line is the email subject and the remaining lines are the body. Do not add labels or numbering.'
    payload = {
        'model': model,
        'temperature': 0.8,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt_text}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        response_text = getattr(getattr(exc, 'response', None), 'text', '')
        logger.warning('OpenAI request failed (status=%s): %s | response=%s', status_code, exc, (response_text or '')[:500])
        raise
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning('OpenAI response parsing failed: %s', exc, exc_info=True)
        raise RuntimeError('Unexpected response from OpenAI API')

def _parse_openai_response(content, expect_subject=True):
    cleaned = (content or '').strip('\ufeff')
    if not cleaned:
        raise RuntimeError('OpenAI response is empty')
    if not expect_subject:
        lines = cleaned.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and lines[0].lower().startswith('subject:'):
            lines.pop(0)
        if lines:
            first = lines[0]
            if first.lower().startswith('body:'):
                lines[0] = first.split(':', 1)[1].strip()
        body_text = '\n'.join(lines).strip()
        if not body_text:
            raise RuntimeError('OpenAI reply body missing')
        return '', body_text
    lines = cleaned.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        raise RuntimeError('OpenAI response is malformed')
    subject_line = lines[index].strip()
    if subject_line.lower().startswith('subject:'):
        subject_line = subject_line.split(':', 1)[1].strip()
    body_candidates = '\n'.join(lines[index + 1:]).strip()
    if body_candidates.lower().startswith('body:'):
        body_candidates = body_candidates.split(':', 1)[1].strip()
    body_text = body_candidates
    if not body_text:
        raise RuntimeError('Email body missing from OpenAI response')
    subject_line = subject_line.strip() or 'Quick update'
    return subject_line, body_text

def _wrap_body_with_template(body_text, first_name, last_name, to_name):
    template = _resolve_email_template()
    working_template = template.replace(AI_EMAIL_PLACEHOLDER, AI_TEMPLATE_PLACEHOLDER)
    if AI_TEMPLATE_PLACEHOLDER not in working_template:
        working_template = '{}\n\n{}'.format(working_template, AI_TEMPLATE_PLACEHOLDER)
    spun_body = utils.format_email(working_template, first_name or '', last_name or '', to_name or '')
    return spun_body.replace(AI_TEMPLATE_PLACEHOLDER, body_text.strip())

def _wrap_reply_body_with_template(body_text, first_name, last_name, to_name):
    template = _resolve_reply_email_template()
    working_template = template.replace(REPLY_EMAIL_PLACEHOLDER, REPLY_TEMPLATE_PLACEHOLDER)
    if REPLY_TEMPLATE_PLACEHOLDER not in working_template:
        working_template = '{}\n\n{}'.format(working_template, REPLY_TEMPLATE_PLACEHOLDER)
    spun_body = utils.format_email(working_template, first_name or '', last_name or '', to_name or '')
    return spun_body.replace(REPLY_TEMPLATE_PLACEHOLDER, body_text.strip())

def build_ai_email_payload(first_name, last_name, to_name):
    prompt_text = _render_prompt(first_name, last_name, to_name)
    openai_raw = _call_openai(prompt_text)
    subject_line, gpt_body = _parse_openai_response(openai_raw)
    final_body = _wrap_body_with_template(gpt_body, first_name, last_name, to_name)
    return subject_line.strip(), final_body.strip()

def build_ai_reply_body(incoming_email, first_name, last_name, to_name):
    prompt_text = _render_reply_prompt(incoming_email, first_name, last_name, to_name)
    system_prompt = 'You craft thoughtful reply emails. Return ONLY the email body with no greeting, no signature, no emojis, and no subject line.'
    openai_raw = _call_openai(prompt_text, system_prompt=system_prompt)
    _, gpt_body = _parse_openai_response(openai_raw, expect_subject=False)
    final_body = _wrap_reply_body_with_template(gpt_body, first_name, last_name, to_name)
    return final_body.strip()

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

def _sleep_with_cancel(total_seconds, step=0.5):
    end_time = time.monotonic() + max(0, total_seconds)
    while time.monotonic() < end_time:
        if var.cancel:
            return True
        time.sleep(min(step, end_time - time.monotonic()))
    return var.cancel

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

    def _compose_subject_body(self, recipient):
        recipient_name = ''
        recipient_email = 'unknown'
        if isinstance(recipient, dict):
            recipient_name = (recipient.get('FIRSTFROMNAME') or '').strip()
            recipient_email = recipient.get('EMAIL', recipient_email)
        if var.email_mode == 'ai':
            try:
                return build_ai_email_payload(self.FIRSTFROMNAME, self.LASTFROMNAME, recipient_name)
            except Exception as exc:
                self.logger.error('AI email generation failed (%s -> %s): %s', self.user, recipient_email, exc)
        subject_text = utils.format_email(var.compose_email_subject, self.FIRSTFROMNAME, self.LASTFROMNAME, recipient_name)
        body_text = utils.format_email(var.compose_email_body, self.FIRSTFROMNAME, self.LASTFROMNAME, recipient_name)
        return subject_text, body_text

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
                    if _sleep_with_cancel(50):
                        return None
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
                if _sleep_with_cancel(random.randint(self.delay_start, self.delay_end)):
                    break
                if var.cancel:
                    break
                server = self.login()
                if server is None or var.cancel:
                    break
                msg = MIMEMultipart('alternative')
                subject_text, body_text = self._compose_subject_body(item)
                msg['Subject'] = subject_text
                msg['From'] = formataddr((str(Header('{} {}'.format(self.FIRSTFROMNAME, self.LASTFROMNAME), 'utf-8')), self.user))
                msg['To'] = item['EMAIL']
                msg['Date'] = formatdate(localtime=True)
                msg.attach(MIMEText(body_text, 'plain'))
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

class Reply_SMTP(SMTP_):

    def __init__(self, **kwargs):
        super(Reply_SMTP, self).__init__(**kwargs)

    def run(self):
        global total_email_sent_count
        try:
            var.thread_open += 1
            for item in self.targets:
                reciever_df = var.group.loc[var.group['EMAIL'] == item['reciever']]
                if reciever_df.empty:
                    self.logger.warning('Reply target %s not found in group, skipping.', item.get('reciever'))
                    continue
                reciever = reciever_df.to_dict('records')[0]
                if var.cancel:
                    break
                if _sleep_with_cancel(random.randint(self.delay_start, self.delay_end)):
                    break
                if var.cancel:
                    break
                server = self.login()
                if server is None or var.cancel:
                    break
                msg = MIMEMultipart('alternative')
                msg['Subject'] = 'RE: ' + item['subject']
                msg['From'] = formataddr((str(Header('{} {}'.format(self.FIRSTFROMNAME, self.LASTFROMNAME), 'utf-8')), self.user))
                msg['To'] = item['reciever']
                if percent_boolean_gen(30):
                    msg['X-Priority'] = '2'
                msg['Date'] = formatdate(localtime=True)
                reply_body = None
                if var.email_mode == 'ai':
                    try:
                        reply_body = build_ai_reply_body(item.get('body', ''), self.FIRSTFROMNAME, self.LASTFROMNAME, reciever['FIRSTFROMNAME'])
                    except Exception as exc:
                        self.logger.error('AI reply generation failed (%s -> %s): %s', self.user, item.get('reciever'), exc)
                if not reply_body:
                    reply_body = utils.format_email(var.compose_email_body, self.FIRSTFROMNAME, self.LASTFROMNAME, reciever['FIRSTFROMNAME'])
                msg.add_header('In-Reply-To', item['msg_id'])
                msg.add_header('References', item['msg_id'])
                msg.attach(MIMEText(reply_body, 'plain'))
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
        user_df = var.group.loc[var.group['EMAIL'] == key]
        if user_df.empty:
            logger.warning('Reply session user %s missing from current group, skipping.', key)
            continue
        user = user_df.to_dict('records')[0]
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
            if _sleep_with_cancel(1):
                break
        if var.cancel:
            break
        Reply_SMTP(threadID=count, name=name, proxy_host=proxy_host, proxy_port=proxy_port, proxy_user=proxy_user, proxy_pass=proxy_pass, user=username, password=password, FIRSTFROMNAME=FIRSTFROMNAME, LASTFROMNAME=LASTFROMNAME, targets=item['reply_info'], delay_start=phase['delay_start'], delay_end=phase['delay_end'], total_email_to_be_sent=total_email_to_be_replied).start()
    while var.thread_open != 0:
        time.sleep(1)
    return True

def main():
    while not var.cancel:
        var.load_db()

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

        # if len_group >= 26 and len_group % 2 == 0:
        if len_group > 0:
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
                

                
                
                text1 = "Phase {}: Number of emails per account set to {}".format(key, number_of_emails)
                status_print(print_text=text1, textbrowser=[text1, True])

                mode_label = 'AI' if getattr(var, 'email_mode', 'canned') == 'ai' else 'Canned'
                mode_text = "Phase {}: Mode set to {}".format(key, mode_label)
                status_print(print_text=mode_text, textbrowser=[mode_text, True])

                

                text = "Phase {} sending : 0/{}".format(
                    key, len(group) * number_of_emails)
                status_print(label_text=text)

                # NEW: Progress tracking for sending phase start
                progress_print(key, 0, "Sending")

                # Reinitialize session_track with all emails from group
                for email in group["EMAIL"].tolist():
                    if email not in session_track:
                        session_track[email] = {
                            "avoid": [],
                            "send_info": [],
                            "reply_info": []
                        }

                phase_email_list = []
                sending(item, group, len(group) * number_of_emails, number_of_emails)
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

                time.sleep(15)

                if var.cancel:
                    break

                text = "Phase {}: checking inbox and spam".format(key)
                status_print(label_text=text, print_text=text,
                             textbrowser=[text, True])

                temp_q, total_email_moved = imap.main(group, session_track)
                # for k, i in session_track.items():
                #     print(k , i)

                text = "Phase {}: checking inbox and spam - Done.\nTotal Email Moved From Spam: {}".format(
                            key, total_email_moved)
                status_print(label_text=text, print_text=text,
                             textbrowser=[text, True])
                status_print(
                    textbrowser=["*** Phase {} collection error list ***".format(int(key)), False])
                show_report(temp_q)

                time.sleep(15)

                if var.cancel:
                    break



                status_print(textbrowser=[
                    "Total email received - {}".format(imap.total_email_to_be_replied), True])
                text = "Phase {} Replying : 0/{}".format(
                    key, imap.total_email_to_be_replied)
                status_print(label_text=text)

                # NEW: Progress tracking for replying phase start
                progress_print(key, 0, "Replying")

                total_email_sent_count = 0
                var.thread_open = 0
                reply(item, imap.total_email_to_be_replied)
                status_print(
                    textbrowser=["*** Phase {} replying error list ***".format(int(key)), False])
                show_report(error_list)

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
            alert(text="Database should contain at least 1 email",
                  title="Alert", button="OK")
            break

    GUI.startButton.setEnabled(True)
    GUI.cancelButton.setEnabled(False)

    text = "Session ended"
    status_print(label_text=text, print_text=text, textbrowser=[text, True])

def sending(phase, group, total_email_to_be_sent, number_of_emails):
    for index, user in group.iterrows():
        # Initialize session_track entry if it doesn't exist
        if user['EMAIL'] not in session_track:
            session_track[user['EMAIL']] = {
                "avoid": [],
                "send_info": [],
                "reply_info": []
            }
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
            if _sleep_with_cancel(1):
                break
        if var.cancel:
            break
        SMTP_(threadID=index, name=name, proxy_host=proxy_host, proxy_port=proxy_port, proxy_user=proxy_user, proxy_pass=proxy_pass, user=username, password=password, FIRSTFROMNAME=FIRSTFROMNAME, LASTFROMNAME=LASTFROMNAME, targets=receiver_list, delay_start=phase['delay_start'], delay_end=phase['delay_end'], total_email_to_be_sent=total_email_to_be_sent).start()
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
