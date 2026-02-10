# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class NexPortInvoice(Document):
	def validate(self) -> None:
		self._set_entity_type()

	def _set_entity_type(self) -> None:
		"""Auto-set entity_type based on invoice type."""
		if self.type == "AP":
			self.entity_type = "Supplier"
		elif self.type == "AR":
			self.entity_type = "Customer"
