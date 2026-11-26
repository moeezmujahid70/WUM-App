"""AI text generation for WUM.

All AI requests go to the Gmonster server (POST ``verify/ai_response``), which
picks the provider (OpenAI / DeepSeek) and holds the provider keys, so WUM never
needs an API key of its own.
"""

import logging

import requests

logger = logging.getLogger('ai_client')


class AIError(RuntimeError):
    """AI generation failed; the message is safe to log."""


def _config():
    import var
    return var


def _server_prompt(prompt_text, system_prompt):
    # The server endpoint takes a single prompt, so the instructions go in front.
    if not system_prompt:
        return prompt_text
    return '{}\n\n{}'.format(system_prompt.strip(), prompt_text)


def _server_error(response):
    try:
        data = response.json()
    except Exception:
        data = None
    if isinstance(data, dict):
        for key in ('message', 'error', 'error_code'):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return 'HTTP {}'.format(response.status_code)


def _generate_via_server(prompt_text, system_prompt, config, session):
    password = getattr(config, 'login_password', '') or ''
    email = getattr(config, 'login_email', '') or ''
    if not email or not password:
        raise AIError('Not signed in to the Gmonster server; sign in again to use AI mode.')
    try:
        response = session.post(
            config.api + 'verify/ai_response',
            json={
                'email': email,
                'password': password,
                'machine_uuid': getattr(config, 'login_machine_uuid', '') or '',
                'processor_id': getattr(config, 'login_processor_id', '') or '',
                'prompt': _server_prompt(prompt_text, system_prompt),
            },
            timeout=getattr(config, 'openai_timeout', 45) or 45,
        )
    except requests.RequestException as exc:
        raise AIError('Could not reach the AI server: {}'.format(type(exc).__name__)) from exc

    if not response.ok:
        raise AIError('AI server error: {}'.format(_server_error(response)))
    try:
        data = response.json()
    except Exception as exc:
        raise AIError('AI server sent an unexpected response') from exc
    if not isinstance(data, dict):
        raise AIError('AI server sent an unexpected response')
    status = data.get('status')
    if status is not None and status != 'ok':
        raise AIError('AI server error: {}'.format(_server_error(response)))
    answer = data.get('answer')
    if not isinstance(answer, str) or not answer.strip():
        raise AIError('AI server returned an empty answer')
    return answer


def generate_text(prompt_text, system_prompt=None, *, config=None, session=requests):
    """Return generated text, or raise AIError."""
    config = config or _config()
    return _generate_via_server(prompt_text, system_prompt, config, session)
