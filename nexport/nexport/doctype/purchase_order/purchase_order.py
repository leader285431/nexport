# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document

from nexport.services.order_service import validate_purchase_order


class PurchaseOrder(Document):
    def before_insert(self) -> None:
        validate_purchase_order(self, old_status=None, for_before_insert=True)

    def validate(self) -> None:
        old_status = None
        if not self.is_new():
            old_status = self.get_db_value("status")
        validate_purchase_order(self, old_status=old_status, for_before_insert=False)
        self._fill_supplier_item_codes()

    def _fill_supplier_item_codes(self) -> None:
        """Auto-populate supplier_item_code on PO lines from Item Supplier table."""
        if not self.supplier:
            return
        for row in self.get("items") or []:
            if not row.item_code:
                continue
            code = frappe.db.get_value(
                "Item Supplier",
                {"parent": row.item_code, "supplier": self.supplier},
                "supplier_item_code",
            )
            if code:
                row.supplier_item_code = code

