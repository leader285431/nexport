# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Payment processing service for installment scheduling and payment tracking."""

from __future__ import annotations

from datetime import datetime, timedelta

import frappe
from frappe.utils import add_days, cint, flt, getdate

from nexport.constants import (
	PaymentTerms,
	PaymentStatus,
	REMINDER_DAYS_FIRST,
	REMINDER_DAYS_SECOND,
	REMINDER_DAYS_FINAL,
)


def generate_payment_schedule(invoice: frappe.model.document.Document) -> None:
	"""
	Generate payment schedule installments based on payment_terms.
	Splits invoice.total_amount into payment_schedule rows.
	"""
	if not invoice.payment_terms:
		return

	# Clear existing schedule
	invoice.payment_schedule = []

	amount = flt(invoice.total_amount)
	due_date_base = getdate(invoice.invoice_date)
	installment_num = 1

	if invoice.payment_terms == PaymentTerms.IMMEDIATE:
		# Single installment due today
		invoice.append("payment_schedule", {
			"installment_number": installment_num,
			"due_date": due_date_base,
			"amount": amount,
			"status": PaymentStatus.PENDING,
		})

	elif invoice.payment_terms == PaymentTerms.NET_30:
		invoice.append("payment_schedule", {
			"installment_number": installment_num,
			"due_date": add_days(due_date_base, 30),
			"amount": amount,
			"status": PaymentStatus.PENDING,
		})

	elif invoice.payment_terms == PaymentTerms.NET_60:
		invoice.append("payment_schedule", {
			"installment_number": installment_num,
			"due_date": add_days(due_date_base, 60),
			"amount": amount,
			"status": PaymentStatus.PENDING,
		})

	elif invoice.payment_terms == PaymentTerms.NET_90:
		invoice.append("payment_schedule", {
			"installment_number": installment_num,
			"due_date": add_days(due_date_base, 90),
			"amount": amount,
			"status": PaymentStatus.PENDING,
		})

	elif invoice.payment_terms == PaymentTerms.INSTALLMENT_3:
		# 3 equal installments: 30, 60, 90 days
		installment_amount = amount / 3
		for days in [30, 60, 90]:
			invoice.append("payment_schedule", {
				"installment_number": installment_num,
				"due_date": add_days(due_date_base, days),
				"amount": installment_amount,
				"status": PaymentStatus.PENDING,
			})
			installment_num += 1

	elif invoice.payment_terms == PaymentTerms.INSTALLMENT_6:
		# 6 equal installments: 30, 60, 90, 120, 150, 180 days
		installment_amount = amount / 6
		for days in [30, 60, 90, 120, 150, 180]:
			invoice.append("payment_schedule", {
				"installment_number": installment_num,
				"due_date": add_days(due_date_base, days),
				"amount": installment_amount,
				"status": PaymentStatus.PENDING,
			})
			installment_num += 1

	invoice.save(ignore_permissions=True)


def apply_payment_execution(execution: frappe.model.document.Document) -> None:
	"""
	Record payment execution and update installment + invoice status.
	Called from Payment Execution on_submit hook.
	"""
	savepoint = "payment_execution"
	try:
		frappe.db.savepoint(savepoint)

		# Load invoice
		invoice = frappe.get_doc("Invoice", execution.invoice)

		# Find matching payment plan row
		payment_plan_row = None
		for row in invoice.payment_schedule or []:
			if cint(row.installment_number) == cint(execution.installment):
				payment_plan_row = row
				break

		if not payment_plan_row:
			frappe.throw(
				f"Payment plan installment {execution.installment} not found in invoice {execution.invoice}"
			)

		# Update installment status
		payment_plan_row.status = PaymentStatus.PAID
		payment_plan_row.paid_date = execution.payment_date
		payment_plan_row.payment_execution = execution.name

		# Check overall invoice payment status
		all_paid = True
		any_paid = False
		for row in invoice.payment_schedule or []:
			if row.status != PaymentStatus.PAID:
				all_paid = False
			if row.status == PaymentStatus.PAID:
				any_paid = True

		if all_paid:
			invoice.status = "Paid"
		elif any_paid:
			invoice.status = "Partial"

		invoice.save(ignore_permissions=True)

	except Exception as e:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(
			f"Payment execution {execution.name} failed: {str(e)}",
			"Payment Service - apply_payment_execution"
		)
		raise


def mark_overdue_installments() -> None:
	"""
	Daily scheduler function: Mark past-due pending installments as Overdue.
	"""
	try:
		today = getdate()
		frappe.db.sql(
			"""
			UPDATE `tabNexPort Payment Plan`
			SET status = %s
			WHERE status = %s AND due_date < %s
			""",
			(PaymentStatus.OVERDUE, PaymentStatus.PENDING, today),
		)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(
			f"Failed to mark overdue installments: {str(e)}",
			"Payment Service - mark_overdue_installments"
		)


def send_payment_reminders() -> None:
	"""
	Daily scheduler function: Send email reminders at 7, 3, and 1 day thresholds.
	"""
	try:
		today = getdate()

		# Find installments matching reminder thresholds
		for reminder_days in [REMINDER_DAYS_FIRST, REMINDER_DAYS_SECOND, REMINDER_DAYS_FINAL]:
			target_date = add_days(today, reminder_days)

			# Get pending installments due on target_date
			installments = frappe.db.sql(
				"""
				SELECT
					pp.name,
					pp.installment_number,
					pp.due_date,
					pp.amount,
					i.name as invoice_name,
					i.entity_type,
					i.entity,
					i.total_amount
				FROM `tabNexPort Payment Plan` pp
				JOIN `tabInvoice` i ON pp.parent = i.name
				WHERE pp.status = %s
				AND DATE(pp.due_date) = %s
				""",
				(PaymentStatus.PENDING, target_date),
				as_dict=True,
			)

			for installment in installments:
				_send_reminder_email(installment, reminder_days)

	except Exception as e:
		frappe.log_error(
			f"Failed to send payment reminders: {str(e)}",
			"Payment Service - send_payment_reminders"
		)


def _send_reminder_email(installment: dict, days_until_due: int) -> None:
	"""Send individual reminder email for an installment."""
	try:
		# Get entity (customer/supplier) email
		entity_email = frappe.db.get_value(installment.entity_type, installment.entity, "email")
		if not entity_email:
			return

		# Format message
		if days_until_due == 1:
			due_text = "TOMORROW"
		else:
			due_text = f"in {days_until_due} days"

		subject = f"Payment Due {due_text} - Invoice {installment.invoice_name}"
		message = f"""
		<p>Payment reminder for Invoice <strong>{installment.invoice_name}</strong></p>
		<p>
			<strong>Installment {installment.installment_number}:</strong> {installment.amount}<br/>
			<strong>Due Date:</strong> {installment.due_date}<br/>
			<strong>Total Invoice Amount:</strong> {installment.total_amount}
		</p>
		<p>Please arrange payment accordingly.</p>
		"""

		frappe.sendmail(
			recipients=[entity_email],
			subject=subject,
			message=message,
		)

	except Exception as e:
		frappe.log_error(
			f"Failed to send reminder for installment {installment.get('name')}: {str(e)}",
			"Payment Service - _send_reminder_email"
		)


def record_payment(
	invoice: str,
	installment_no: int,
	payment_date: str,
	amount_paid: float,
	exchange_rate: float,
	remittance_reference: str,
	bank_reference: str = "",
) -> str:
	"""
	Phase 1: Record payment execution document (own savepoint).

	Args:
		invoice: Invoice document name.
		installment_no: Installment number from Payment Schedule.
		payment_date: Date the payment was made.
		amount_paid: Amount paid in transaction currency.
		exchange_rate: Exchange rate used at time of payment.
		remittance_reference: Unique remittance/reference identifier.
		bank_reference: Optional bank reference string.

	Returns:
		Name of the created NexPort Payment Execution document.

	Raises:
		frappe.ValidationError: If idempotency key already exists.
		Exception: Re-raised after savepoint rollback on any failure.
	"""
	frappe.db.savepoint("payment_phase1")
	try:
		inv_doc = frappe.get_doc("Invoice", invoice)
		invoice_rate = flt(inv_doc.actual_exchange_rate) or 1.0
		fx_variance = (flt(exchange_rate) - invoice_rate) * flt(amount_paid)

		exec_doc = frappe.get_doc({
			"doctype": "NexPort Payment Execution",
			"invoice": invoice,
			"installment": installment_no,
			"payment_date": payment_date,
			"amount_paid": amount_paid,
			"exchange_rate": exchange_rate,
			"remittance_reference": remittance_reference,
			"bank_reference": bank_reference,
			"fx_variance": fx_variance,
		})
		exec_doc.insert(ignore_permissions=True)

		# Update installment row status via raw SQL
		frappe.db.sql(
			"""
			UPDATE `tabNexPort Payment Plan`
			SET status = %s,
				paid_amount = %s,
				paid_date = %s,
				payment_reference = %s,
				exchange_rate_variance = %s
			WHERE parent = %s
			  AND installment_number = %s
			""",
			(
				PaymentStatus.PAID,
				amount_paid,
				payment_date,
				exec_doc.name,
				fx_variance,
				invoice,
				installment_no,
			),
		)

		_sync_invoice_status(inv_doc)
		return exec_doc.name

	except Exception:
		frappe.db.rollback(save_point="payment_phase1")
		raise


def _sync_invoice_status(inv_doc: frappe.model.document.Document) -> None:
	"""
	Update Invoice status based on installment completion.

	Args:
		inv_doc: The Invoice document to inspect and update.
	"""
	rows = frappe.db.get_all(
		"NexPort Payment Plan",
		filters={"parent": inv_doc.name},
		fields=["status"],
	)
	statuses = {r.status for r in rows}
	if not statuses:
		return
	if statuses == {PaymentStatus.PAID}:
		frappe.db.set_value("Invoice", inv_doc.name, "status", "Paid")
	elif PaymentStatus.PAID in statuses:
		frappe.db.set_value("Invoice", inv_doc.name, "status", "Partial")


def trigger_revaluation(invoice: str, payment_execution: str) -> None:
	"""
	Phase 2: Trigger finance_service revaluation (separate savepoint).

	Failure is logged but does NOT roll back Phase 1.

	Args:
		invoice: Invoice document name.
		payment_execution: NexPort Payment Execution document name.
	"""
	frappe.db.savepoint("payment_phase2")
	try:
		from nexport.services.finance_service import revalue_on_payment
		revalue_on_payment(invoice)
	except Exception as e:
		frappe.db.rollback(save_point="payment_phase2")
		frappe.log_error(
			title=f"Revaluation failed for {invoice} / {payment_execution}",
			message=str(e),
		)
