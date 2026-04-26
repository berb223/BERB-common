"""1Password-based secret resolution.

See :mod:`berb_common.secrets.onepassword` for the raw CLI wrapper, and
:mod:`berb_common.secrets.resolve` for higher-level resolution with caching.
"""

from berb_common.secrets.onepassword import (
    OpReadError,
    clear_op_cache,
    clear_op_disk_cache,
    read_op_secret,
    try_read_op_secret,
)
from berb_common.secrets.resolve import (
    clear_secret_cache,
    resolve_secret,
)

__all__ = [
    "OpReadError",
    "clear_op_cache",
    "clear_op_disk_cache",
    "clear_secret_cache",
    "read_op_secret",
    "resolve_secret",
    "try_read_op_secret",
]
