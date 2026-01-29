#!/usr/bin/env python3
"""
Asynchronous Reply System for WUM
Continuously monitors inbox and sends replies independently from sending phases
"""

import threading
import time
import random
from datetime import datetime, timedelta
import var
import imap
from smtp import Reply_SMTP
import queue
import server_client


class AsyncReplyManager:
    """Manages continuous inbox monitoring and automatic replies"""
    
    def __init__(self):
        self.running = False
        self.monitor_thread = None
        self.reply_threads = {}  # email -> thread
        self.last_check = {}     # email -> datetime
        self.check_interval = 300  # 5 minutes between checks
        self.reply_queue = queue.Queue()
        
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
                        delay = random.randint(30, 120)  # 30-120 seconds
                        time.sleep(delay)
                        
                        if var.cancel:
                            break
                        
                        self._check_inbox_async(user)
                        self.last_check[email] = current_time
                
                # Sleep before next round of checks
                time.sleep(60)  # Check every minute for accounts that need checking
                
            except Exception as e:
                print(f"Error in async reply monitor: {e}")
                time.sleep(30)  # Wait before retrying
    
    def _check_inbox_async(self, user):
        """Check inbox for a specific user (non-blocking)"""
        try:
            email = user['EMAIL']
            
            # Create a simplified session track for this account
            mock_session_track = {
                email: {"send_info": []}  # We'll get this from server if centralized
            }
            
            # If centralized mode, we don't have local send_info
            # The reply system will need to work differently
            if server_client.is_centralized_mode():
                # In centralized mode, we look for any emails that could be replies
                # rather than specific ones we sent
                mock_session_track[email]["send_info"] = [
                    {"EMAIL": email, "subject": None, "date": None}
                ]
            
            # Use existing IMAP logic but in async mode
            temp_group = var.group[var.group['EMAIL'] == email]
            
            # Run inbox check
            error_queue, total_moved = imap.main(temp_group, mock_session_track)
            
            # Process any found emails for replies
            while not imap.email_q.empty():
                email_info = imap.email_q.get()
                
                # Add to reply queue with randomized delay
                reply_delay = random.randint(300, 1800)  # 5-30 minutes
                reply_time = datetime.now() + timedelta(seconds=reply_delay)
                
                reply_task = {
                    'user': user,
                    'email_info': email_info,
                    'reply_time': reply_time
                }
                
                self.reply_queue.put(reply_task)
                print(f"Queued reply for {email} -> {email_info['reciever']} (reply in {reply_delay//60} minutes)")
            
        except Exception as e:
            print(f"Error checking inbox for {user['EMAIL']}: {e}")
    
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
                ready_replies = [r for r in pending_replies if r['reply_time'] <= current_time]
                pending_replies = [r for r in pending_replies if r['reply_time'] > current_time]
                
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
            user = reply_task['user']
            email_info = reply_task['email_info']
            
            # Create reply targets list
            reply_targets = [{
                'reciever': email_info['reciever'],
                'subject': email_info['subject'],
                'msg_id': email_info['msg_id']
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
            print(f"✓ Sent async reply: {username} -> {email_info['reciever']}")
            
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

