# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class DNItem(Document):
	def validate(self) -> None:
		if (self.quantity or 0) <= 0:
			frappe.throw(f"Row {self.idx}: Quantity must be greater than 0")
