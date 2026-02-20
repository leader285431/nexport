# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None) -> tuple[list, list]:
	columns = _get_columns()
	data = _get_data(filters or {})
	return columns, data


def get_filters() -> list[dict]:
	return [
		{
			"fieldname": "supplier",
			"label": _("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier",
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
		},
	]


def _get_columns() -> list[dict]:
	return [
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 130,
		},
		{
			"label": _("PO Unit Price"),
			"fieldname": "po_unit_price",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Cost Landed (Physical)"),
			"fieldname": "cost_landed",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Cost Declared"),
			"fieldname": "cost_declared",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("PO vs Landed Variance"),
			"fieldname": "po_landed_variance",
			"fieldtype": "Currency",
			"width": 160,
		},
		{
			"label": _("Declared vs Landed Variance"),
			"fieldname": "decl_landed_variance",
			"fieldtype": "Currency",
			"width": 190,
		},
		{
			"label": _("Markup %"),
			"fieldname": "markup_pct",
			"fieldtype": "Percent",
			"width": 100,
		},
	]


def _get_data(filters: dict) -> list[dict]:
	conditions = ""
	values: dict = {}

	if filters.get("supplier"):
		conditions += " AND po.supplier = %(supplier)s"
		values["supplier"] = filters["supplier"]

	if filters.get("currency"):
		conditions += " AND po.currency = %(currency)s"
		values["currency"] = filters["currency"]

	return frappe.db.sql(
		f"""
		SELECT
			i.name           AS item,
			i.item_name      AS item_name,
			po.supplier      AS supplier,
			AVG(poi.unit_price)                          AS po_unit_price,
			i.cost_landed                                AS cost_landed,
			i.cost_declared                              AS cost_declared,
			i.cost_landed - AVG(poi.unit_price)          AS po_landed_variance,
			i.cost_landed - i.cost_declared              AS decl_landed_variance,
			CASE WHEN i.cost_declared > 0
				THEN ROUND((i.cost_landed - i.cost_declared) / i.cost_declared * 100, 2)
				ELSE NULL
			END                                          AS markup_pct
		FROM `tabItem` i
		INNER JOIN `tabPurchase Order Item` poi ON poi.item = i.name
		INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
		WHERE po.status != 'Cancelled'
		  AND i.cost_landed IS NOT NULL
		  {conditions}
		GROUP BY i.name, i.item_name, po.supplier, i.cost_landed, i.cost_declared
		ORDER BY ABS(i.cost_landed - AVG(poi.unit_price)) DESC
		""",
		values,
		as_dict=True,
	)
