# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class NexPortPaymentExecution(Document):
	def before_insert(self) -> None:
		"""Set idempotency key and check for duplicates before inserting."""
		self.idempotency_key = (
			f"{self.invoice}|{self.installment}|{self.remittance_reference or ''}"
		)
		self._check_duplicate()

	def _check_duplicate(self) -> None:
		"""Throw if a payment with the same idempotency key already exists."""
		if frappe.db.exists(
			"NexPort Payment Execution", {"idempotency_key": self.idempotency_key}
		):
			frappe.throw(
				frappe._("Duplicate payment: {0}").format(self.idempotency_key)
			)

	def on_submit(self) -> None:
		"""Apply payment when document is submitted."""
		from nexport.services.payment_service import apply_payment_execution
		apply_payment_execution(self)
