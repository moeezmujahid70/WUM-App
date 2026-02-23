#!/usr/bin/env python3
"""
Asynchronous Reply System for WUM
Continuously monitors inbox and sends replies independently from sending phases
"""

import threading
import time
import random
import re
from datetime import datetime, timedelta, timezone
import email as py_email
from email.utils import parseaddr, parsedate_to_datetime
import var
import imap
import imaplib
import proxy_imaplib
import socks
import queue
import server_client


class AsyncReplyManager:
    """Manages continuous inbox monitoring and automatic replies"""

    def __init__(self):
        self.running = False
        self.monitor_thread = None
        self.reply_threads = {}  # email -> thread
        self.last_check = {}     # email -> datetime
        self.check_interval = 200  #
        self.reply_queue = queue.Queue()
        self.queued_or_seen = set()
        self.lookback_days = 7  # How many days back to look for emails when checking inbox

    def start_monitoring(self, group):
        """Start continuous inbox monitoring for all accounts"""
        if self.running:
            print("Async reply monitoring already running")
            return

        self.running = True
        self.group = group.copy()

        # Start main monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="AsyncReplyMonitor"
        )
        self.monitor_thread.start()

        # Start reply processing thread
        self.reply_processor = threading.Thread(
            target=self._process_reply_queue,
            daemon=True,
            name="ReplyProcessor"
        )
        self.reply_processor.start()

        print("✓ Started asynchronous reply monitoring")

    def stop_monitoring(self):
        """Stop continuous inbox monitoring"""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        print("✓ Stopped asynchronous reply monitoring")

    def _monitor_loop(self):
        """Main monitoring loop - checks inboxes continuously"""
        while self.running and not var.cancel:
            try:
                current_time = datetime.now()

                for index, user in self.group.iterrows():
                    if var.cancel:
                        break

                    email = user['EMAIL']

                    # Check if it's time to check this account
                    if (email not in self.last_check or
                            (current_time - self.last_check[email]).total_seconds() >= self.check_interval):

                        # Add some randomization to avoid pattern detection
                        delay = random.randint(20, 60)  # 30-120 seconds
                        time.sleep(delay)

                        if var.cancel:
                            break

                        self._check_inbox_async(user)
                        self.last_check[email] = current_time

                # Sleep before next round of checks
                # Check every minute for accounts that need checking
                time.sleep(60)

            except Exception as e:
                print(f"Error in async reply monitor: {e}")
                time.sleep(30)  # Wait before retrying

    def _check_inbox_async(self, user):
        """Check inbox for a specific user (non-blocking)"""
        try:
            mailbox_email = (user.get('EMAIL') or '').strip()
            if not mailbox_email:
                return

            candidates = self._collect_inbox_candidates(user)
            queued_count = 0

            for email_info in candidates:
                sender_email = (email_info.get('reciever')
                                or '').strip().lower()
                msg_id = (email_info.get('msg_id') or '').strip()
                dedupe_key = '{}|{}|{}'.format(
                    mailbox_email.lower(), sender_email, msg_id or email_info.get('subject', ''))
                if dedupe_key in self.queued_or_seen:
                    continue

                # In centralized mode, validate sender using server-side pool state.
                if server_client.is_centralized_mode():
                    report_result = server_client.report_received_email(
                        recipient_email=mailbox_email,
                        sender_email=sender_email,
                        message_id=msg_id,
                        received_at=email_info.get('received_at', '')
                    )
                    if isinstance(report_result, dict) and 'error' in report_result:
                        print(
                            f"report_received failed for {mailbox_email} <- {sender_email}: {report_result['error']}")
                        continue
                    is_pool_sender = bool(
                        (report_result or {}).get('is_pool_sender', False))
                    is_currently_active = bool(
                        (report_result or {}).get('is_sender_currently_active_in_pool', False))
                    if not is_pool_sender:
                        print(
                            f"Skipping non-pool sender for {mailbox_email}: {sender_email}")
                        continue
                    if not is_currently_active:
                        print(
                            f"Skipping inactive pool sender for {mailbox_email}: {sender_email}")
                        continue

                    claim_result = server_client.claim_reply_permission(
                        recipient_email=mailbox_email,
                        sender_email=sender_email,
                        message_id=msg_id,
                        subject=(email_info.get('subject') or '')
                    )
                    if isinstance(claim_result, dict) and 'error' in claim_result:
                        print(
                            f"claim_reply failed for {mailbox_email} <- {sender_email}: {claim_result['error']}")
                        continue
                    if not bool((claim_result or {}).get('granted', False)):
                        print(
                            f"Reply claim denied for {mailbox_email} <- {sender_email}: {(claim_result or {}).get('reason', 'not granted')}")
                        continue

                # Add to reply queue with randomized delay
                reply_delay = random.randint(200, 1200)  # 5-30 minutes
                reply_time = datetime.now() + timedelta(seconds=reply_delay)
                reply_task = {
                    'user': user,
                    'email_info': email_info,
                    'reply_time': reply_time
                }
                self.reply_queue.put(reply_task)
                self.queued_or_seen.add(dedupe_key)
                queued_count += 1

            print(
                f"Async inbox check complete for {mailbox_email}. candidates={len(candidates)} queued={queued_count}")

        except Exception as e:
            print(f"Error checking inbox for {user['EMAIL']}: {e}")

    def _collect_inbox_candidates(self, user, max_messages=30):
        """Collect recent inbox messages and transform them into reply candidates."""
        imap_conn = None
        candidates = []
        try:
            mailbox_email = user['EMAIL']
            mailbox_pass = user['EMAIL_PASS']

            regex = re.compile('(?<=@)(\\S+$)')
            mail_domain = regex.findall(mailbox_email)[0]
            mail_vendor = mail_domain.split('.')[0]
            parts = mail_domain.split('.')
            if len(parts) > 2:
                mail_vendor = '.'.join(parts[:-1])
            elif len(parts) == 2:
                mail_vendor = parts[0]
            else:
                mail_vendor = mail_domain
            imap_server = var.mail_server[mail_vendor]['imap']['server']
            imap_port = var.mail_server[mail_vendor]['imap']['port']

            if user.get('PROXY:PORT') and user.get('PROXY:PORT') != ' ':
                proxy_host = user['PROXY:PORT'].split(':')[0]
                proxy_port = int(user['PROXY:PORT'].split(':')[1])
                imap_conn = proxy_imaplib.IMAP(
                    proxy_host=proxy_host,
                    proxy_port=proxy_port,
                    proxy_type=socks.PROXY_TYPE_SOCKS5,
                    proxy_user=user.get('PROXY_USER', ''),
                    proxy_pass=user.get('PROXY_PASS', ''),
                    host=imap_server,
                    port=imap_port,
                    timeout=30
                )
            else:
                imap_conn = imaplib.IMAP4_SSL(imap_server, imap_port)

            imap_conn.login(mailbox_email, mailbox_pass)
            imap_conn.select('INBOX')

            # status, data = imap_conn.search(None, 'UNSEEN')

            since_date = (
                datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).strftime('%d-%b-%Y')
            status, data = imap_conn.search(
                None, 'UNSEEN', 'SINCE', since_date)

            if status != 'OK' or not data or not data[0]:
                return candidates

            message_numbers = data[0].split()[-max_messages:]

            for msg_num in message_numbers:
                fetch_status, fetch_data = imap_conn.fetch(msg_num, '(RFC822)')
                if fetch_status != 'OK' or not fetch_data or not fetch_data[0]:
                    continue

                raw_message = fetch_data[0][1]
                email_message = py_email.message_from_bytes(raw_message)

                sender_email = parseaddr(email_message.get('From', ''))[
                    1].strip().lower()
                if not sender_email or sender_email == mailbox_email.lower():
                    continue

                msg_id = parseaddr(email_message.get(
                    'Message-ID', ''))[1].strip()
                subject = str(py_email.header.make_header(
                    py_email.header.decode_header(
                        email_message.get('Subject', ''))
                ))
                body_text = imap._extract_plain_text_body(email_message)

                received_iso = ''
                try:
                    dt = parsedate_to_datetime(email_message.get('Date'))
                    if dt is not None:
                        received_iso = dt.isoformat()
                except Exception:
                    received_iso = ''

                candidates.append({
                    'reciever': sender_email,
                    'sender': mailbox_email,
                    'subject': subject,
                    'msg_id': msg_id,
                    'body': body_text,
                    'received_at': received_iso
                })

            return candidates
        except Exception as e:
            print(
                f"Error collecting inbox candidates for {user.get('EMAIL', '')}: {e}")
            return candidates
        finally:
            if imap_conn is not None:
                try:
                    imap_conn.close()
                except Exception:
                    pass
                try:
                    imap_conn.logout()
                except Exception:
                    pass

    def _process_reply_queue(self):
        """Process queued replies when their time comes"""
        pending_replies = []

        while self.running and not var.cancel:
            try:
                # Check for new replies
                try:
                    while True:
                        reply_task = self.reply_queue.get_nowait()
                        pending_replies.append(reply_task)
                except queue.Empty:
                    pass

                # Process replies whose time has come
                current_time = datetime.now()
                ready_replies = [
                    r for r in pending_replies if r['reply_time'] <= current_time]
                pending_replies = [
                    r for r in pending_replies if r['reply_time'] > current_time]

                for reply_task in ready_replies:
                    if var.cancel:
                        break
                    self._send_reply(reply_task)

                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                print(f"Error in reply processor: {e}")
                time.sleep(30)

    def _send_reply(self, reply_task):
        """Send a single reply"""
        try:
            from smtp import Reply_SMTP

            user = reply_task['user']
            email_info = reply_task['email_info']

            # Create reply targets list
            reply_targets = [{
                'reciever': email_info['reciever'],
                'subject': email_info['subject'],
                'msg_id': email_info['msg_id'],
                'body': email_info.get('body', '')
            }]

            # Set up SMTP parameters
            proxy_user = user['PROXY_USER']
            proxy_pass = user['PROXY_PASS']
            username = user['EMAIL']
            password = user['EMAIL_PASS']
            FIRSTFROMNAME = user['FIRSTFROMNAME']
            LASTFROMNAME = user['LASTFROMNAME']

            if user['PROXY:PORT'] != ' ':
                proxy_host = user['PROXY:PORT'].split(':')[0]
                proxy_port = int(user['PROXY:PORT'].split(':')[1])
            else:
                proxy_host = ''
                proxy_port = ''

            # Create and start reply thread
            reply_thread = Reply_SMTP(
                threadID=0,
                name=username,
                proxy_host=proxy_host,
                proxy_port=proxy_port,
                proxy_user=proxy_user,
                proxy_pass=proxy_pass,
                user=username,
                password=password,
                FIRSTFROMNAME=FIRSTFROMNAME,
                LASTFROMNAME=LASTFROMNAME,
                targets=reply_targets,
                delay_start=60,    # Reply delay range in seconds (60–300)
                delay_end=300,
                total_email_to_be_sent=1
            )

            reply_thread.start()
            print(
                f"✓ Sent async reply: {username} -> {email_info['reciever']}")

        except Exception as e:
            print(f"Error sending async reply: {e}")


# Global async reply manager instance
async_reply_manager = AsyncReplyManager()


def start_async_replies(group):
    """Start asynchronous reply monitoring"""
    async_reply_manager.start_monitoring(group)


def stop_async_replies():
    """Stop asynchronous reply monitoring"""
    async_reply_manager.stop_monitoring()


def is_async_reply_running():
    """Check if async reply system is running"""
    return async_reply_manager.running
