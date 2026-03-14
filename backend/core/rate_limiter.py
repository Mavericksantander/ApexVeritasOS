from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

rate_window_minutes = max(1, settings.AVOS_RATE_WINDOW // 60)
rate_limit_str = f"{settings.AVOS_RATE_LIMIT}/{rate_window_minutes} minute"
limiter = Limiter(key_func=get_remote_address)
