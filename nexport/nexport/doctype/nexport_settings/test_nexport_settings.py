# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestNexPortSettings(FrappeTestCase):
	def test_default_values(self):
		settings = frappe.get_single("NexPort Settings")
		self.assertIsNotNone(settings)

	def test_invalid_markup_multiplier(self):
		settings = frappe.get_single("NexPort Settings")
		settings.default_markup_multiplier = -1
		self.assertRaises(frappe.ValidationError, settings.validate)

	def test_invalid_gap_deadline_days(self):
		settings = frappe.get_single("NexPort Settings")
		settings.default_gap_deadline_days = 0
		self.assertRaises(frappe.ValidationError, settings.validate)
