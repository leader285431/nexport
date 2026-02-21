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
			"fieldname": "assigned_to",
			"label": _("Salesperson"),
			"fieldtype": "Link",
			"options": "User",
		},
	]


def _get_columns() -> list[dict]:
	return [
		{"label": _("Opportunity"), "fieldname": "name", "fieldtype": "Link", "options": "Opportunity", "width": 160},
		{"label": _("Opportunity Name"), "fieldname": "opportunity_name", "fieldtype": "Data", "width": 180},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Salesperson"), "fieldname": "assigned_to", "fieldtype": "Link", "options": "User", "width": 130},
		{"label": _("Expected Revenue"), "fieldname": "expected_revenue", "fieldtype": "Currency", "width": 140},
		{"label": _("Probability %"), "fieldname": "probability", "fieldtype": "Percent", "width": 110},
		{"label": _("Weighted Revenue"), "fieldname": "weighted_revenue", "fieldtype": "Currency", "width": 140},
		{"label": _("Close Date"), "fieldname": "expected_close_date", "fieldtype": "Date", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]


def _get_data(filters: dict) -> list[dict]:
	conditions = "WHERE status NOT IN ('Won','Lost')"
	values: dict = {}

	if filters.get("assigned_to"):
		conditions += " AND assigned_to = %(assigned_to)s"
		values["assigned_to"] = filters["assigned_to"]

	rows = frappe.db.sql(
		f"""
		SELECT
			name,
			opportunity_name,
			customer,
			assigned_to,
			expected_revenue,
			probability,
			expected_close_date,
			status
		FROM `tabOpportunity`
		{conditions}
		ORDER BY expected_close_date ASC
		""",
		values,
		as_dict=True,
	)
	for r in rows:
		r.weighted_revenue = (r.expected_revenue or 0) * (r.probability or 0) / 100
	return rows
