# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document

from nexport.constants import EntityType, InvoiceType


class NexPortInvoice(Document):
	def validate(self) -> None:
		self._set_entity_type()

	def _set_entity_type(self) -> None:
		"""Auto-set entity_type and related_order_type based on invoice type."""
		if self.type == InvoiceType.AP:
			self.entity_type = EntityType.SUPPLIER
			self.related_order_type = "NexPort Purchase Order"
		elif self.type == InvoiceType.AR:
			self.entity_type = EntityType.CUSTOMER
			self.related_order_type = "NexPort Sales Order"
