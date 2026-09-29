"""Rule-based decision: does this memory stay on the device or may it sync?"""
import re

from config import SENSITIVE_KEYWORDS

_RX = re.compile(r"\b(" + "|".join(re.escape(k) for k in SENSITIVE_KEYWORDS) + r")\b", re.I)


def classify(text: str, tags: str = "", force_local: bool = False) -> tuple[bool, str]:
    """Returns (local_only, reason)."""
    if force_local:
        return True, "marked local-only by user"
    m = _RX.search(f"{text} {tags}")
    if m:
        return True, f"contains sensitive keyword '{m.group(1).lower()}'"
    return False, ""
