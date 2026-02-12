# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class PriceHistory(Document):
	def validate(self) -> None:
		if (self.thb_unit_price or 0) < 0:
			frappe.throw(f"Row {self.idx}: THB Unit Price cannot be negative")
		if self.exchange_rate and self.exchange_rate <= 0:
			frappe.throw(f"Row {self.idx}: Exchange Rate must be positive")
