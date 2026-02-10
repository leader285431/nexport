# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class NexPortQuote(Document):
	def validate(self) -> None:
		self._compute_totals()

	def _compute_totals(self) -> None:
		total = 0.0
		for row in self.items:
			row.amount = (row.quantity or 0) * (row.unit_price or 0)
			total += row.amount
		self.total_amount = total

	@frappe.whitelist()
	def create_sales_order(self) -> str:
		"""Convert accepted quote to Sales Order."""
		if self.status != "Accepted":
			frappe.throw("Only accepted quotes can be converted to Sales Orders")

		so = frappe.new_doc("NexPort Sales Order")
		so.customer = self.customer
		so.quote = self.name
		so.currency = self.currency

		for row in self.items:
			so.append("items", {
				"item": row.item,
				"quantity": row.quantity,
				"unit_price": row.unit_price,
			})

		so.insert()
		return so.name
