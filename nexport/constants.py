ROLE_ADMIN = "NexPort Admin"
ROLE_FINANCE = "NexPort Finance"
ROLE_WAREHOUSE = "NexPort Warehouse"
ROLE_PROCUREMENT = "NexPort Procurement"
ROLE_SALES = "NexPort Sales"

CURRENCIES = ["THB", "USD", "CNY"]
GAP_DEADLINE_DAYS = 30
DEFAULT_MARKUP_MULTIPLIER = 1.0
STOCK_ALERT_THRESHOLD_DAYS = 60
MAX_EXCHANGE_RATE_DEVIATION = 0.05

DEFAULT_FALLBACK_CODE = "GEN"
SETTINGS_DOCTYPE = "NexPort Settings"

# Payment Terms & Status
class PaymentTerms:
	NET_30 = "Net 30"
	NET_60 = "Net 60"
	NET_90 = "Net 90"
	INSTALLMENT_3 = "3 Installments"
	INSTALLMENT_6 = "6 Installments"
	IMMEDIATE = "Immediate"
	CUSTOM = "Custom"

class PaymentStatus:
	PENDING = "Pending"
	PAID = "Paid"
	OVERDUE = "Overdue"

PROJECT_DOCTYPE = "Project"
TASK_DOCTYPE = "NexPort Task"
CURRENCY_EXCHANGE_DOCTYPE = "Currency Exchange"
EXCHANGE_RATE_API_BASE = "https://v6.exchangerate-api.com/v6"

MATERIAL_REQUEST_DOCTYPE = "Material Request"
STOCK_RESERVATION_DOCTYPE = "Stock Reservation"


class MaterialRequestStatus:
	OPEN = "Open"
	ORDERED = "Ordered"
	CANCELLED = "Cancelled"


class StockReservationStatus:
	ACTIVE = "Active"
	RELEASED = "Released"
	CANCELLED = "Cancelled"


PAYMENT_PLAN_DOCTYPE = "NexPort Payment Plan"
PAYMENT_EXECUTION_DOCTYPE = "NexPort Payment Execution"
REMINDER_DAYS_FIRST = 7
REMINDER_DAYS_SECOND = 3
REMINDER_DAYS_FINAL = 1

