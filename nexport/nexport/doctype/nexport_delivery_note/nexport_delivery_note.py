# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document

from nexport.services.inventory_service import deduct_stock, restore_stock


class NexPortDeliveryNote(Document):
	def validate(self) -> None:
		if not self.is_provisional and not self.sales_order:
			frappe.throw("Sales Order is required unless this is a Provisional delivery")

	def on_submit(self) -> None:
		deduct_stock(self)

	def on_cancel(self) -> None:
		restore_stock(self)
