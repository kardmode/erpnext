# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _

from frappe.model.document import Document
from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff,fmt_money, add_to_date, formatdate,money_in_words
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_start_end_dates
from erpnext import get_company_currency

class MRPGratuity(Document):
	def validate(self):
		self.test_calculate_gratuity()
	def test_calculate_gratuity(self):
		from math import ceil

		
		gratuity_pay = 0
		gratuity_calculation = ''
		leave_encashment_amount = 0
		
		salary_per_day = 0
		self.salary_structure = self.check_sal_struct(self.joining_date, self.relieving_date)
		
		salary_structure_doc = frappe.get_doc('Salary Structure', self.salary_structure)
		salary_per_day = self.calculate_salary_per_day(salary_structure_doc.earnings)
		gratuity_pay, gratuity_calculation, leave_encashment_amount = calculate_gratuity(self.employee,salary_per_day,self.joining_date,self.relieving_date,self.contract_type,self.reason_for_leaving)
	
		loan_deduction, loan_deduction_summary = self.check_loan_deductions()
	
		gratuity_calculation = loan_deduction_summary + "<br>" + gratuity_calculation
		
		self.gratuity = gratuity_pay
		self.summary = gratuity_calculation
		self.leave_encashment_amount = leave_encashment_amount
		self.salary_per_day = salary_per_day
		self.total_deduction = loan_deduction
		self.grand_total = flt(gratuity_pay) + flt(leave_encashment_amount) - flt(loan_deduction)
		self.rounded_total = ceil(self.grand_total)
		self.total_in_words = money_in_words(self.grand_total, get_company_currency(self.company))

		return gratuity_pay, gratuity_calculation, leave_encashment_amount, salary_per_day
		
		
	def check_sal_struct(self, joining_date, relieving_date):
		payroll_frequency = "Monthly"
		date_details = get_start_end_dates(payroll_frequency,self.relieving_date)
		start_date = date_details.start_date
		end_date = date_details.end_date
		
		cond = """and sa.employee=%(employee)s and (sa.from_date <= %(start_date)s or
				sa.from_date <= %(end_date)s or sa.from_date <= %(joining_date)s)"""
		if payroll_frequency:
			cond += """and ss.payroll_frequency = '%(payroll_frequency)s'""" % {"payroll_frequency": payroll_frequency}

		st_name = frappe.db.sql("""
			select sa.salary_structure
			from `tabSalary Structure Assignment` sa join `tabSalary Structure` ss
			where sa.salary_structure=ss.name
				and sa.docstatus = 1 and ss.docstatus = 1 and ss.is_active ='Yes' %s
			order by sa.from_date desc
			limit 1
		""" %cond, {'employee': self.employee, 'start_date': start_date,
			'end_date': end_date, 'joining_date': joining_date})

		if st_name:
			self.salary_structure = st_name[0][0]
			return self.salary_structure
		else:
			self.salary_structure = None
			frappe.throw(_("No active or default Salary Structure found for employee {0} for the given dates")
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

		date_details = get_start_end_dates(payroll_frequency,self.relieving_date)
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

def get_approved_leaves_for_period(employee, leave_type, from_date, to_date):
	query = """
		select employee, leave_type, from_date, to_date, total_leave_days
		from `tabLeave Application`
		where employee=%(employee)s
			and docstatus<2
			and status in ('Approved','Back From Leave')
			and (from_date between %(from_date)s and %(to_date)s
				or to_date between %(from_date)s and %(to_date)s
				or (from_date < %(from_date)s and to_date > %(to_date)s))
	"""
	if leave_type:
		query += "and leave_type=%(leave_type)s"

	leave_applications = frappe.db.sql(query,{
		"from_date": from_date,
		"to_date": to_date,
		"employee": employee,
		"leave_type": leave_type
	}, as_dict=1)

	leave_days = 0
	for leave_app in leave_applications:
		if leave_app.from_date >= getdate(from_date) and leave_app.to_date <= getdate(to_date):
			leave_days += leave_app.total_leave_days
		else:
			if leave_app.from_date < getdate(from_date):
				leave_app.from_date = from_date
			if leave_app.to_date > getdate(to_date):
				leave_app.to_date = to_date

			leave_days += get_number_of_leave_days(employee, leave_type,
				leave_app.from_date, leave_app.to_date)

	return leave_days
	
@frappe.whitelist()			
def calculate_gratuity(employee, salaryperday, joining_date,relieving_date,contract_type = "Limited",reason_for_leaving = "Resignation"):
	from math import ceil
	from frappe.utils import formatdate
	from erpnext.hr.doctype.mrp_gratuity.mrp_gratuity import get_approved_leaves_for_period

	if reason_for_leaving == None or reason_for_leaving=="":
		reason_for_leaving = "Resignation"
	if contract_type == None or contract_type=="":
		contract_type = "Limited"


	gratuity_pay = 0
	gratuity_calculation = ''
	leave_encashment_amount = 0
	
	if not relieving_date or not joining_date or not employee or salaryperday == 0:
		return gratuity_pay, gratuity_calculation, leave_encashment_amount
		
	# Relieving date is the last day of work
	payment_days = date_diff(relieving_date, joining_date)+1
	payment_years = flt(payment_days)/365

	leavedaysdue = 0
	leavedaystaken = 0

	if(payment_years >= 1):
		leavedaysdue = ceil(flt(payment_days)/365 * 30)	

	leave_types = frappe.db.sql("""
			select t2.name
			from `tabLeave Type` t2
			where
			t2.is_paid_in_advance = 1""", as_dict=True)
	
	for leave_type in leave_types:
		leavedaystaken += get_approved_leaves_for_period(employee, leave_type.name, joining_date, relieving_date)
	
	# leaves = frappe.db.sql("""
		# select t1.total_leave_days
		# from `tabLeave Application` t1, `tabLeave Type` t2
		# where 
		# t2.name = t1.leave_type
		# and t2.is_paid_in_advance = 1
		# and t1.docstatus < 2
		# and t1.status in ('Approved','Back From Leave')
		# and t1.employee = %s
		# and t1.from_date >= %s
		# and t1.to_date <= %s""", (employee, joining_date,relieving_date), as_dict=True)
	
	# for leave in leaves:
		# leavedaystaken = leavedaystaken + leave.total_leave_days
	
	net_payment_days = payment_days
	leavesbalance = leavedaysdue - leavedaystaken
	if leavesbalance < 0:
		net_payment_days += leavesbalance
	else:
		leave_encashment_amount = flt(leavesbalance) * flt(salaryperday)
		
	net_payment_years = flt(net_payment_days)/365
	
	gratuity_text = "Law as of 2018 - Max 2 Years Salary<br>"
	appended_gratuity_text = ""
	
	LR_one = "Less than 1 year, no leave or gratuity<br>"
	LR_less_five = "Between 1 and 5 years: No. of years worked * Basic Salary per day * 21<br>"
	LR_greater_five = "More than 5 years: (5 * Basic Salary per day * 21) + (No. of years worked - 5) * (Basic Salary per day * 30)<br>"
	LU_less_one = "Early Resignation before completing five years of continuous service<br>"
	LT_greater_one = "More than 1 year: No. of years worked * Basic Salary per day * 21<br>"
	UR_less_three = "Between 1 and 3 years: No. of years worked * Basic Salary per day * 21 * 1/3<br>"
	UR_less_five = "Between 3 and 5 years: No. of years worked * Basic Salary per day * 21 * 2/3<br>"
	UR_greater_five = "More than 5 years: (5 * Basic Salary per day * 21) + (No. of years worked - 5) * (Basic Salary per day * 30)<br>"
	UT_less_three = "Between 1 and 3 years: No. of years worked * Basic Salary per day * 21<br>"
	UT_less_five = "Between 3 and 5 years: No. of years worked * Basic Salary per day * 21<br>"
	UT_greater_five = "More than 5 years: (5 * Basic Salary per day * 21) + (No. of years worked - 5) * (Basic Salary per day * 30)<br>"

	
	if contract_type == "Limited":
		if reason_for_leaving == "Early Resignation":
			if(net_payment_years < 5):
				appended_gratuity_text = LU_less_one
				gratuity_pay = 0
			else:
				appended_gratuity_text = LR_greater_five
				gratuity_pay = (5*21*flt(salaryperday)) + (net_payment_years - 5)*(30*flt(salaryperday))
		else:
			if(net_payment_years < 1):
				appended_gratuity_text = LR_one
				gratuity_pay = 0
			elif(net_payment_years <= 5):
				appended_gratuity_text = LR_less_five
				gratuity_pay = flt(net_payment_years) * 21 * flt(salaryperday)
			else:
				appended_gratuity_text = LR_greater_five
				gratuity_pay = (5*21*flt(salaryperday)) + (net_payment_years - 5)*(30*flt(salaryperday))
	else:
		if reason_for_leaving in ["Resignation","Early Resignation"]:
			if(net_payment_years < 1):
				appended_gratuity_text = LR_one
				gratuity_pay = 0
			elif(net_payment_years <= 3):
				appended_gratuity_text = UR_less_three
				gratuity_pay = flt(net_payment_years) * 21 * flt(salaryperday) * flt(1/3)
			elif(net_payment_years <= 5):
				appended_gratuity_text = UR_less_five
				gratuity_pay = flt(net_payment_years) * 21 * flt(salaryperday) * flt(2/3)
			else:
				appended_gratuity_text = UR_greater_five
				gratuity_pay = (5*21*flt(salaryperday)) + (net_payment_years - 5)*(30*flt(salaryperday))
		else:
			if(net_payment_years < 1):
				appended_gratuity_text = LR_one
				gratuity_pay = 0
			elif(net_payment_years <= 5):
				appended_gratuity_text = UT_less_five
				gratuity_pay = flt(net_payment_years) * 21 * flt(salaryperday)
			else:
				appended_gratuity_text = UT_greater_five
				gratuity_pay = (5*21*flt(salaryperday)) + (net_payment_years - 5)*(30*flt(salaryperday))
				
	
	max_gratuity = 2 * 12 * 30 * flt(salaryperday)
	gratuity_pay = min(gratuity_pay, max_gratuity)
	
	joiningtext = "Total Working Days: " + str(payment_days) + " - Total Working Years: " + str(round(payment_years,3))
	gratuity_text += appended_gratuity_text
	workingdaystext =  "Total Leave Due: " + str(leavedaysdue) + " - Total Leave Taken: " + str(leavedaystaken) + " - Leave Balance: " + str(leavesbalance)
	networkingdaytext = "Net Working Days: " + str(net_payment_days) + " - Net Working Years: " + str(round(net_payment_years,3))
	gratuity_calculation = joiningtext + "<br>" + workingdaystext + "<br>" + networkingdaytext + "<br><br>" + gratuity_text
	return gratuity_pay, gratuity_calculation, leave_encashment_amount