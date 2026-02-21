# Copyright (c) 2026, NexPort and contributors
from __future__ import annotations
import frappe
from frappe.utils import nowdate, get_first_day, get_last_day


def execute(filters: dict | None = None) -> tuple[list, list]:
	columns = _get_columns()
	data = _get_data(filters or {})
	return columns, data


def _get_columns() -> list[dict]:
	return [
		{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Data", "width": 200},
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Data", "width": 80},
		{"label": "Overdue", "fieldname": "overdue", "fieldtype": "Currency", "width": 130},
		{"label": "Due This Month", "fieldname": "due_this_month", "fieldtype": "Currency", "width": 140},
		{"label": "Future", "fieldname": "future", "fieldtype": "Currency", "width": 130},
		{"label": "Total Outstanding", "fieldname": "total", "fieldtype": "Currency", "width": 150},
	]


def _get_data(filters: dict) -> list[dict]:
	today = nowdate()
	month_end = get_last_day(today)

	rows = frappe.db.sql("""
		SELECT
			i.supplier,
			i.currency,
			SUM(CASE WHEN ps.status = 'Overdue' THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS overdue,
			SUM(CASE WHEN ps.status = 'Pending' AND ps.due_date <= %(month_end)s THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS due_this_month,
			SUM(CASE WHEN ps.status = 'Pending' AND ps.due_date > %(month_end)s THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS future,
			SUM(CASE WHEN ps.status IN ('Pending', 'Overdue') THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS total
		FROM `tabPayment Schedule` ps
		JOIN `tabInvoice` i ON i.name = ps.parent
		WHERE i.invoice_type = 'AP (Accounts Payable)'
		  AND ps.status != 'Paid'
		GROUP BY i.supplier, i.currency
		ORDER BY i.supplier, i.currency
	""", {"month_end": month_end}, as_dict=True)
	return rows
