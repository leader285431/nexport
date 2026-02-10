from enum import StrEnum


# ──────────────────────────── General ────────────────────────────
CURRENCIES = ["THB", "USD", "CNY"]
GAP_DEADLINE_DAYS = 30
DEFAULT_MARKUP_MULTIPLIER = 1.0
STOCK_ALERT_THRESHOLD_DAYS = 90
MAX_EXCHANGE_RATE_DEVIATION = 0.1


# ──────────────────────────── Status Enums ────────────────────────────
class QuoteStatus(StrEnum):
	DRAFT = "Draft"
	SENT = "Sent"
	ACCEPTED = "Accepted"
	REJECTED = "Rejected"
	EXPIRED = "Expired"


class POStatus(StrEnum):
	DRAFT = "Draft"
	ORDERED = "Ordered"
	SHIPPED = "Shipped"
	RECEIVED = "Received"
	CLOSED = "Closed"


class InvoiceStatus(StrEnum):
	UNPAID = "Unpaid"
	PARTIAL = "Partial"
	PAID = "Paid"
	OVERDUE = "Overdue"


class InvoiceType(StrEnum):
	AP = "AP"
	AR = "AR"


class EntityType(StrEnum):
	SUPPLIER = "Supplier"
	CUSTOMER = "Customer"


class PriceHistoryType(StrEnum):
	PURCHASE = "PURCHASE"
	REVALUATION = "REVALUATION"
	DECLARED = "DECLARED"
	ADJUSTMENT = "ADJUSTMENT"


class CostType(StrEnum):
	PHYSICAL = "PHYSICAL"
	DECLARED = "DECLARED"
