from enum import Enum


class Country(str, Enum):
    POLAND = "Poland"
    SWEDEN = "Sweden"
    USA = "USA"


class Protocol(str, Enum):
    XRAY = "Xray"
    AWG = "AWG"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentType(str, Enum):
    NEW_SUB = "new_sub"
    RENEWAL = "renewal"
    CRYPTO = "crypto"
    CARD = "card"


class PlanType(str, Enum):
    BASE = "base"
    PREMIUM = "premium"
    MONTH_1 = "1_month"
    MONTH_3 = "3_months"
    MONTH_6 = "6_months"
    YEAR_1 = "1_year"


class RefundTicketStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    CLOSED = "closed"


class KeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    PENDING_SYNC = "pending_sync"


class NotificationPreference(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
