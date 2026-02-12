import frappe
from frappe.tests.utils import FrappeTestCase


class TestSupplier(FrappeTestCase):
	def test_create_supplier(self):
		sup = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": "_Test Supplier",
		}).insert(ignore_permissions=True)
		self.assertEqual(sup.supplier_name, "_Test Supplier")
		self.assertEqual(sup.name, "_Test Supplier")
