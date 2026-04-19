"""Mai CLI - Safe exec check module.

v1.1.0
"""

import re


DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=",
    r":\(\)\{",
    r"curl.*\|.*sh",
    r"wget.*\|.*sh",
    r"chmod\s+-R\s+777",
    r">\s*/dev/sd",
    r"mkfs",
    r"systemctl\s+stop",
    r"shutdown",
]


def exec_safe_check(cmd: str) -> bool:
    """Return True if command is safe, False if it matches dangerous patterns."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False
    return True
