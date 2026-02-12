import frappe
from frappe.tests.utils import FrappeTestCase


class TestCustomer(FrappeTestCase):
	def test_create_customer(self):
		cust = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "_Test Customer",
		}).insert(ignore_permissions=True)
		self.assertEqual(cust.customer_name, "_Test Customer")
		self.assertEqual(cust.name, "_Test Customer")
