# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

from frappe.model.document import Document


class Lead(Document):
	def before_insert(self) -> None:
		if not self.status:
			self.status = "New"
