# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
import frappe, math
import erpnext
from frappe import _
from frappe.utils import flt, rounded, add_months, nowdate
from frappe.model.document import Document
from erpnext.hr.utils import set_employee_name

class EmployeeLoans(Document):
	def validate(self):

		# from frappe.utils import money_in_words
		
		self.calculate_earning_total()
			
		# company_currency = erpnext.get_company_currency(self.company)

		set_employee_name(self)
	
	def calculate_earning_total(self):
		total_earn = 0
		for d in self.get("e_loan_transaction"):
			if d.transaction_type == "Deduction":
				total_earn -= flt(d.transaction_amount)
			else:
				total_earn += flt(d.transaction_amount)

		self.net_balance = total_earn
	
