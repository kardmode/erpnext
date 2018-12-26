# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff,fmt_money, add_to_date, formatdate,money_in_words
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_start_end_dates
from erpnext.hr.doctype.salary_slip.salary_slip import calculate_gratuity
from erpnext import get_company_currency

class MRPGratuity(Document):
	def validate(self):
		self.test_calculate_gratuity()
	def test_calculate_gratuity(self):
		gratuity_pay = 0
		gratuity_calculation = ''
		leave_encashment_amount = 0
		
		salary_per_day = 0
		struct = self.check_sal_struct(self.joining_date, self.relieving_date)
		if struct:
			salary_structure_doc = frappe.get_doc('Salary Structure', struct)
			
			salary_per_day = self.calculate_salary_per_day(salary_structure_doc.earnings)
			
				
			
			gratuity_pay, gratuity_calculation, leave_encashment_amount = calculate_gratuity(self.employee,salary_per_day,self.joining_date,self.relieving_date)
		
		loan_deduction, loan_deduction_summary = self.check_loan_deductions()
	
		gratuity_calculation = loan_deduction_summary + "<br>" + gratuity_calculation
		
		self.gratuity = gratuity_pay
		self.summary = gratuity_calculation
		self.leave_encashment_amount = leave_encashment_amount
		self.salary_per_day = salary_per_day
		self.total_deduction = loan_deduction
		self.grand_total = flt(gratuity_pay) + flt(leave_encashment_amount) - flt(loan_deduction)
		
		self.total_in_words = money_in_words(self.grand_total, get_company_currency(self.company))

		return gratuity_pay, gratuity_calculation, leave_encashment_amount, salary_per_day
		
		
	def check_sal_struct(self, joining_date, relieving_date):
		cond = ''
		payroll_frequency = "Monthly"
		date_details = get_start_end_dates(payroll_frequency,self.posting_date)
		start_date = date_details.start_date
		end_date = date_details.end_date
		
		
		if payroll_frequency:
			cond = """and payroll_frequency = '%(payroll_frequency)s'""" % {"payroll_frequency": payroll_frequency}


		st_name = frappe.db.sql("""select parent from `tabSalary Structure Employee`
			where employee=%s and (from_date <= %s or from_date <= %s)
			and (to_date is null or to_date >= %s or to_date >= %s)
			and parent in (select name from `tabSalary Structure`
				where is_active = 'Yes'%s)
			"""% ('%s', '%s', '%s','%s','%s', cond),(self.employee, start_date, joining_date, end_date, relieving_date))

		
		if st_name:
			if len(st_name) > 1:
				frappe.msgprint(_("Multiple active Salary Structures found for employee {0} for the given dates")
					.format(self.employee), title=_('Warning'))
			return st_name and st_name[0][0] or ''
		else:
			frappe.msgprint(_("No active or default Salary Structure found for employee {0} for the given dates")
				.format(self.employee), title=_('Salary Structure Missing'))
				
	def calculate_salary_per_day(self,earnings):
		salaryperday = 0
		hourlyrate = 0	
			
		for d in earnings:
			if(d.salary_component == "Basic Salary"):
				salaryperday = 	flt(d.amount)/30
				hourlyrate = flt(salaryperday)/ 9

		if salaryperday == 0:
			frappe.throw(_("No salary per day calculation for employee {0}").format(self.employee))
		
		return salaryperday
	
	def check_loan_deductions(self):
		payroll_frequency = "Monthly"

		date_details = get_start_end_dates(payroll_frequency,self.posting_date)
		it = date_details.start_date
		dt = date_details.end_date
		
		
		loandata = frappe.db.sql("""
				select t1.transaction_amount,t1.transaction_date
				from `tabLoan Transaction` t1,`tabMRP Loan Type` t2
				where 
				t1.parent = %s
				and t1.transaction_date >= %s 
				and t1.transaction_date <= %s
				and (t2.name = t1.transaction_type and t2.type = 'Deduction' and t2.affect_doctype = 'Gratuity')
				""", (self.employee,it,dt), as_dict=True)
		
		company_currency = get_company_currency(self.company)
		loan_deduction = 0
		loan_deduction_summary = ""
		if loandata:
			# loan_deduction_summary = "<b>Loan Deducions</b><br>"
			for d in loandata:
				# loan_deduction_summary += str(formatdate(d.transaction_date)) + " - " + str(fmt_money(d.transaction_amount, currency=company_currency)) + "<br>"
				loan_deduction += flt(d.transaction_amount)
		
		loan_deduction_summary = "<b>Total Loan Deduction:</b> " + str(fmt_money(loan_deduction, currency=company_currency))
		
		return loan_deduction, loan_deduction_summary
			