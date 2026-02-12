# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document

from nexport.constants import POStatus
from nexport.utils import compute_line_totals


class PurchaseOrder(Document):
	def validate(self) -> None:
		compute_line_totals(self)
		self._check_duplicate_supplementary()
		self._warn_no_invoice()

	def _check_duplicate_supplementary(self) -> None:
		"""Block duplicate supplementary POs for the same parent."""
		if not self.is_supplementary or not self.parent_po:
			return
		existing = frappe.db.exists(
			"Purchase Order",
			{
				"parent_po": self.parent_po,
				"is_supplementary": 1,
				"name": ("!=", self.name),
				"docstatus": ("!=", 2),
			},
		)
		if existing:
			frappe.throw(
				f"A supplementary PO already exists for {self.parent_po}: {existing}. "
				"Only one supplementary PO per parent is allowed."
			)

	def _warn_no_invoice(self) -> None:
		"""Warn (not block) if transitioning to Shipped/Received without invoice."""
		if self.status in (POStatus.SHIPPED, POStatus.RECEIVED) and not self.invoice_id:
			frappe.msgprint(
				"This PO has no linked Invoice. Consider creating an invoice first.",
				indicator="orange",
				title="Missing Invoice",
			)
