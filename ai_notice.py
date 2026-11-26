"""Tell the user, once per run, that AI mode fell back to the canned message."""

import logging
import threading

import ai_client

logger = logging.getLogger('ai_notice')

_lock = threading.Lock()
_notified = False


def reset():
    """Allow one new notice; call when a sending run starts."""
    global _notified
    with _lock:
        _notified = False


def fallback_message(error):
    if isinstance(error, ai_client.AIError):
        reason = str(error)
    else:
        reason = 'an unexpected error while generating the AI text'
    return (
        'AI mode is not working, so WUM is sending the canned message instead.\n\n'
        'Reason: {}\n\nDetails are in the WUM log.'.format(reason)
    )


def report_fallback(error, notify):
    """Call notify(message) the first time AI falls back during a run."""
    global _notified
    with _lock:
        if _notified:
            return
        _notified = True
    try:
        notify(fallback_message(error))
    except Exception:
        logger.warning('Could not show the AI fallback notice', exc_info=True)
