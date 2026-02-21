# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class Opportunity(Document):
	def before_insert(self) -> None:
		if not self.status:
			self.status = "Prospecting"

	@frappe.whitelist()
	def create_quote(self) -> str:
		"""Convert this Opportunity to a Quote. Returns the new Quote name."""
		frappe.has_permission("Quote", ptype="create", raise_exception=True)
		quote = frappe.get_doc({
			"doctype": "Quote",
			"customer": self.customer,
			"items": [
				{
					"doctype": "Quote Item",
					"item": row.item,
					"quantity": row.quantity,
					"unit_price": row.unit_price or 0,
				}
				for row in (self.items or [])
			],
		})
		quote.insert(ignore_permissions=True)
		return quote.name
