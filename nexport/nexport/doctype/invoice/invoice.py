# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

from frappe.model.document import Document

from nexport.services.order_service import validate_invoice
from nexport.services.finance_service import enqueue_revaluation_on_payment
from nexport.services.payment_service import generate_payment_schedule

AP_TYPES = frozenset({"AP", "AP (Accounts Payable)"})


class Invoice(Document):
	def before_insert(self) -> None:
		validate_invoice(self, for_before_insert=True)

	def validate(self) -> None:
		validate_invoice(self, for_before_insert=False)
		# Auto-populate payment schedule for new documents with payment_terms set
		if self.payment_terms and not self.payment_schedule and not self.is_new():
			generate_payment_schedule(self)

	def on_update(self) -> None:
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.type not in AP_TYPES:
			return
		if old_status == "Paid" or self.status != "Paid":
			return
		if self.is_rate_finalized:
			return
		enqueue_revaluation_on_payment(self.name)

		# Generate payment schedule when payment terms change
		old_terms = previous.payment_terms if previous else None
		if self.payment_terms and self.payment_terms != old_terms:
			generate_payment_schedule(self)
