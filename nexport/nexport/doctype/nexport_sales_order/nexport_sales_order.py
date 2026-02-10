# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

from frappe.model.document import Document


class NexPortSalesOrder(Document):
	def validate(self) -> None:
		self._compute_totals()

	def _compute_totals(self) -> None:
		total = 0.0
		for row in self.items:
			row.amount = (row.quantity or 0) * (row.unit_price or 0)
			total += row.amount
		self.total_amount = total
