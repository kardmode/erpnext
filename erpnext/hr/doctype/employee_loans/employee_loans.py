# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import add_days, cint, cstr, flt, getdate, nowdate, rounded, date_diff
from frappe.model.naming import make_autoname

from frappe import msgprint, _
from erpnext.setup.utils import get_company_currency
from erpnext.hr.utils import set_employee_name
from erpnext.hr.doctype.process_payroll.process_payroll import get_month_details

from erpnext.utilities.transaction_base import TransactionBase

class EmployeeLoans(TransactionBase):
	
	
	def calculate_earning_total(self):
		
		for d in self.get("e_loan_transaction"):
			if d.transaction_type == "Deduction":
				total_earn -= flt(d.transaction_amount)
			else:
				total_earn += flt(d.transaction_amount)

		self.net_balance = total_earn
	def validate(self):
		from frappe.utils import money_in_words
		
		if not self.net_balance:
			self.calculate_earning_total()
			
		company_currency = get_company_currency(self.company)

		set_employee_name(self)


	def send_mail_funct(self):
		receiver = frappe.db.get_value("Employee", self.employee, "company_email")
		if receiver:
			subj = 'Employee Loan - ' + cstr(self.month) +'/'+cstr(self.fiscal_year)
			frappe.sendmail([receiver], subject=subj, message = _("Please see attachment"),
				attachments=[frappe.attach_print(self.doctype, self.name, file_name=self.name)])
		else:
			msgprint(_("Company Email ID not found, hence mail not sent"))
