# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document

from nexport.constants import QuoteStatus
from nexport.utils import compute_line_totals


class Quote(Document):
	def validate(self) -> None:
		compute_line_totals(self)

	@frappe.whitelist()
	def create_sales_order(self) -> str:
		"""Convert accepted quote to Sales Order."""
		if self.status != QuoteStatus.ACCEPTED:
			frappe.throw("Only accepted quotes can be converted to Sales Orders")

		so = frappe.new_doc("Sales Order")
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
