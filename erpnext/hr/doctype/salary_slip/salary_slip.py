# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, erpnext
import datetime, math

from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff,money_in_words
from frappe.model.naming import make_autoname
from math import ceil
from datetime import timedelta
from calendar import monthrange


from frappe import msgprint, _
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_start_end_dates
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.utilities.transaction_base import TransactionBase
from frappe.utils.background_jobs import enqueue
from erpnext.hr.doctype.additional_salary.additional_salary import get_additional_salary_component
from erpnext.hr.doctype.payroll_period.payroll_period import get_period_factor, get_payroll_period
from erpnext.hr.doctype.employee_benefit_application.employee_benefit_application import get_benefit_component_amount
from erpnext.hr.doctype.employee_benefit_claim.employee_benefit_claim import get_benefit_claim_amount, get_last_payroll_period_benefits

class SalarySlip(TransactionBase):
	def __init__(self, *args, **kwargs):
		super(SalarySlip, self).__init__(*args, **kwargs)
		# self.series = 'Sal Slip/{0}/.#####'.format(self.employee)
		self.whitelisted_globals = {
			"int": int,
			"float": float,
			"long": int,
			"round": round,
			"date": datetime.date,
			"getdate": getdate
		}


	def validate(self):
		self.status = self.get_status()
		self.validate_dates()
		self.check_existing()
		if not self.salary_slip_based_on_timesheet:
			self.get_date_details()
			
		

		if not (len(self.get("earnings")) or len(self.get("deductions"))):
			# get details from salary structure
			self.get_emp_and_leave_details()
		else:
			self.get_leave_details(lwp = self.leave_without_pay)

		self.calculate_net_pay()

		self.total_in_words = money_in_words(self.rounded_total, erpnext.get_company_currency(self.company))

		if frappe.db.get_single_value("HR Settings", "max_working_hours_against_timesheet"):
			max_working_hours = frappe.db.get_single_value("HR Settings", "max_working_hours_against_timesheet")
			if self.salary_slip_based_on_timesheet and (self.total_working_hours > int(max_working_hours)):
				frappe.msgprint(_("Total working hours should not be greater than max working hours {0}").
								format(max_working_hours), alert=True)
	
	def on_submit(self):
		if self.net_pay < 0:
			frappe.throw(_("Net Pay cannot be less than 0"))
		else:
			self.set_status()
			self.update_status(self.name)
			self.update_salary_slip_in_additional_salary()
			if (frappe.db.get_single_value("HR Settings", "email_salary_slip_to_employee")) and not frappe.flags.via_payroll_entry:
				self.email_salary_slip()

	def on_cancel(self):
		self.set_status()
		self.update_status()
		self.update_salary_slip_in_additional_salary()

	# def on_trash(self):
		# from frappe.model.naming import revert_series_if_last
		# revert_series_if_last(self.series, self.name)

	def get_status(self):
		if self.docstatus == 0:
			status = "Draft"
		elif self.docstatus == 1:
			status = "Submitted"
		elif self.docstatus == 2:
			status = "Cancelled"
		return status

	def validate_dates(self):
		if date_diff(self.end_date, self.start_date) < 0:
			frappe.throw(_("To date cannot be before From date"))

	def check_existing(self):
		if not self.salary_slip_based_on_timesheet:
			ret_exist = frappe.db.sql("""select name from `tabSalary Slip`
						where start_date = %s and end_date = %s and docstatus != 2
						and employee = %s and name != %s""",
						(self.start_date, self.end_date, self.employee, self.name))
			if ret_exist:
				employee = self.employee
				self.employee = ''
				frappe.throw(_("Salary Slip of employee {0} already created for this period").format(employee))
		else:
			for data in self.timesheets:
				if frappe.db.get_value('Timesheet', data.time_sheet, 'status') == 'Payrolled':
					frappe.throw(_("Salary Slip of employee {0} already created for time sheet {1}").format(self.employee, data.time_sheet))

	def get_date_details(self):
		if not self.end_date:
			date_details = get_start_end_dates(self.payroll_frequency, self.start_date or self.posting_date)
			self.start_date = date_details.start_date
			self.end_date = date_details.end_date

	def get_emp_and_leave_details(self):
		'''First time, load all the components from salary structure'''
		if self.employee:
			self.set("earnings", [])
			self.set("deductions", [])
			
			self.pull_emp_details()

			if not self.salary_slip_based_on_timesheet:
				self.get_date_details()
				
			self.validate_dates()
			joining_date, relieving_date = frappe.get_cached_value("Employee", self.employee,
				["date_of_joining", "relieving_date"])
			
			self.get_leave_details(joining_date, relieving_date)
			
			struct = self.check_sal_struct(joining_date, relieving_date)

			if struct:
				self._salary_structure_doc = frappe.get_doc('Salary Structure', struct)
				self.salary_slip_based_on_timesheet = self._salary_structure_doc.salary_slip_based_on_timesheet or 0
				self.set_time_sheet()
				self.pull_sal_struct()
				


	def set_time_sheet(self):
		if self.salary_slip_based_on_timesheet:
			self.set("timesheets", [])
			timesheets = frappe.db.sql(""" select * from `tabTimesheet` where employee = %(employee)s and start_date BETWEEN %(start_date)s AND %(end_date)s and (status = 'Submitted' or
				status = 'Billed')""", {'employee': self.employee, 'start_date': self.start_date, 'end_date': self.end_date}, as_dict=1)

			for data in timesheets:
				self.append('timesheets', {
					'time_sheet': data.name,
					'working_hours': data.total_hours
				})


	def check_sal_struct(self, joining_date, relieving_date):
		cond = """and sa.employee=%(employee)s and (sa.from_date <= %(start_date)s or
				sa.from_date <= %(end_date)s or sa.from_date <= %(joining_date)s)"""
		if self.payroll_frequency:
			cond += """and ss.payroll_frequency = '%(payroll_frequency)s'""" % {"payroll_frequency": self.payroll_frequency}

		st_name = frappe.db.sql("""
			select sa.salary_structure
			from `tabSalary Structure Assignment` sa join `tabSalary Structure` ss
			where sa.salary_structure=ss.name
				and sa.docstatus = 1 and ss.docstatus = 1 and ss.is_active ='Yes' %s
			order by sa.from_date desc
			limit 1
		""" %cond, {'employee': self.employee, 'start_date': self.start_date,
			'end_date': self.end_date, 'joining_date': joining_date})

		
		if st_name:
			self.salary_structure = st_name[0][0]
			return self.salary_structure

		else:
			self.salary_structure = None
			frappe.msgprint(_("No active or default Salary Structure found for employee {0} for the given dates")
				.format(self.employee), title=_('Salary Structure Missing'))			


	def pull_sal_struct(self):
		from erpnext.hr.doctype.salary_structure.salary_structure import make_salary_slip

		if self.salary_slip_based_on_timesheet:
			self.salary_structure = self._salary_structure_doc.name
			self.hour_rate = self._salary_structure_doc.hour_rate
			self.total_working_hours = sum([d.working_hours or 0.0 for d in self.timesheets]) or 0.0
			wages_amount = self.hour_rate * self.total_working_hours

			self.add_earning_for_hourly_wages(self, self._salary_structure_doc.salary_component, wages_amount)

		make_salary_slip(self._salary_structure_doc.name, self)

	def get_leave_details(self, joining_date=None, relieving_date=None, lwp=None, for_preview=0):
		if not joining_date:
			joining_date, relieving_date = frappe.get_cached_value("Employee", self.employee,
				["date_of_joining", "relieving_date"])

		working_days = date_diff(self.end_date, self.start_date) + 1
		if for_preview:
			self.total_working_days = working_days
			self.payment_days = working_days
			return

		holidays = self.get_holidays_for_employee(self.start_date, self.end_date)
		actual_lwp = self.calculate_lwp(holidays, working_days)
		self.on_leave_days = actual_lwp
		self.get_attendance_details()
		
		if not cint(frappe.db.get_value("HR Settings", None, "include_holidays_in_total_working_days")):
			working_days -= len(holidays)
			if working_days < 0:
				frappe.throw(_("There are more holidays than working days this month."))

		if not lwp:
			lwp = actual_lwp
		elif lwp != actual_lwp:
			pass
			# frappe.msgprint(_("Leave Without Pay does not match with approved Leave Application records"))

		self.total_working_days = working_days			
		
		self.leave_without_pay = lwp

		payment_days = flt(self.get_payment_days(joining_date, relieving_date)) - flt(lwp)
		self.payment_days = payment_days > 0 and payment_days or 0
		
		

	def get_payment_days(self, joining_date, relieving_date):
		start_date = getdate(self.start_date)
		if joining_date:
			if getdate(self.start_date) <= joining_date <= getdate(self.end_date):
				start_date = joining_date
			elif joining_date > getdate(self.end_date):
				return 0

		end_date = getdate(self.end_date)
		if relieving_date:
			if getdate(self.start_date) <= relieving_date <= getdate(self.end_date):
				end_date = relieving_date
			elif relieving_date < getdate(self.start_date):
				frappe.throw(_("Employee relieved on {0} must be set as 'Left'")
					.format(relieving_date))

		payment_days = date_diff(end_date, start_date) + 1
		
		
		if not cint(frappe.db.get_value("HR Settings", None, "include_holidays_in_total_working_days")):
			holidays = self.get_holidays_for_employee(start_date, end_date)
			payment_days -= len(holidays)
		return payment_days

	def get_holidays_for_employee(self, start_date, end_date):
		holiday_list = get_holiday_list_for_employee(self.employee)
		holidays = frappe.db.sql_list('''select holiday_date from `tabHoliday`
			where
				parent=%(holiday_list)s
				and holiday_date >= %(start_date)s
				and holiday_date <= %(end_date)s''', {
					"holiday_list": holiday_list,
					"start_date": start_date,
					"end_date": end_date
				})

		holidays = [cstr(i) for i in holidays]

		return holidays

	def calculate_lwp(self, holidays, working_days):
		lwp = 0
		holidays = "','".join(holidays)
		for d in range(working_days):
			dt = add_days(cstr(getdate(self.start_date)), d)
			leave = frappe.db.sql("""
				select t1.name, t1.half_day
				from `tabLeave Application` t1, `tabLeave Type` t2
				where t2.name = t1.leave_type
				and (t2.is_lwp = 1 or t2.is_present_during_period = 0)
				and t1.docstatus < 2
				and t1.status in ('Approved','Back From Leave')
				and t1.employee = %(employee)s
				and CASE WHEN t2.include_holiday != 1 THEN %(dt)s not in ('{0}') and %(dt)s between from_date and to_date and ifnull(t1.salary_slip, '') = ''
				WHEN t2.include_holiday THEN %(dt)s between from_date and to_date and ifnull(t1.salary_slip, '') = ''
				END
				""".format(holidays), {"employee": self.employee, "dt": dt})
			if leave:
				lwp = cint(leave[0][1]) and (lwp + 0.5) or (lwp + 1)
		
		return lwp


	def add_earning_for_hourly_wages(self, doc, salary_component, amount):
		row_exists = False
		for row in doc.earnings:
			if row.salary_component == salary_component:
				row.amount = amount
				row_exists = True
				break

		if not row_exists:
			wages_row = {
				"salary_component": salary_component,
				"abbr": frappe.db.get_value("Salary Component", salary_component, "salary_component_abbr"),
				"amount": self.hour_rate * self.total_working_hours,
				"default_amount": 0.0,
				"additional_amount": 0.0
			}
			doc.append('earnings', wages_row)
		
	def calculate_net_pay(self):
		if self.salary_structure:
			self.calculate_component_amounts()

		self.gross_pay = self.get_component_totals("earnings")
		self.total_deduction = self.get_component_totals("deductions")

		
		# self.set_loan_repayment()

		# self.net_pay = flt(self.gross_pay) - (flt(self.total_deduction) + flt(self.total_loan_repayment))
		
		# disable_rounded_total = cint(frappe.db.get_value("Global Defaults", None, "disable_rounded_total"))
		# self.rounded_total = rounded(self.net_pay,
			# self.precision("net_pay") if disable_rounded_total else 0)
			
		self.net_pay = flt(self.gross_pay) - flt(self.total_deduction)
		self.rounded_total = ceil(self.net_pay)

	def calculate_component_amounts(self):
		if not getattr(self, '_salary_structure_doc', None):
			self._salary_structure_doc = frappe.get_doc('Salary Structure', self.salary_structure)

		payroll_period = get_payroll_period(self.start_date, self.end_date, self.company)

		self.add_structure_components()
		self.add_employee_benefits(payroll_period)
		self.add_additional_salary_components()
		self.add_tax_components(payroll_period)
		self.set_component_amounts_based_on_payment_days()

	def add_structure_components(self):
		data = self.get_data_for_eval()
		for key in ('earnings', 'deductions'):
			for struct_row in self._salary_structure_doc.get(key):
				amount = self.eval_condition_and_formula(struct_row, data)
				# if amount and struct_row.statistical_component == 0:
					# self.update_component_row(struct_row, amount, key)

	def get_data_for_eval(self):
		'''Returns data for evaluating formula'''
		data = frappe._dict()

		data.update(frappe.get_doc("Salary Structure Assignment",
			{"employee": self.employee, "salary_structure": self.salary_structure}).as_dict())

		data.update(frappe.get_doc("Employee", self.employee).as_dict())
		data.update(self.as_dict())

		# set values for components
		salary_components = frappe.get_all("Salary Component", fields=["salary_component_abbr"])
		for sc in salary_components:
			data.setdefault(sc.salary_component_abbr, 0)

		for key in ('earnings', 'deductions'):
			for d in self.get(key):
				data[d.abbr] = d.amount

		return data

	def eval_condition_and_formula(self, d, data):
		try:
			condition = d.condition.strip() if d.condition else None
			if condition:
				if not frappe.safe_eval(condition, self.whitelisted_globals, data):
					return None
			amount = d.amount
			if d.amount_based_on_formula:
				formula = d.formula.strip() if d.formula else None
				if formula:
					amount = flt(frappe.safe_eval(formula, self.whitelisted_globals, data), d.precision("amount"))
			# if amount:
				# data[d.abbr] = amount

			return amount

		except NameError as err:
			frappe.throw(_("Name error: {0}".format(err)))
		except SyntaxError as err:
			frappe.throw(_("Syntax error in formula or condition: {0}".format(err)))
		except Exception as e:
			frappe.throw(_("Error in formula or condition: {0}".format(e)))
			raise

	def add_employee_benefits(self, payroll_period):
		for struct_row in self._salary_structure_doc.get("earnings"):
			if struct_row.is_flexible_benefit == 1:
				if frappe.db.get_value("Salary Component", struct_row.salary_component, "pay_against_benefit_claim") != 1:
					benefit_component_amount = get_benefit_component_amount(self.employee, self.start_date, self.end_date,
						struct_row.salary_component, self._salary_structure_doc, self.payroll_frequency, payroll_period)
					if benefit_component_amount:
						self.update_component_row(struct_row, benefit_component_amount, "earnings")
				else:
					benefit_claim_amount = get_benefit_claim_amount(self.employee, self.start_date, self.end_date, struct_row.salary_component)
					if benefit_claim_amount:
						self.update_component_row(struct_row, benefit_claim_amount, "earnings")

		self.adjust_benefits_in_last_payroll_period(payroll_period)

	def adjust_benefits_in_last_payroll_period(self, payroll_period):
		if payroll_period:
			if (getdate(payroll_period.end_date) <= getdate(self.end_date)):
				last_benefits = get_last_payroll_period_benefits(self.employee, self.start_date, self.end_date,
					payroll_period, self._salary_structure_doc)
				if last_benefits:
					for last_benefit in last_benefits:
						last_benefit = frappe._dict(last_benefit)
						amount = last_benefit.amount
						self.update_component_row(frappe._dict(last_benefit.struct_row), amount, "earnings")

	def add_additional_salary_components(self):
		additional_components = get_additional_salary_component(self.employee, self.start_date, self.end_date)
		if additional_components:
			for additional_component in additional_components:
				amount = additional_component.amount
				overwrite = additional_component.overwrite
				key = "earnings" if additional_component.type == "Earning" else "deductions"
				self.update_component_row(frappe._dict(additional_component.struct_row), amount, key, overwrite=overwrite)

	def add_tax_components(self, payroll_period):
		# Calculate variable_based_on_taxable_salary after all components updated in salary slip
		tax_components, other_deduction_components = [], []
		for d in self._salary_structure_doc.get("deductions"):
			if d.variable_based_on_taxable_salary == 1 and not d.formula and not flt(d.amount):
				tax_components.append(d.salary_component)
			else:
				other_deduction_components.append(d.salary_component)

		if not tax_components:
			tax_components = [d.name for d in frappe.get_all("Salary Component", filters={"variable_based_on_taxable_salary": 1})
				if d.name not in other_deduction_components]

		for d in tax_components:
			tax_amount = self.calculate_variable_based_on_taxable_salary(d, payroll_period)
			tax_row = self.get_salary_slip_row(d)
			self.update_component_row(tax_row, tax_amount, "deductions")

	def update_component_row(self, struct_row, amount, key, overwrite=1):
		component_row = None
		for d in self.get(key):
			if d.salary_component == struct_row.salary_component:
				component_row = d

		if not component_row:
			if amount:
				self.append(key, {
					'amount': amount,
					'default_amount': amount if not struct_row.get("is_additional_component") else 0,
					'depends_on_payment_days' : struct_row.depends_on_payment_days,
					'salary_component' : struct_row.salary_component,
					'abbr' : struct_row.abbr,
					'do_not_include_in_total' : struct_row.do_not_include_in_total,
					'is_tax_applicable': struct_row.is_tax_applicable,
					'is_flexible_benefit': struct_row.is_flexible_benefit,
					'variable_based_on_taxable_salary': struct_row.variable_based_on_taxable_salary,
					'deduct_full_tax_on_selected_payroll_date': struct_row.deduct_full_tax_on_selected_payroll_date,
					'additional_amount': amount if struct_row.get("is_additional_component") else 0
				})
		else:
			if struct_row.get("is_additional_component"):
				if overwrite:
					component_row.additional_amount = amount - component_row.get("default_amount", 0)
				else:
					component_row.additional_amount = amount

				if not overwrite and component_row.default_amount:
					amount += component_row.default_amount
			else:
				component_row.default_amount = amount

			component_row.amount = amount
			component_row.deduct_full_tax_on_selected_payroll_date = struct_row.deduct_full_tax_on_selected_payroll_date

	def calculate_variable_based_on_taxable_salary(self, tax_component, payroll_period):
		if not payroll_period:
			frappe.msgprint(_("Start and end dates not in a valid Payroll Period, cannot calculate {0}.")
				.format(tax_component))
			return

		# Deduct taxes forcefully for unsubmitted tax exemption proof and unclaimed benefits in the last period
		if payroll_period.end_date <= getdate(self.end_date):
			self.deduct_tax_for_unsubmitted_tax_exemption_proof = 1
			self.deduct_tax_for_unclaimed_employee_benefits = 1

		return self.calculate_variable_tax(payroll_period, tax_component)

	def calculate_variable_tax(self, payroll_period, tax_component):
		# get remaining numbers of sub-period (period for which one salary is processed)
		remaining_sub_periods = get_period_factor(self.employee,
			self.start_date, self.end_date, self.payroll_frequency, payroll_period)[1]

		# get taxable_earnings, paid_taxes for previous period
		previous_taxable_earnings = self.get_taxable_earnings_for_prev_period(payroll_period.start_date, self.start_date)
		previous_total_paid_taxes = self.get_tax_paid_in_period(payroll_period.start_date, self.start_date, tax_component)

		# get taxable_earnings for current period (all days)
		current_taxable_earnings = self.get_taxable_earnings()
		future_structured_taxable_earnings = current_taxable_earnings.taxable_earnings * (math.ceil(remaining_sub_periods) - 1)

		# get taxable_earnings, addition_earnings for current actual payment days
		current_taxable_earnings_for_payment_days = self.get_taxable_earnings(based_on_payment_days=1)
		current_structured_taxable_earnings = current_taxable_earnings_for_payment_days.taxable_earnings
		current_additional_earnings = current_taxable_earnings_for_payment_days.additional_income
		current_additional_earnings_with_full_tax = current_taxable_earnings_for_payment_days.additional_income_with_full_tax

		# Get taxable unclaimed benefits
		unclaimed_taxable_benefits = 0
		if self.deduct_tax_for_unclaimed_employee_benefits:
			unclaimed_taxable_benefits = self.calculate_unclaimed_taxable_benefits(payroll_period)
			unclaimed_taxable_benefits += current_taxable_earnings_for_payment_days.flexi_benefits

		# Total exemption amount based on tax exemption declaration
		total_exemption_amount, other_incomes = self.get_total_exemption_amount_and_other_incomes(payroll_period)

		# Total taxable earnings including additional and other incomes
		total_taxable_earnings = previous_taxable_earnings + current_structured_taxable_earnings + future_structured_taxable_earnings \
			+ current_additional_earnings + other_incomes + unclaimed_taxable_benefits - total_exemption_amount

		# Total taxable earnings without additional earnings with full tax
		total_taxable_earnings_without_full_tax_addl_components = total_taxable_earnings - current_additional_earnings_with_full_tax

		# Structured tax amount
		total_structured_tax_amount = self.calculate_tax_by_tax_slab(payroll_period, total_taxable_earnings_without_full_tax_addl_components)
		current_structured_tax_amount = (total_structured_tax_amount - previous_total_paid_taxes) / remaining_sub_periods

		# Total taxable earnings with additional earnings with full tax
		full_tax_on_additional_earnings = 0.0
		if current_additional_earnings_with_full_tax:
			total_tax_amount = self.calculate_tax_by_tax_slab(payroll_period, total_taxable_earnings)
			full_tax_on_additional_earnings = total_tax_amount - total_structured_tax_amount

		current_tax_amount = current_structured_tax_amount + full_tax_on_additional_earnings
		if flt(current_tax_amount) < 0:
			current_tax_amount = 0

		return current_tax_amount

	def get_taxable_earnings_for_prev_period(self, start_date, end_date):
		taxable_earnings = frappe.db.sql("""
			select sum(sd.amount)
			from
				`tabSalary Detail` sd join `tabSalary Slip` ss on sd.parent=ss.name
			where
				sd.parentfield='earnings'
				and sd.is_tax_applicable=1
				and is_flexible_benefit=0
				and ss.docstatus=1
				and ss.employee=%(employee)s
				and ss.start_date between %(from_date)s and %(to_date)s
				and ss.end_date between %(from_date)s and %(to_date)s
			""", {
				"employee": self.employee,
				"from_date": start_date,
				"to_date": end_date
			})
		return flt(taxable_earnings[0][0]) if taxable_earnings else 0

	def get_tax_paid_in_period(self, start_date, end_date, tax_component):
		# find total_tax_paid, tax paid for benefit, additional_salary
		total_tax_paid = flt(frappe.db.sql("""
			select
				sum(sd.amount)
			from
				`tabSalary Detail` sd join `tabSalary Slip` ss on sd.parent=ss.name
			where
				sd.parentfield='deductions'
				and sd.salary_component=%(salary_component)s
				and sd.variable_based_on_taxable_salary=1
				and ss.docstatus=1
				and ss.employee=%(employee)s
				and ss.start_date between %(from_date)s and %(to_date)s
				and ss.end_date between %(from_date)s and %(to_date)s
		""", {
			"salary_component": tax_component,
			"employee": self.employee,
			"from_date": start_date,
			"to_date": end_date
		})[0][0])

		return total_tax_paid

	def get_taxable_earnings(self, based_on_payment_days=0):
		joining_date, relieving_date = frappe.get_cached_value("Employee", self.employee,
			["date_of_joining", "relieving_date"])

		if not relieving_date:
			relieving_date = getdate(self.end_date)

		if not joining_date:
			frappe.throw(_("Please set the Date Of Joining for employee {0}").format(frappe.bold(self.employee_name)))

		taxable_earnings = 0
		additional_income = 0
		additional_income_with_full_tax = 0
		flexi_benefits = 0

		for earning in self.earnings:
			if based_on_payment_days:
				amount, additional_amount = self.get_amount_based_on_payment_days(earning, joining_date, relieving_date)
			else:
				amount, additional_amount = earning.amount, earning.additional_amount

			if earning.is_tax_applicable:
				if additional_amount:
					taxable_earnings += (amount - additional_amount)
					additional_income += additional_amount
					if earning.deduct_full_tax_on_selected_payroll_date:
						additional_income_with_full_tax += additional_amount
					continue

				if earning.is_flexible_benefit:
					flexi_benefits += amount
				else:
					taxable_earnings += amount

		return frappe._dict({
			"taxable_earnings": taxable_earnings,
			"additional_income": additional_income,
			"additional_income_with_full_tax": additional_income_with_full_tax,
			"flexi_benefits": flexi_benefits
		})

	def get_amount_based_on_payment_days(self, row, joining_date, relieving_date):
		amount, additional_amount = row.amount, row.additional_amount
		if (self.salary_structure and
			cint(row.depends_on_payment_days) and cint(self.total_working_days) and
			(not self.salary_slip_based_on_timesheet or
				getdate(self.start_date) < joining_date or
				getdate(self.end_date) > relieving_date
			)):
			
			payment_days = self.payment_days
			total_working_days = self.total_working_days
			
			if payment_days == total_working_days:
				payment_days = 30
			total_working_days = 30
			
			additional_amount = flt((flt(row.additional_amount) * flt(payment_days)
				/ cint(total_working_days)), row.precision("additional_amount"))
			amount = flt((flt(row.default_amount) * flt(payment_days)
				/ cint(total_working_days)), row.precision("amount")) + additional_amount

		elif not self.payment_days and not self.salary_slip_based_on_timesheet and cint(row.depends_on_payment_days):
			amount, additional_amount = 0, 0
		elif not row.amount:
			amount = flt(row.default_amount) + flt(row.additional_amount)

		# apply rounding
		if frappe.get_cached_value("Salary Component", row.salary_component, "round_to_the_nearest_integer"):
			amount, additional_amount = rounded(amount), rounded(additional_amount)

		return amount, additional_amount

	def calculate_unclaimed_taxable_benefits(self, payroll_period):
		# get total sum of benefits paid
		total_benefits_paid = flt(frappe.db.sql("""
			select sum(sd.amount)
			from `tabSalary Detail` sd join `tabSalary Slip` ss on sd.parent=ss.name
			where
				sd.parentfield='earnings'
				and sd.is_tax_applicable=1
				and is_flexible_benefit=1
				and ss.docstatus=1
				and ss.employee=%(employee)s
				and ss.start_date between %(start_date)s and %(end_date)s
				and ss.end_date between %(start_date)s and %(end_date)s
		""", {
			"employee": self.employee,
			"start_date": payroll_period.start_date,
			"end_date": self.start_date
		})[0][0])

		# get total benefits claimed
		total_benefits_claimed = flt(frappe.db.sql("""
			select sum(claimed_amount)
			from `tabEmployee Benefit Claim`
			where
				docstatus=1
				and employee=%s
				and claim_date between %s and %s
		""", (self.employee, payroll_period.start_date, self.end_date))[0][0])

		return total_benefits_paid - total_benefits_claimed

	def get_total_exemption_amount_and_other_incomes(self, payroll_period):
		total_exemption_amount, other_incomes = 0, 0
		if self.deduct_tax_for_unsubmitted_tax_exemption_proof:
			exemption_proof = frappe.db.get_value("Employee Tax Exemption Proof Submission",
				{"employee": self.employee, "payroll_period": payroll_period.name, "docstatus": 1},
				["exemption_amount", "income_from_other_sources"])
			if exemption_proof:
				total_exemption_amount, other_incomes = exemption_proof
		else:
			declaration = frappe.db.get_value("Employee Tax Exemption Declaration",
				{"employee": self.employee, "payroll_period": payroll_period.name, "docstatus": 1},
				["total_exemption_amount", "income_from_other_sources"])
			if declaration:
				total_exemption_amount, other_incomes = declaration

		return total_exemption_amount, other_incomes

	def calculate_tax_by_tax_slab(self, payroll_period, annual_taxable_earning):
		payroll_period_obj = frappe.get_doc("Payroll Period", payroll_period)
		annual_taxable_earning -= flt(payroll_period_obj.standard_tax_exemption_amount)
		data = self.get_data_for_eval()
		data.update({"annual_taxable_earning": annual_taxable_earning})
		taxable_amount = 0
		for slab in payroll_period_obj.taxable_salary_slabs:
			if slab.condition and not self.eval_tax_slab_condition(slab.condition, data):
				continue
			if not slab.to_amount and annual_taxable_earning > slab.from_amount:
				taxable_amount += (annual_taxable_earning - slab.from_amount) * slab.percent_deduction *.01
				continue
			if annual_taxable_earning > slab.from_amount and annual_taxable_earning < slab.to_amount:
				taxable_amount += (annual_taxable_earning - slab.from_amount) * slab.percent_deduction *.01
			elif annual_taxable_earning > slab.from_amount and annual_taxable_earning > slab.to_amount:
				taxable_amount += (slab.to_amount - slab.from_amount) * slab.percent_deduction * .01
		return taxable_amount

	def eval_tax_slab_condition(self, condition, data):
		try:
			condition = condition.strip()
			if condition:
				return frappe.safe_eval(condition, self.whitelisted_globals, data)
		except NameError as err:
			frappe.throw(_("Name error: {0}".format(err)))
		except SyntaxError as err:
			frappe.throw(_("Syntax error in condition: {0}".format(err)))
		except Exception as e:
			frappe.throw(_("Error in formula or condition: {0}".format(e)))
			raise

	def get_salary_slip_row(self, salary_component):
		component = frappe.get_doc("Salary Component", salary_component)
		# Data for update_component_row
		struct_row = frappe._dict()
		struct_row['depends_on_payment_days'] = component.depends_on_payment_days
		struct_row['salary_component'] = component.name
		struct_row['abbr'] = component.salary_component_abbr
		struct_row['do_not_include_in_total'] = component.do_not_include_in_total
		struct_row['is_tax_applicable'] = component.is_tax_applicable
		struct_row['is_flexible_benefit'] = component.is_flexible_benefit
		struct_row['variable_based_on_taxable_salary'] = component.variable_based_on_taxable_salary
		return struct_row

	def get_component_totals(self, component_type):
		total = 0.0
		
		# for d in self.get(component_type):
			

		joining_date, relieving_date = frappe.db.get_value("Employee", self.employee,
				["date_of_joining", "relieving_date"])
		if not joining_date:
			frappe.throw(_("Please set the Date Of Joining for employee {0}").format(frappe.bold(self.employee_name)))

		if relieving_date:
			check_end_date = relieving_date
		else:
			check_end_date = getdate(self.end_date)

		hourlyrate = 0
		salaryperday = 0
		if component_type == 'earnings':
			salaryperday = self.calculate_salary_per_day()
			hourlyrate = flt(salaryperday)/ 9
			self.calculate_leave_and_gratuity(salaryperday,joining_date,relieving_date)
			
		elif component_type == 'deductions':
			self.set_salary_component(component_type,'Loan Repayment',self.custom_get_loan_deductions())	
			

		for d in self.get(component_type):
		
			if component_type == 'earnings':
				if(d.salary_component == "Overtime Weekdays"):
					d.rate = flt(frappe.db.get_single_value("Regulations", "overtime_weekdays_rate"))
					d.default_amount = flt(self.overtime_hours_weekdays) * flt(d.rate) * flt(hourlyrate)
				elif(d.salary_component == "Overtime Fridays"):
					d.rate = flt(frappe.db.get_single_value("Regulations", "overtime_fridays_rate"))
					d.default_amount = flt(self.overtime_hours_fridays) * flt(d.rate) * flt(hourlyrate)
				elif(d.salary_component == "Overtime Holidays"):
					d.rate = flt(frappe.db.get_single_value("Regulations", "overtime_holidays_rate"))
					d.default_amount = flt(self.overtime_hours_holidays) * flt(d.rate) * flt(hourlyrate)
				
				if d.salary_component in ["Overtime Weekdays","Overtime Fridays","Overtime Holidays"]:
					if ((cint(d.depends_on_lwp) == 1 and not self.salary_slip_based_on_timesheet) or 
					getdate(self.start_date) < joining_date or getdate(self.end_date) > check_end_date):
			
			
						payment_days = self.payment_days
						total_working_days = self.total_working_days
					
						if payment_days == total_working_days:
							payment_days = 30
						total_working_days = 30
							
						
						d.amount = rounded((flt(d.default_amount) * flt(payment_days)
							/ cint(total_working_days)), self.precision("amount", component_type))
					
						d.amount = d.amount > 0 and d.amount or 0

					elif not self.payment_days and not self.salary_slip_based_on_timesheet and \
						cint(d.depends_on_lwp):
						d.amount = 0
					elif not d.amount:
						d.amount = d.default_amount
					
			if not d.do_not_include_in_total:
				d.amount = flt(d.amount, d.precision("amount"))
				total += d.amount
				
		return total


	def calculate_salary_per_day(self):
		salaryperday = 0
		hourlyrate = 0	
			
		for d in self.get("earnings"):
			if(d.salary_component == "Basic Salary"):
				salaryperday = 	flt(d.default_amount)/30
				hourlyrate = flt(salaryperday)/ 9
				d.rate = hourlyrate
				break

		if salaryperday == 0:
			frappe.throw(_("No salary per day calculation for employee {0}").format(self.employee))
		
		return salaryperday
		
		
	
	def set_salary_component(self,type,salary_component,amount):
		dtypefound = 0
		for d in self.get(type):
			if d.salary_component == salary_component:
				if dtypefound:
					self.get(type).remove(d)
				else:
					if amount > 0:
						d.default_amount = amount
						dtypefound = 1
						d.amount = d.default_amount

					else:
						self.get(type).remove(d)
		
		if amount > 0:
			if not dtypefound:
				newd = self.append(type, {})
				newd.salary_component = salary_component
				newd.default_amount = amount
				newd.amount = newd.default_amount
		
	
	def calculate_leave_and_gratuity(self,salaryperday,joining_date,relieving_date):

		leave_encashment_amount = 0
		self.leave_calculation = ''
		gratuity_encashment = 0
		# self.gratuity_calculation = ''
		
		if not relieving_date:
			leave_encashment_amount,self.leave_calculation = self.calculate_leaveadvance(salaryperday, joining_date)

		# elif relieving_date <= getdate(self.end_date):
			# gratuity_encashment, self.gratuity_calculation, leave_encashment_amount = calculate_gratuity(self.employee,salaryperday,joining_date, relieving_date)

		
		self.set_salary_component('earnings','Leave Encashment',leave_encashment_amount)		
		# self.set_salary_component('earnings','Gratuity Encashment',gratuity_encashment)	
		


	def custom_get_loan_deductions(self):
		it = self.start_date
		dt = self.end_date
		loandata = frappe.db.sql("""
				select t1.transaction_amount
				from `tabLoan Transaction` t1,`tabMRP Loan Type` t2
				where
				t1.parent = %s
				and t1.transaction_date >= %s 
				and t1.transaction_date <= %s
				and (t2.name = t1.transaction_type and t2.type = 'Deduction' and t2.affect_doctype = 'Salary Slip')
				""", (self.employee,it,dt), as_dict=True)
			
	
		total_loan_deduction = 0
		if loandata:
			for d in loandata:
				total_loan_deduction += d.transaction_amount
		
		return total_loan_deduction
				
			
		


	def set_component_amounts_based_on_payment_days(self):
		joining_date, relieving_date = frappe.get_cached_value("Employee", self.employee,
			["date_of_joining", "relieving_date"])

		if not relieving_date:
			relieving_date = getdate(self.end_date)

		if not joining_date:
			frappe.throw(_("Please set the Date Of Joining for employee {0}").format(frappe.bold(self.employee_name)))

		for component_type in ("earnings", "deductions"):
			for d in self.get(component_type):
				d.amount = self.get_amount_based_on_payment_days(d, joining_date, relieving_date)[0]

	def set_loan_repayment(self):
		self.set('loans', [])
		self.total_loan_repayment = 0
		self.total_interest_amount = 0
		self.total_principal_amount = 0

		for loan in self.get_loan_details():
			self.append('loans', {
				'loan': loan.name,
				'total_payment': loan.total_payment,
				'interest_amount': loan.interest_amount,
				'principal_amount': loan.principal_amount,
				'loan_account': loan.loan_account,
				'interest_income_account': loan.interest_income_account
			})

			self.total_loan_repayment += loan.total_payment
			self.total_interest_amount += loan.interest_amount
			self.total_principal_amount += loan.principal_amount

	def get_loan_details(self):
		return frappe.db.sql("""select rps.principal_amount, rps.interest_amount, l.name,
				rps.total_payment, l.loan_account, l.interest_income_account
			from
				`tabRepayment Schedule` as rps, `tabLoan` as l
			where
				l.name = rps.parent and rps.payment_date between %s and %s and
				l.repay_from_salary = 1 and l.docstatus = 1 and l.applicant = %s""",
			(self.start_date, self.end_date, self.employee), as_dict=True) or []

			
	def calculate_leaveadvance(self, salaryperday, joining_date):
		dt = add_days(self.start_date, self.total_working_days+2)
		
		leaveadvance = 0
		leave_calculation = ''
		
		leave = frappe.db.sql("""
			select t1.from_date,t1.to_date,t1.leave_type,t2.is_paid_in_advance,t2.is_present_during_period
			from `tabLeave Application` t1, `tabLeave Type` t2
			where 
			t2.name = t1.leave_type
			and t2.is_paid_in_advance = 1
			and t1.docstatus < 2
			and t1.status in ('Approved','Back From Leave')
			and t1.employee = %s
			and t1.from_date <= %s
			ORDER BY to_date DESC LIMIT 2""", (self.employee, dt), as_dict=True)
		
		if leave:
			if leave[0].is_present_during_period == 0:
				end_date = leave[0].from_date
				# Relieving date should be decremented since leave applications include the first day
				end_date = end_date - timedelta(days=1)

				if end_date < getdate(self.start_date):
					self.encash_leave = 0
					# frappe.msgprint(_("No leave applications found for this period. Please approve a leave application for this employee"))
					return leaveadvance,leave_calculation
					
				if date_diff(end_date, joining_date) < 365:
					if self.encash_leave:
						leave_calculation = "Less than 1 year leave salary." + "<br>"
					else:
						frappe.msgprint(_("This employee has worked at the company for less than a year."))
						return leaveadvance,leave_calculation
				
				if len(leave)>1:
					# Check for case where employee joining date is greater than previous leave departure date
					if joining_date < getdate(leave[1].from_date):
						# Joining date should be incremented since leave applications include the last day
						start_date = leave[1].to_date + timedelta(days=1)
						# frappe.msgprint(_("Calculating Leave From Date {0} To Date {1}.").format(joining_date,end_date))
					else:
						start_date = joining_date
						# frappe.msgprint(_("Previous application is before employee joining date. Using company joining date."))
				else:
					start_date = joining_date
					# frappe.msgprint(_("No previous application found for this employee. Using company joining date."))


			else:					
				end_date = leave[0].to_date
				start_date = leave[0].from_date
				# frappe.msgprint(_("Special Case: Leave Encashment application dated {0}.").format(end_date))

		else:
			self.encash_leave = 0
			# frappe.msgprint(_("No leave applications found for this period. Please approve a valid leave application for this employee"))
			return leaveadvance,leave_calculation
		
		payment_days = date_diff(end_date, start_date)+1
		leavedaysdue = flt(payment_days)/365 * 30	
		leavedaysdue = ceil(leavedaysdue)
		if leavedaysdue < 30 and leavedaysdue + 2 >= 30:
			leavedaysdue = 30
		
		leaveadvance = flt(leavedaysdue)*flt(salaryperday)
		leaveadvance = rounded(leaveadvance,
			self.precision("net_pay"))
		
		from frappe.utils import formatdate
		
		
	
		
		leave_type_text = ""
		if leave[0].is_present_during_period == False:
			leave_type_text = "Away for Leave"
		else:
			leave_type_text = "Present for Leave"
		header_text = str(leave[0].leave_type) + " - Paid In Advance - " + str(leave_type_text)
		joiningtext = "From Date: " + formatdate(start_date) + " - To Date: " + formatdate(end_date) + " - Total Working Days: " + str(payment_days) 
		workingdaystext =  "Leave Days Due (Rounded): " + str(leavedaysdue)
		leavetext = "30 Days Leave Accumulated Every Year"
		leave_calculation += header_text + "<br>" + joiningtext + " - " + workingdaystext + "<br>" + leavetext + "<br>"
		
		return leaveadvance,leave_calculation
	
	def update_salary_slip_in_additional_salary(self):
		salary_slip = self.name if self.docstatus==1 else None
		frappe.db.sql("""
			update `tabAdditional Salary` set salary_slip=%s
			where employee=%s and payroll_date between %s and %s and docstatus=1
		""", (salary_slip, self.employee, self.start_date, self.end_date))

	def email_salary_slip(self):
		receiver = frappe.db.get_value("Employee", self.employee, "prefered_email")

		if receiver:
			email_args = {
				"recipients": [receiver],
				"message": _("Please see attachment"),
				"subject": 'Salary Slip - from {0} to {1}'.format(self.start_date, self.end_date),
				"attachments": [frappe.attach_print(self.doctype, self.name, file_name=self.name)],
				"reference_doctype": self.doctype,
				"reference_name": self.name
				}
			if not frappe.flags.in_test:
				enqueue(method=frappe.sendmail, queue='short', timeout=300, is_async=True, **email_args)
			else:
				frappe.sendmail(**email_args)
		else:
			msgprint(_("{0}: Employee email not found, hence email not sent").format(self.employee_name))

	def update_status(self, salary_slip=None):
		for data in self.timesheets:
			if data.time_sheet:
				timesheet = frappe.get_doc('Timesheet', data.time_sheet)
				timesheet.salary_slip = salary_slip
				timesheet.flags.ignore_validate_update_after_submit = True
				timesheet.set_status()
				timesheet.save()

	def set_status(self, status=None):
		'''Get and update status'''
		if not status:
			status = self.get_status()
		self.db_set("status", status)


	def process_salary_structure(self, for_preview=0):
		'''Calculate salary after salary structure details have been updated'''
		if not self.salary_slip_based_on_timesheet:
			self.get_date_details()
		self.pull_emp_details()
		self.get_leave_details(for_preview=for_preview)
		self.calculate_net_pay()
			
	def pull_emp_details(self):
		emp = frappe.db.sql("""select employee_name, department,designation,company,bank_name,bank_ac_no from tabEmployee where employee = %(employee)s""",{"employee": self.employee}, as_dict=True)
		if emp:
			employee_data = emp[0]
			self.designation = employee_data["designation"]
			self.department = employee_data["department"]
			self.company = employee_data["company"]
			self.bank_name = employee_data["bank_name"]
			self.bank_account_no = employee_data["bank_ac_no"]
			self.employee_name = employee_data["employee_name"]
			
		self.letter_head = frappe.db.get_value("Company", self.company, "default_letter_head")

	def process_salary_based_on_leave(self, lwp=0):
		self.get_leave_details(lwp=lwp)
		self.calculate_net_pay()
		
		
	def get_attendance_details(self):
		
		self.overtime_hours_weekdays = 0
		self.overtime_hours_fridays	= 0		
		self.overtime_hours_holidays = 0
		self.absent_days = 0
		self.unverified_days = 0
		self.attendance_summary = ''
		
		if self.employee and self.start_date and self.end_date:
			
			import calendar
			month = getdate(self.start_date).month
			month_in_words =  calendar.month_abbr[cint(month)]
			fiscal_year = getdate(self.start_date).year
			
			# header_html = '<div class=""><h2>ATTENDANCE SLIP - {0}. {1}</h2></div></div>'.format(month_in_words,fiscal_year)
			table_header = '<table class="table table-bordered table-condensed"><thead><tr style><th style="width: 15%;line-height:1">{0}</th><th style="width: 12%;line-height:1">{1}</th><th style="width: 12%;line-height:1">{2}</th><th style="width: 15%;line-height:1">{3}</th><th style="width: 15%;line-height:1">{4}</th><th style="width: 15%;line-height:1">{5}</th><th style="width: 15%;line-height:1">{6}</th></tr></thead><tbody>'.format("Date","Arrival","Departure","Normal","OT Weekdays","OT Fridays","OT Holidays")
			table_body = ''
			
			total_absent = 0
			total_present_days = 0
			total_nt = 0
			total_ot = 0
			total_otf = 0
			total_oth = 0
			
			working_days = date_diff(self.end_date, self.start_date)+1

			for d in range(working_days):
				dt = add_days(cstr(getdate(self.start_date)), d)
				
				if getdate(dt) <= getdate(self.end_date):
				
					attendance_list = frappe.db.sql("""select arrival_time,departure_time,normal_time,overtime,overtime_fridays,overtime_holidays, attendance_date, status from tabAttendance where employee = %(employee)s and attendance_date  = %(atendance_date)s order by attendance_date"""
					,{'employee': self.employee, 'atendance_date': dt}, as_dict=1)
					
					details = {}
					if attendance_list:
						details = attendance_list[0]
					
			
					if details:
						total_present_days += 1
						if details.status == "Present":
							if self.enable_attendance:
								self.overtime_hours_weekdays += flt(details.overtime)
								self.overtime_hours_fridays += flt(details.overtime_fridays)
								self.overtime_hours_holidays += flt(details.overtime_holidays)
								
							arrival_time = details.arrival_time
							departure_time = details.departure_time

							arrival_time = str(arrival_time)[:-3]
							departure_time = str(departure_time)[:-3]
						elif details.status in ["Absent"]:
							total_absent = total_absent+1
							arrival_time = "-"
							departure_time = "-"
						elif details.status in ["On Leave"]:
							total_absent = total_absent+1
							arrival_time = "On Leave"
							departure_time = "On Leave"
					
						

						normal_time = flt(details.normal_time)
						overtime = flt(details.overtime)
						overtime_fridays = flt(details.overtime_fridays)
						overtime_holidays = flt(details.overtime_holidays)
					else:
						arrival_time = "--:--"
						departure_time = "--:--"
						normal_time = 0
						overtime = 0
						overtime_fridays = 0
						overtime_holidays = 0
						
						
					total_ot = flt(total_ot) + flt(overtime)
					total_otf = flt(total_otf) + flt(overtime_fridays)
					total_oth = flt(total_oth) + flt(overtime_holidays)
					total_nt = flt(total_ot) + flt(total_otf) +flt(total_oth)

					
					
					textdate = str(getdate(dt).strftime("%a")) + ' ' + str(getdate(dt).day) + ', ' + str(getdate(dt).year)

					table_row = '<tr style><td style="line-height:1">{0}</td><td style="line-height:1">{1}</td><td style="line-height:1">{2}</td><td style="line-height:1">{3}</td><td style="line-height:1">{4}</td><td style="line-height:1">{5}</td><td style="line-height:1">{6}</td></tr>'.format(str(textdate),str(arrival_time),str(departure_time),str(round(normal_time,2)),str(round(overtime,2)),str(round(overtime_fridays,2)),str(round(overtime_holidays,2)))
					table_body = table_body + table_row
					
					
			
			
					
			self.absent_days = flt(total_absent)
			

			self.unverified_days = flt(self.total_working_days) - flt(total_present_days)

			self.overtime_hours_weekdays = flt(self.overtime_hours_weekdays)/ flt(frappe.db.get_single_value("Regulations", "overtime_weekdays_rate"))
			self.overtime_hours_fridays = flt(self.overtime_hours_fridays) / flt(frappe.db.get_single_value("Regulations", "overtime_fridays_rate"))
			self.overtime_hours_holidays = flt(self.overtime_hours_holidays) / flt(frappe.db.get_single_value("Regulations", "overtime_holidays_rate"))
			
			table_space = '<tr style><td style="line-height:1">{0}</td><td style="line-height:1">{1}</td><td style="line-height:1">{2}</td><td style="line-height:1">{3}</td><td style="line-height:1">{4}</td><td style="line-height:1">{5}</td><td style="line-height:1">{6}</td></tr>'.format(str(''),str(''),str(''),str(''),str(''),str(''),str(''))

			table_total = '<tr style="font-weight:bold;"><td style="line-height:1">{0}</td><td style="line-height:1">{1}</td><td style="line-height:1">{2}</td><td style="line-height:1">{3}</td><td style="line-height:1">{4}</td><td style="line-height:1">{5}</td><td style="line-height:1">{6}</td></tr>'.format(str('Total'),str(round(total_nt,2)),str(''),str(''),str(round(total_ot,2)),str(round(total_otf,2)),str(round(total_oth,2)))
			table_end = '</tbody></table>'

			# self.attendance_summary = ''
			self.attendance_summary = table_header + table_body + table_space + table_total + table_end

def unlink_ref_doc_from_salary_slip(ref_no):
	linked_ss = frappe.db.sql_list("""select name from `tabSalary Slip`
	where journal_entry=%s and docstatus < 2""", (ref_no))
	if linked_ss:
		for ss in linked_ss:
			ss_doc = frappe.get_doc("Salary Slip", ss)
			frappe.db.set_value("Salary Slip", ss_doc.name, "journal_entry", "")




			
@frappe.whitelist()			
def calculate_gratuity(employee, salaryperday, joining_date,relieving_date,contract_type = "Limited",reason_for_termination = "Resignation"):

	gratuity_pay = 0
	gratuity_calculation = ''
	leave_encashment_amount = 0
	
	
	if not relieving_date or not joining_date or not employee or salaryperday == 0:
		return gratuity_pay, gratuity_calculation, leave_encashment_amount
		
	# Relieving date is the last day of work
	payment_days = date_diff(relieving_date, joining_date)+1
		
	payment_years = flt(payment_days)/365
	payment_years = rounded(payment_years, 3)
	
	from frappe.utils import formatdate
	joiningtext = "Joining Date: " + formatdate(joining_date) + " - Relieving Date: " + formatdate(relieving_date) + " - Total Working Days: " + str(payment_days) + " - Total Working Years: " + str(payment_years)

	leavedaysdue = 0
	if(payment_years >= 1):
		leavedaysdue = flt(payment_days)/365 * 30
	leavedaysdue = ceil(leavedaysdue)
	
	from erpnext.hr.doctype.leave_application.leave_application \
		import get_approved_leaves_for_period
	
	
	leave_types = frappe.db.sql("""
			select t2.name
			from `tabLeave Type` t2
			where
			t2.is_paid_in_advance = 1""", as_dict=True)
	
	leavedaystaken = 0
	
	for leave_type in leave_types:
		leavedaystaken += get_approved_leaves_for_period(employee, leave_type.name, joining_date, relieving_date)
	leavesbalance = leavedaysdue - leavedaystaken
	
	
	if leavesbalance < 0:
		payment_days += leavesbalance
	else:
		leave_encashment_amount = flt(leavesbalance) * flt(salaryperday)

	leave_encashment_amount = rounded(leave_encashment_amount,3)
		
	payment_years = flt(payment_days)/365
	payment_years = rounded(payment_years,3)
	
	gratuity_text = "Law as of 2018 - Max 2 Years Salary<br>"
	appended_gratuity_text = ""
	
	LR_one = "Less than 1 year, no leave or gratuity<br>"
	LR_less_five = "Between 1 and 5 years: No. of years worked * Basic Salary per day * 21<br>"
	LR_greater_five = "More than 5 years: (5 * Basic Salary per day * 21) + (No. of years worked - 5) * (Basic Salary per day * 30)<br>"

	LT_greater_one = "More than 1 year: No. of years worked * Basic Salary per day * 21<br>"

	UR_less_three = "Between 1 and 3 years: No. of years worked * Basic Salary per day * 21 * 1/3<br>"
	UR_less_five = "Between 3 and 5 years: No. of years worked * Basic Salary per day * 21 * 2/3<br>"
	UR_greater_five = "More than 5 years: (5 * Basic Salary per day * 21) + (No. of years worked - 5) * (Basic Salary per day * 30)<br>"

	UT_less_three = "Between 1 and 3 years: No. of years worked * Basic Salary per day * 21<br>"
	UT_less_five = "Between 3 and 5 years: No. of years worked * Basic Salary per day * 21<br>"
	UT_greater_five = "More than 5 years: (5 * Basic Salary per day * 21) + (No. of years worked - 5) * (Basic Salary per day * 30)<br>"

	
	if contract_type == "Limited":
		if reason_for_termination == "Resignation":
			if(payment_years < 1):
				appended_gratuity_text = LR_one
				gratuity_pay = 0
			elif(payment_years <= 5):
				appended_gratuity_text = LR_less_five
				gratuity_pay = flt(payment_years) * 21 * flt(salaryperday)
			else:
				appended_gratuity_text = LR_greater_five
				gratuity_pay = (5*21*flt(salaryperday)) + (payment_years - 5)*(30*flt(salaryperday))
		elif reason_for_termination == "Termination":
			if(payment_years < 1):
				appended_gratuity_text = LR_one
				gratuity_pay = 0
			else:
				appended_gratuity_text = LT_greater_one
				gratuity_pay = flt(payment_years) * 21 * flt(salaryperday)
	elif contract_type == "Unlimited":
		if reason_for_termination == "Resignation":
			if(payment_years < 1):
				appended_gratuity_text = LR_one
				gratuity_pay = 0
			elif(payment_years <= 3):
				appended_gratuity_text = UR_less_three
				gratuity_pay = flt(payment_years) * 21 * flt(salaryperday) * flt(1/3)
			elif(payment_years <= 5):
				appended_gratuity_text = UR_less_five
				gratuity_pay = flt(payment_years) * 21 * flt(salaryperday) * flt(2/3)
			else:
				appended_gratuity_text = UR_greater_five
				gratuity_pay = (5*21*flt(salaryperday)) + (payment_years - 5)*(30*flt(salaryperday))
		elif reason_for_termination == "Termination":
			if(payment_years < 1):
				appended_gratuity_text = LR_one
				gratuity_pay = 0
			elif(payment_years <= 3):
				appended_gratuity_text = UT_less_three
				gratuity_pay = flt(payment_years) * 21 * flt(salaryperday)
			elif(payment_years <= 5):
				appended_gratuity_text = UT_less_five
				gratuity_pay = flt(payment_years) * 21 * flt(salaryperday)
			else:
				appended_gratuity_text = UT_greater_five
				gratuity_pay = (5*21*flt(salaryperday)) + (payment_years - 5)*(30*flt(salaryperday))
				
	
	max_gratuity= 2*12*30*flt(salaryperday)
	if gratuity_pay > max_gratuity:
		gratuity_pay = max_gratuity
	
	gratuity_text += appended_gratuity_text
	
	gratuity_pay = rounded(gratuity_pay,3)
	workingdaystext =  "Total Leave Due: " + str(leavedaysdue) + " - Total Leave Taken: " + str(leavedaystaken) + " - Leave Balance: " + str(leavesbalance)
	networkingdaytext = "Net Working Days: " + str(payment_days) + " - Net Working Years: " + str(payment_years)
	gratuity_calculation = joiningtext + "<br>" + workingdaystext + "<br>" + networkingdaytext + "<br><br>" + gratuity_text
	return gratuity_pay, gratuity_calculation, leave_encashment_amount

