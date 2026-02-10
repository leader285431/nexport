# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

from frappe.model.document import Document

from nexport.utils import compute_line_totals


class NexPortSalesOrder(Document):
	def validate(self) -> None:
		compute_line_totals(self)
