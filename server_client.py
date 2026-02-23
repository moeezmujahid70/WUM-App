#!/usr/bin/env python3
"""
Server Client Module for WUM
Handles communication with the centralized email warming orchestrator
"""

import requests
import uuid
import time
import threading
from typing import List, Dict, Optional
import var

logger = var.logging.getLogger('server_client')


class WarmingServerClient:
    """Client for communicating with the warming orchestrator server"""

    def __init__(self, server_url: str = None, subscriber_email: str = None):
        self.server_url = var.api  # Use existing API from var.py
        self.subscriber_email = subscriber_email or var.login_email
        self.client_id = str(uuid.uuid4())
        self.session = requests.Session()
        self.timeout = 30  # 30 seconds timeout for all requests

        # Add retry strategy for network reliability
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def register_accounts(self, accounts: List[Dict]) -> Dict:
        """Register email accounts with the warming orchestrator"""
        try:
            url = f"{self.server_url}warming/register_client"
            data = {
                'subscriber_email': self.subscriber_email,
                'client_id': self.client_id,
                'accounts': accounts
            }

            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()
            print(f"✓ Registered {len(accounts)} accounts with warming server")
            return result

        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to register accounts: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ Registration error: {e}")
            return {'error': str(e)}

    def get_target(self, sender_email: str, phase: int = None) -> Optional[Dict]:
        """Get next target email for sender"""
        try:
            url = f"{self.server_url}warming/get_target"
            params = {'sender_email': sender_email}
            if phase:
                params['phase'] = phase

            response = self.session.get(
                url, params=params, timeout=self.timeout)

            if response.status_code == 404:
                print(f"No targets available for {sender_email}")
                return None
            elif response.status_code == 429:
                result = response.json()
                print(f"Send quota exhausted for {sender_email}: {result}")
                return result

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get target for {sender_email}: {e}")
            return None
        except Exception as e:
            print(f"✗ Target request error: {e}")
            return None

    def update_phase(self, email: str, phase: int, send_quota: int, receive_quota: int = 5) -> Dict:
        """Update account phase and quotas"""
        try:
            url = f"{self.server_url}warming/update_phase"
            data = {
                'email': email,
                'phase': phase,
                'send_quota': send_quota,
                'receive_quota': receive_quota  # Self-balancing
            }

            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to update phase for {email}: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ Phase update error: {e}")
            return {'error': str(e)}

    def report_sent(self, sender_email: str, target_email: str, subject: str = '', message_id: str = '') -> Dict:
        """Report that an email was successfully sent"""
        try:
            url = f"{self.server_url}warming/report_sent"
            data = {
                'sender_email': sender_email,
                'target_email': target_email,
                'subject': subject,
                'message_id': message_id
            }

            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to report sent email: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ Report error: {e}")
            return {'error': str(e)}

    def get_stats(self) -> Dict:
        """Get warming statistics"""
        try:
            url = f"{self.server_url}warming/stats"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get stats: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ Stats error: {e}")
            return {'error': str(e)}

    def heartbeat(self, accounts: List[Dict], mark_inactive_missing: bool = False) -> Dict:
        """Update account last_activity and keep client presence active."""
        try:
            url = f"{self.server_url}warming/heartbeat"
            data = {
                'client_id': self.client_id,
                'accounts': accounts,
                'mark_inactive_missing': mark_inactive_missing
            }
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed heartbeat update: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ Heartbeat error: {e}")
            return {'error': str(e)}

    def deregister_client(self, accounts: List[Dict]) -> Dict:
        """Mark current client accounts inactive on stop/cancel."""
        try:
            url = f"{self.server_url}warming/deregister_client"
            data = {
                'subscriber_email': self.subscriber_email,
                'client_id': self.client_id,
                'accounts': accounts
            }
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to deregister accounts: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ Deregister error: {e}")
            return {'error': str(e)}

    def report_received(self, recipient_email: str, sender_email: str, message_id: str = '', received_at: str = '') -> Dict:
        """Report an incoming email and get pool-sender eligibility."""
        try:
            url = f"{self.server_url}warming/report_received"
            data = {
                'client_id': self.client_id,
                'recipient_email': recipient_email,
                'sender_email': sender_email,
                'message_id': message_id,
                'received_at': received_at
            }
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to report received email: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ report_received error: {e}")
            return {'error': str(e)}

    def report_replied(self, recipient_email: str, sender_email: str, message_id: str, replied_at: str = '') -> Dict:
        """Report a sent reply with pool-only enforcement on server."""
        try:
            url = f"{self.server_url}warming/report_replied"
            data = {
                'client_id': self.client_id,
                'recipient_email': recipient_email,
                'sender_email': sender_email,
                'message_id': message_id,
                'replied_at': replied_at
            }
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to report replied email: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ report_replied error: {e}")
            return {'error': str(e)}

    def claim_reply(self, recipient_email: str, sender_email: str, message_id: str, subject: str) -> Dict:
        """Atomically claim reply permission for this client/message."""
        try:
            url = f"{self.server_url}warming/claim_reply"
            data = {
                'recipient_email': recipient_email,
                'sender_email': sender_email,
                'message_id': message_id,
                'subject': subject,
                'client_id': self.client_id
            }
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to claim reply permission: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ claim_reply error: {e}")
            return {'error': str(e)}


class CentralizedTargetProvider:
    """Provides targets using the centralized server instead of local database"""

    def __init__(self, server_client: WarmingServerClient):
        self.server_client = server_client

    def prepare_list(self, sender_email: str, quantity: int, phase: int) -> List[Dict]:
        """Prepare target list by requesting from server (replaces local prepare_list)"""
        targets = []

        for _ in range(quantity):
            target_result = self.server_client.get_target(sender_email, phase)

            if not target_result or 'error' in target_result:
                print(
                    f"Could not get target for {sender_email}: {target_result}")
                break

            if 'target_email' in target_result:
                # Convert to format expected by existing SMTP code
                target_info = {
                    'EMAIL': target_result['target_email'],
                    'FIRSTFROMNAME': 'User',  # Default values - server doesn't track these
                    'LASTFROMNAME': 'Name'
                }
                targets.append(target_info)
                logger.info(
                    'Centralized target selected | sender=%s | phase=%s | target=%s',
                    sender_email,
                    phase,
                    target_result.get('target_email', '')
                )

            # Brief delay to avoid overwhelming server
            time.sleep(0.1)

        logger.info(
            'Centralized selection summary | sender=%s | phase=%s | requested=%s | selected=%s',
            sender_email,
            phase,
            quantity,
            len(targets)
        )

        return targets


# Global instance - will be initialized by smtp.py
warming_client: Optional[WarmingServerClient] = None
target_provider: Optional[CentralizedTargetProvider] = None
heartbeat_thread: Optional[threading.Thread] = None
heartbeat_stop_event = threading.Event()
registered_accounts_cache: List[Dict] = []
HEARTBEAT_INTERVAL_SECONDS = 120


def _build_accounts_payload_from_group(group=None) -> List[Dict]:
    payload = []
    if group is None:
        group = getattr(var, 'group', None)
    if group is None:
        return payload
    try:
        for _, user in group.iterrows():
            email = (user.get('EMAIL') or '').strip()
            if email:
                payload.append({'email': email})
    except Exception:
        return payload
    return payload


def initialize_warming_client():
    """Initialize the global warming client instance"""
    global warming_client, target_provider, registered_accounts_cache

    try:
        warming_client = WarmingServerClient()
        target_provider = CentralizedTargetProvider(warming_client)

        # Register all local accounts with the server
        accounts = []
        for index, user in var.group.iterrows():
            accounts.append({
                'email': user['EMAIL'],
                'phase': 1,  # Start at phase 1
                'send_quota': 2,  # Will be updated per phase
                'receive_quota': 5  # Self-balancing with send_quota
            })

        if accounts:
            result = warming_client.register_accounts(accounts)
            if 'error' in result:
                print(f"Failed to register accounts: {result['error']}")
                return False
            else:
                registered_accounts_cache = [
                    {'email': item['email']} for item in accounts if item.get('email')]
                print(f"✓ Successfully registered {len(accounts)} accounts")
                return True

    except Exception as e:
        print(f"Failed to initialize warming client: {e}")
        warming_client = None
        target_provider = None
        return False

    return True


def is_centralized_mode():
    """Check if centralized mode is enabled and working"""
    return warming_client is not None and target_provider is not None


def get_centralized_targets(sender_email: str, quantity: int, phase: int) -> List[Dict]:
    """Get targets from centralized server (fallback to local if server unavailable)"""
    if not is_centralized_mode():
        print("Centralized mode not available, falling back to local targets")
        return []

    try:
        targets = target_provider.prepare_list(sender_email, quantity, phase)
        logger.info(
            'get_centralized_targets result | sender=%s | phase=%s | selected_targets=%s',
            sender_email,
            phase,
            [item.get('EMAIL', '') for item in targets]
        )
        return targets
    except Exception as e:
        print(f"Error getting centralized targets: {e}")
        logger.error(
            'get_centralized_targets error | sender=%s | phase=%s | error=%s',
            sender_email,
            phase,
            e
        )
        return []


def report_email_sent(sender_email: str, target_email: str, subject: str = '', message_id: str = ''):
    """Report sent email to server"""
    if warming_client:
        return warming_client.report_sent(sender_email, target_email, subject, message_id)
    return {'error': 'Warming client not available'}


def update_phase_on_server(email: str, phase: int, send_quota: int):
    """Update phase and quota on server"""
    if warming_client:
        return warming_client.update_phase(email, phase, send_quota)
    return {'error': 'Warming client not available'}


def report_received_email(recipient_email: str, sender_email: str, message_id: str = '', received_at: str = '') -> Dict:
    """Proxy for report_received API."""
    if warming_client:
        return warming_client.report_received(recipient_email, sender_email, message_id, received_at)
    return {'error': 'Warming client not available'}


def report_email_replied(recipient_email: str, sender_email: str, message_id: str, replied_at: str = '') -> Dict:
    """Proxy for report_replied API."""
    if warming_client:
        return warming_client.report_replied(recipient_email, sender_email, message_id, replied_at)
    return {'error': 'Warming client not available'}


def claim_reply_permission(recipient_email: str, sender_email: str, message_id: str, subject: str) -> Dict:
    """Proxy for claim_reply API."""
    if warming_client:
        return warming_client.claim_reply(recipient_email, sender_email, message_id, subject)
    return {'error': 'Warming client not available'}


def _heartbeat_loop(interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS):
    while not heartbeat_stop_event.wait(interval_seconds):
        if not is_centralized_mode():
            continue
        accounts = registered_accounts_cache or _build_accounts_payload_from_group()
        if not accounts:
            continue
        result = warming_client.heartbeat(
            accounts, mark_inactive_missing=False)
        if isinstance(result, dict) and 'error' in result:
            print(f"Heartbeat warning: {result['error']}")


def start_heartbeat(interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS) -> bool:
    """Start background heartbeat updates for current registered accounts."""
    global heartbeat_thread
    if not is_centralized_mode():
        return False
    if heartbeat_thread and heartbeat_thread.is_alive():
        return True

    accounts = registered_accounts_cache or _build_accounts_payload_from_group()
    if not accounts:
        print('No accounts available for heartbeat start')
        return False

    initial_result = warming_client.heartbeat(
        accounts, mark_inactive_missing=True)
    if isinstance(initial_result, dict) and 'error' in initial_result:
        print(f"Heartbeat start failed: {initial_result['error']}")
        return False

    heartbeat_stop_event.clear()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        kwargs={'interval_seconds': interval_seconds},
        daemon=True,
        name='WarmingHeartbeat'
    )
    heartbeat_thread.start()
    print(f"✓ Heartbeat started (every {interval_seconds}s)")
    return True


def stop_heartbeat(deregister: bool = False) -> Dict:
    """Stop heartbeat loop and optionally deregister active accounts."""
    global heartbeat_thread
    result = {'status': 'noop'}

    heartbeat_stop_event.set()
    if heartbeat_thread and heartbeat_thread.is_alive():
        heartbeat_thread.join(timeout=3)
    heartbeat_thread = None

    if deregister and is_centralized_mode():
        accounts = registered_accounts_cache or _build_accounts_payload_from_group()
        if accounts:
            result = warming_client.deregister_client(accounts)
            if isinstance(result, dict) and 'error' not in result:
                print('✓ Deregistered accounts from centralized pool')
        return result

    return result
