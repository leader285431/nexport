# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class NexPortSettings(Document):
	def validate(self) -> None:
		if self.default_markup_multiplier <= 0:
			frappe.throw("Default Markup Multiplier must be greater than 0")
		if self.default_markup_multiplier > 10:
			frappe.throw("Default Markup Multiplier cannot exceed 10")
		if self.default_gap_deadline_days <= 0:
			frappe.throw("Default Gap Deadline Days must be greater than 0")
		if self.default_gap_deadline_days > 365:
			frappe.throw("Default Gap Deadline Days cannot exceed 365")
