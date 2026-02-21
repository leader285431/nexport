# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call

from nexport.constants import PaymentTerms, PaymentStatus

import nexport.services.payment_service as payment_service


_SERVICE = "nexport.services.payment_service"


class TestGeneratePaymentSchedule(unittest.TestCase):
	"""Test payment schedule generation logic."""

	@patch(f"{_SERVICE}.frappe")
	def test_net_30_single_installment(self, mock_frappe: MagicMock) -> None:
		"""Net 30 terms should create single installment due in 30 days."""
		invoice = MagicMock()
		invoice.payment_terms = PaymentTerms.NET_30
		invoice.total_amount = 1000.0
		invoice.invoice_date = "2026-02-20"
		invoice.payment_schedule = []

		payment_service.generate_payment_schedule(invoice)

		invoice.append.assert_called_once()
		invoice.save.assert_called_once_with(ignore_permissions=True)

	@patch(f"{_SERVICE}.frappe")
	def test_three_installments_split(self, mock_frappe: MagicMock) -> None:
		"""3 Installments should split amount into 3 equal parts."""
		invoice = MagicMock()
		invoice.payment_terms = PaymentTerms.INSTALLMENT_3
		invoice.total_amount = 3000.0
		invoice.invoice_date = "2026-02-20"
		invoice.payment_schedule = []

		payment_service.generate_payment_schedule(invoice)

		self.assertEqual(invoice.append.call_count, 3)
		invoice.save.assert_called_once()

	@patch(f"{_SERVICE}.frappe")
	def test_immediate_due_today(self, mock_frappe: MagicMock) -> None:
		"""Immediate terms should create a single installment due on invoice date."""
		invoice = MagicMock()
		invoice.payment_terms = PaymentTerms.IMMEDIATE
		invoice.total_amount = 500.0
		invoice.invoice_date = "2026-02-20"
		invoice.payment_schedule = []

		payment_service.generate_payment_schedule(invoice)

		invoice.append.assert_called_once()
		invoice.save.assert_called_once()

	@patch(f"{_SERVICE}.frappe")
	def test_no_payment_terms_is_noop(self, mock_frappe: MagicMock) -> None:
		"""If payment_terms is empty, do nothing."""
		invoice = MagicMock()
		invoice.payment_terms = None

		payment_service.generate_payment_schedule(invoice)

		invoice.append.assert_not_called()
		invoice.save.assert_not_called()


class TestApplyPaymentExecution(unittest.TestCase):
	"""Test payment execution application."""

	@patch(f"{_SERVICE}.frappe")
	def test_full_payment_sets_paid_status(self, mock_frappe: MagicMock) -> None:
		"""Single installment fully paid → invoice status = Paid."""
		execution = MagicMock()
		execution.invoice = "INV-001"
		execution.installment = 1
		execution.payment_date = "2026-02-20"
		execution.name = "PAY-EX-0001"

		row1 = MagicMock()
		row1.installment_number = 1
		row1.status = PaymentStatus.PENDING

		invoice = MagicMock()
		invoice.payment_schedule = [row1]

		mock_frappe.get_doc.return_value = invoice
		mock_frappe.db = MagicMock()

		payment_service.apply_payment_execution(execution)

		self.assertEqual(row1.status, PaymentStatus.PAID)
		self.assertEqual(invoice.status, "Paid")
		invoice.save.assert_called_once()

	@patch(f"{_SERVICE}.frappe")
	def test_partial_payment_sets_partial_status(self, mock_frappe: MagicMock) -> None:
		"""First of 3 installments paid → invoice status = Partial."""
		execution = MagicMock()
		execution.invoice = "INV-002"
		execution.installment = 1
		execution.payment_date = "2026-02-20"
		execution.name = "PAY-EX-0002"

		row1 = MagicMock()
		row1.installment_number = 1
		row1.status = PaymentStatus.PENDING
		row2 = MagicMock()
		row2.installment_number = 2
		row2.status = PaymentStatus.PENDING
		row3 = MagicMock()
		row3.installment_number = 3
		row3.status = PaymentStatus.PENDING

		invoice = MagicMock()
		invoice.payment_schedule = [row1, row2, row3]

		mock_frappe.get_doc.return_value = invoice
		mock_frappe.db = MagicMock()

		payment_service.apply_payment_execution(execution)

		self.assertEqual(row1.status, PaymentStatus.PAID)
		self.assertEqual(invoice.status, "Partial")

	@patch(f"{_SERVICE}.frappe")
	def test_invalid_installment_throws_error(self, mock_frappe: MagicMock) -> None:
		"""Non-existent installment number should cause frappe.throw to be called."""
		execution = MagicMock()
		execution.invoice = "INV-003"
		execution.installment = 999
		execution.payment_date = "2026-02-20"
		execution.name = "PAY-EX-0003"

		row1 = MagicMock()
		row1.installment_number = 1
		row1.status = PaymentStatus.PENDING

		invoice = MagicMock()
		invoice.payment_schedule = [row1]

		mock_frappe.get_doc.return_value = invoice
		mock_frappe.db = MagicMock()
		mock_frappe.throw.side_effect = Exception("Installment not found")

		with self.assertRaises(Exception):
			payment_service.apply_payment_execution(execution)

		mock_frappe.throw.assert_called_once()


class TestMarkOverdueInstallments(unittest.TestCase):
	"""Test overdue marking scheduler function."""

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.getdate", return_value="2026-02-20")
	def test_marks_past_due_as_overdue(self, mock_getdate: MagicMock, mock_frappe: MagicMock) -> None:
		"""SQL UPDATE should be executed to mark overdue installments."""
		payment_service.mark_overdue_installments()

		mock_frappe.db.sql.assert_called_once()
		call_sql = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("UPDATE", call_sql)
		mock_frappe.db.commit.assert_called_once()

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.getdate", return_value="2026-02-20")
	def test_logs_error_on_db_failure(self, mock_getdate: MagicMock, mock_frappe: MagicMock) -> None:
		"""DB error should be logged without raising."""
		mock_frappe.db.sql.side_effect = Exception("DB Error")

		try:
			payment_service.mark_overdue_installments()
		except Exception as e:
			self.fail(f"mark_overdue_installments raised {e}")

		mock_frappe.log_error.assert_called_once()


class TestSendPaymentReminders(unittest.TestCase):
	"""Test payment reminder scheduler function."""

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.add_days", return_value="2026-03-01")
	@patch(f"{_SERVICE}.getdate", return_value="2026-02-20")
	def test_sends_reminder_emails(self, mock_getdate: MagicMock, mock_add_days: MagicMock, mock_frappe: MagicMock) -> None:
		"""Email reminders should be attempted for matching installments."""
		mock_frappe.db.sql.return_value = [
			{
				"name": "pp-1",
				"installment_number": 1,
				"due_date": "2026-03-01",
				"amount": 500.0,
				"invoice_name": "INV-001",
				"entity_type": "Supplier",
				"entity": "SUP-001",
				"total_amount": 1000.0,
			}
		]
		mock_frappe.db.get_value.return_value = "supplier@example.com"

		payment_service.send_payment_reminders()

		# SQL query was executed for each reminder threshold
		self.assertTrue(mock_frappe.db.sql.called)

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.getdate", return_value="2026-02-20")
	def test_logs_error_on_send_failure(self, mock_getdate: MagicMock, mock_frappe: MagicMock) -> None:
		"""DB error should be logged without raising."""
		mock_frappe.db.sql.side_effect = Exception("Query Error")

		try:
			payment_service.send_payment_reminders()
		except Exception as e:
			self.fail(f"send_payment_reminders raised {e}")

		mock_frappe.log_error.assert_called()



class TestRecordPaymentFXVariance(unittest.TestCase):
	"""FX variance = (payment_rate - invoice_rate) x amount_paid."""

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.flt", side_effect=float)
	def test_positive_fx_variance(self, mock_flt: MagicMock, mock_frappe: MagicMock) -> None:
		"""Payment rate > invoice rate produces positive variance."""
		inv_doc = MagicMock()
		inv_doc.name = "INV-FX-001"
		inv_doc.actual_exchange_rate = 30.0
		captured = {}
		call_count = [0]

		def side_get_doc(data_or_doctype, *args, **kwargs):
			call_count[0] += 1
			if call_count[0] == 1:
				return inv_doc
			doc = MagicMock()
			doc.name = "PAY-EX-FX-001"
			if isinstance(data_or_doctype, dict):
				for k, v in data_or_doctype.items():
					captured[k] = v
			return doc

		mock_frappe.get_doc.side_effect = side_get_doc
		mock_frappe.db.get_all.return_value = [MagicMock(status=PaymentStatus.PAID)]
		payment_service.record_payment(
			invoice="INV-FX-001",
			installment_no=1,
			payment_date="2026-02-20",
			amount_paid=1000.0,
			exchange_rate=31.5,
			remittance_reference="REF-FX-001",
		)
		# (31.5 - 30.0) * 1000.0 = 1500.0
		self.assertAlmostEqual(captured.get("fx_variance", 0.0), 1500.0, places=2)

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.flt", side_effect=float)
	def test_zero_fx_variance_when_rates_match(self, mock_flt: MagicMock, mock_frappe: MagicMock) -> None:
		"""Zero variance when payment_rate == invoice_rate."""
		inv_doc = MagicMock()
		inv_doc.name = "INV-FX-002"
		inv_doc.actual_exchange_rate = 32.0
		captured = {}
		call_count = [0]

		def side_get_doc(data_or_doctype, *args, **kwargs):
			call_count[0] += 1
			if call_count[0] == 1:
				return inv_doc
			doc = MagicMock()
			doc.name = "PAY-EX-FX-002"
			if isinstance(data_or_doctype, dict):
				for k, v in data_or_doctype.items():
					captured[k] = v
			return doc

		mock_frappe.get_doc.side_effect = side_get_doc
		mock_frappe.db.get_all.return_value = [MagicMock(status=PaymentStatus.PAID)]
		payment_service.record_payment(
			invoice="INV-FX-002",
			installment_no=1,
			payment_date="2026-02-20",
			amount_paid=500.0,
			exchange_rate=32.0,
			remittance_reference="REF-FX-002",
		)
		self.assertAlmostEqual(captured.get("fx_variance", -999.0), 0.0, places=2)


class TestRecordPaymentIdempotency(unittest.TestCase):
	"""Duplicate payment references must be rejected and phase1 rolled back."""

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.flt", side_effect=float)
	def test_duplicate_reference_raises_and_rolls_back(
		self,
		mock_flt: MagicMock,
		mock_frappe: MagicMock,
	) -> None:
		"""insert() raising duplicate error must re-raise after phase1 rollback."""
		inv_doc = MagicMock()
		inv_doc.name = "INV-DUP-001"
		inv_doc.actual_exchange_rate = 30.0
		exec_doc = MagicMock()
		exec_doc.insert.side_effect = Exception("Duplicate entry REF-DUP")
		call_count = [0]

		def side_get_doc(data_or_doctype, *args, **kwargs):
			call_count[0] += 1
			if call_count[0] == 1:
				return inv_doc
			return exec_doc

		mock_frappe.get_doc.side_effect = side_get_doc
		with self.assertRaises(Exception) as ctx:
			payment_service.record_payment(
				invoice="INV-DUP-001",
				installment_no=1,
				payment_date="2026-02-20",
				amount_paid=600.0,
				exchange_rate=30.0,
				remittance_reference="REF-DUP",
			)
		self.assertIn("Duplicate", str(ctx.exception))
		mock_frappe.db.rollback.assert_called_once_with(save_point="payment_phase1")


class TestRevaluationFailureIsolation(unittest.TestCase):
	"""Phase 2 (revaluation) failure must not roll back Phase 1 payment record."""

	@patch(f"{_SERVICE}.frappe")
	def test_trigger_revaluation_catches_exception_and_logs(
		self,
		mock_frappe: MagicMock,
	) -> None:
		"""trigger_revaluation rolls back phase2 savepoint and logs on error without re-raising."""
		with patch("nexport.services.finance_service.revalue_on_payment") as mock_reval:
			mock_reval.side_effect = Exception("reval error")
			try:
				payment_service.trigger_revaluation("INV-001", "PAY-EX-001")
			except Exception as e:
				self.fail(f"trigger_revaluation raised unexpectedly: {e}")
		mock_frappe.db.rollback.assert_called_once_with(save_point="payment_phase2")
		mock_frappe.log_error.assert_called_once()

	@patch(f"{_SERVICE}.frappe")
	@patch(f"{_SERVICE}.flt", side_effect=float)
	def test_phase1_succeeds_independently_of_phase2(
		self,
		mock_flt: MagicMock,
		mock_frappe: MagicMock,
	) -> None:
		"""record_payment returns exec name; phase1 savepoint never rolled back on success."""
		inv_doc = MagicMock()
		inv_doc.name = "INV-PHASE-001"
		inv_doc.actual_exchange_rate = 30.0
		exec_doc = MagicMock()
		exec_doc.name = "PAY-EX-PHASE-001"
		call_count = [0]

		def side_get_doc(data_or_doctype, *args, **kwargs):
			call_count[0] += 1
			if call_count[0] == 1:
				return inv_doc
			return exec_doc

		mock_frappe.get_doc.side_effect = side_get_doc
		mock_frappe.db.get_all.return_value = [MagicMock(status=PaymentStatus.PAID)]
		result = payment_service.record_payment(
			invoice="INV-PHASE-001",
			installment_no=1,
			payment_date="2026-02-20",
			amount_paid=400.0,
			exchange_rate=30.0,
			remittance_reference="REF-PHASE",
		)
		self.assertEqual(result, "PAY-EX-PHASE-001")
		rollback_calls = [
			c for c in mock_frappe.db.rollback.call_args_list
			if c.kwargs.get("save_point") == "payment_phase1"
		]
		self.assertEqual(len(rollback_calls), 0, "Phase 1 must not rollback on success")


if __name__ == "__main__":
	unittest.main()
