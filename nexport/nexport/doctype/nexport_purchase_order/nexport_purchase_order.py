# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class NexPortPurchaseOrder(Document):
	def validate(self) -> None:
		self._compute_totals()
		self._warn_no_invoice()

	def _compute_totals(self) -> None:
		total = 0.0
		for row in self.items:
			row.amount = (row.quantity or 0) * (row.unit_price or 0)
			total += row.amount
		self.total_amount = total

	def _warn_no_invoice(self) -> None:
		"""Warn (not block) if transitioning to Shipped/Received without invoice."""
		if self.status in ("Shipped", "Received") and not self.invoice_id:
			frappe.msgprint(
				"This PO has no linked Invoice. Consider creating an invoice first.",
				indicator="orange",
				title="Missing Invoice",
			)
