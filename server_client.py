#!/usr/bin/env python3
"""
Server Client Module for WUM
Handles communication with the centralized email warming orchestrator
"""

import requests
import uuid
from datetime import datetime
import time
from typing import List, Dict, Optional
import var


class WarmingServerClient:
    """Client for communicating with the warming orchestrator server"""
    
    def __init__(self, server_url: str = None, subscriber_email: str = None):
        self.server_url = server_url or var.api  # Use existing API from var.py
        self.subscriber_email = subscriber_email or var.login_email
        self.client_id = str(uuid.uuid4())
        self.session = requests.Session()
        self.session.timeout = 30
        
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
            
            response = self.session.post(url, json=data)
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
            
            response = self.session.get(url, params=params)
            
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
    
    def update_phase(self, email: str, phase: int, send_quota: int, receive_quota: int = None) -> Dict:
        """Update account phase and quotas"""
        try:
            url = f"{self.server_url}warming/update_phase"
            data = {
                'email': email,
                'phase': phase,
                'send_quota': send_quota,
                'receive_quota': receive_quota or send_quota  # Self-balancing
            }
            
            response = self.session.post(url, json=data)
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
            
            response = self.session.post(url, json=data)
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
            response = self.session.get(url)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get stats: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"✗ Stats error: {e}")
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
                print(f"Could not get target for {sender_email}: {target_result}")
                break
            
            if 'target_email' in target_result:
                # Convert to format expected by existing SMTP code
                target_info = {
                    'EMAIL': target_result['target_email'],
                    'FIRSTFROMNAME': 'User',  # Default values - server doesn't track these
                    'LASTFROMNAME': 'Name'
                }
                targets.append(target_info)
            
            # Brief delay to avoid overwhelming server
            time.sleep(0.1)
        
        return targets


# Global instance - will be initialized by smtp.py
warming_client: Optional[WarmingServerClient] = None
target_provider: Optional[CentralizedTargetProvider] = None


def initialize_warming_client():
    """Initialize the global warming client instance"""
    global warming_client, target_provider
    
    try:
        warming_client = WarmingServerClient()
        target_provider = CentralizedTargetProvider(warming_client)
        
        # Register all local accounts with the server
        accounts = []
        for index, user in var.group.iterrows():
            accounts.append({
                'email': user['EMAIL'],
                'phase': 1,  # Start at phase 1
                'send_quota': 1,  # Will be updated per phase
                'receive_quota': 1
            })
        
        if accounts:
            result = warming_client.register_accounts(accounts)
            if 'error' in result:
                print(f"Failed to register accounts: {result['error']}")
                return False
            else:
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
        return target_provider.prepare_list(sender_email, quantity, phase)
    except Exception as e:
        print(f"Error getting centralized targets: {e}")
        return []


def report_email_sent(sender_email: str, target_email: str, subject: str = '', message_id: str = ''):
    """Report sent email to server"""
    if warming_client:
        warming_client.report_sent(sender_email, target_email, subject, message_id)


def update_phase_on_server(email: str, phase: int, send_quota: int):
    """Update phase and quota on server"""
    if warming_client:
        return warming_client.update_phase(email, phase, send_quota)
    return {'error': 'Warming client not available'}

