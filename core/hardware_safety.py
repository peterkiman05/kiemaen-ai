"""Safety boundary for Android hardware actions returned by an AI model.

AI output is untrusted data. This module deliberately blocks shell-command
markers; device actions must later be implemented as explicit, locally
allow-listed intents with user confirmation.
"""
import re

_EXEC_MARKER = re.compile(r"\[EXEC\s*:(.*?)\]", re.IGNORECASE | re.DOTALL)
_BLOCKED_MESSAGE = "[Hardware action blocked: AI-generated shell commands are not executed.]"


def block_untrusted_hardware_actions(text: str) -> str:
    """Remove every AI-generated EXEC marker without running its contents."""
    if not isinstance(text, str):
        return ""
    return _EXEC_MARKER.sub(_BLOCKED_MESSAGE, text).strip()
