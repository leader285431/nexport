# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class NexPortSettings(Document):
	def validate(self):
		if self.default_markup_multiplier <= 0:
			frappe.throw("Default Markup Multiplier must be greater than 0")
		if self.default_gap_deadline_days <= 0:
			frappe.throw("Default Gap Deadline Days must be greater than 0")
