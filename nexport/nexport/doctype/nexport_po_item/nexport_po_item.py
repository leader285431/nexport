# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class NexPortPOItem(Document):
	def validate(self) -> None:
		if (self.quantity or 0) <= 0:
			frappe.throw(f"Row {self.idx}: Quantity must be greater than 0")
		if (self.unit_price or 0) < 0:
			frappe.throw(f"Row {self.idx}: Unit Price cannot be negative")
