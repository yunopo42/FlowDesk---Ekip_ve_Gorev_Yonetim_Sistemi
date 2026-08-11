from datetime import datetime, timezone


def utc_now():
    """Veritabanında kullanılmak üzere uyarısız, naive UTC zamanı üretir."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
