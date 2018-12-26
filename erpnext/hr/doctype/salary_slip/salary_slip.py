# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, erpnext

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

class SalarySlip(TransactionBase):
	# def autoname(self):
		# self.name = make_autoname(self.employee + '-SS-.#####')
		
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

		# if self.salary_slip_based_on_timesheet or not self.net_pay:
		self.calculate_net_pay()

		self.total_in_words = money_in_words(self.rounded_total, erpnext.get_company_currency(self.company))

		if frappe.db.get_single_value("HR Settings", "max_working_hours_against_timesheet"):
			max_working_hours = frappe.db.get_single_value("HR Settings", "max_working_hours_against_timesheet")
			if self.salary_slip_based_on_timesheet and (self.total_working_hours > int(max_working_hours)):
				frappe.msgprint(_("Total working hours should not be greater than max working hours {0}").
								format(max_working_hours), alert=True)
	

	def validate_dates(self):
		if date_diff(self.end_date, self.start_date) < 0:
			frappe.throw(_("To date cannot be before From date"))

	def calculate_component_amounts(self):
		if not getattr(self, '_salary_structure_doc', None):
			self._salary_structure_doc = frappe.get_doc('Salary Structure', self.salary_structure)

		data = self.get_data_for_eval()

		for key in ('earnings', 'deductions'):
			for struct_row in self._salary_structure_doc.get(key):
				amount = self.eval_condition_and_formula(struct_row, data)
				self.update_component_row(struct_row, amount, key)
				# if amount and struct_row.statistical_component == 0:
					# self.update_component_row(struct_row, amount, key)

	def update_component_row(self, struct_row, amount, key):
		component_row = None
		for d in self.get(key):
			if d.salary_component == struct_row.salary_component:
				component_row = d

		if not component_row:
			self.append(key, {
				'amount': amount,
				'default_amount': amount,
				'depends_on_lwp' : struct_row.depends_on_lwp,
				'salary_component' : struct_row.salary_component,
				'abbr' : struct_row.abbr,
				'do_not_include_in_total' : struct_row.do_not_include_in_total
			})
		else:
			component_row.amount = amount

	def eval_condition_and_formula(self, d, data):
		try:
			condition = d.condition.strip() if d.condition else None
			if condition:
				if not frappe.safe_eval(condition, None, data):
					return None
			amount = d.amount
			if d.amount_based_on_formula:
				formula = d.formula.strip() if d.formula else None
				if formula:
					amount = frappe.safe_eval(formula, None, data)
			# if amount:
				# data[d.abbr] = amount
			data[d.abbr] = amount

			return amount

		except NameError as err:
			frappe.throw(_("Name error: {0}".format(err)))
		except SyntaxError as err:
			frappe.throw(_("Syntax error in formula or condition: {0}".format(err)))
		except Exception as e:
			frappe.throw(_("Error in formula or condition: {0}".format(e)))
			raise

	def get_data_for_eval(self):
		'''Returns data for evaluating formula'''
		data = frappe._dict()

		data.update(frappe.get_doc("Salary Structure Employee",
			{"employee": self.employee, "parent": self.salary_structure}).as_dict())

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
			total_days = 0
			total_nt = 0
			total_ot = 0
			total_otf = 0
			total_oth = 0
			
			working_days = date_diff(self.end_date, self.start_date) + 1
			
			for d in range(working_days):
				dt = add_days(cstr(getdate(self.start_date)), d)
				attendance_list = frappe.db.sql("""select arrival_time,departure_time,normal_time,overtime,overtime_fridays,overtime_holidays, attendance_date, status from tabAttendance where employee = %(employee)s and attendance_date  = %(atendance_date)s order by attendance_date"""
				,{'employee': self.employee, 'atendance_date': dt}, as_dict=1)
				
				details = {}
				if attendance_list:
					details = attendance_list[0]
				
		
				if details:
					total_days += 1
					if details.status == "Present":
						if self.enable_attendance:
							self.overtime_hours_weekdays += flt(details.overtime)
							self.overtime_hours_fridays += flt(details.overtime_fridays)
							self.overtime_hours_holidays += flt(details.overtime_holidays)
					elif details.status in ["Absent","On Leave"]:
						total_absent = total_absent+1
				
					arrival_time = details.arrival_time
					departure_time = details.departure_time

					arrival_time = str(arrival_time)[:-3]
					departure_time = str(departure_time)[:-3]

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

				
				
				
				daynumber = calendar.weekday(cint(fiscal_year),cint(month),cint(d+1))
				dayofweek = str(calendar.day_name[daynumber])[:3]
				textdate = dayofweek + ' ' + str(d+1)

				table_row = '<tr style><td style="line-height:1">{0}</td><td style="line-height:1">{1}</td><td style="line-height:1">{2}</td><td style="line-height:1">{3}</td><td style="line-height:1">{4}</td><td style="line-height:1">{5}</td><td style="line-height:1">{6}</td></tr>'.format(str(textdate),str(arrival_time),str(departure_time),str(round(normal_time,2)),str(round(overtime,2)),str(round(overtime_fridays,2)),str(round(overtime_holidays,2)))
				table_body = table_body + table_row
					
					
			
			
			
			# attendance_details = frappe.db.sql("""select overtime,overtime_fridays,overtime_holidays, attendance_date, status from tabAttendance where employee = %(employee)s and attendance_date BETWEEN %(start_date)s AND %(end_date)s order by attendance_date"""
			# ,{'employee': self.employee, 'start_date': self.start_date, 'end_date': self.end_date}, as_dict=1)
			
			
			# for d in attendance_details:
				# total_days += 1
				# if d.status == "Present":
					# if self.enable_attendance:
						# self.overtime_hours_weekdays += flt(d.overtime)
						# self.overtime_hours_fridays += flt(d.overtime_fridays)
						# self.overtime_hours_holidays += flt(d.overtime_holidays)
				# elif d.status in ["Absent","On Leave"]:
					# total_absent = total_absent+1
			
					
			self.absent_days = flt(total_absent) 
			self.unverified_days = flt(self.total_working_days) - flt(total_days)
			self.overtime_hours_weekdays = flt(self.overtime_hours_weekdays)/ flt(frappe.db.get_single_value("Regulations", "overtime_weekdays_rate"))
			self.overtime_hours_fridays = flt(self.overtime_hours_fridays) / flt(frappe.db.get_single_value("Regulations", "overtime_fridays_rate"))
			self.overtime_hours_holidays = flt(self.overtime_hours_holidays) / flt(frappe.db.get_single_value("Regulations", "overtime_holidays_rate"))
			
			table_space = '<tr style><td style="line-height:1">{0}</td><td style="line-height:1">{1}</td><td style="line-height:1">{2}</td><td style="line-height:1">{3}</td><td style="line-height:1">{4}</td><td style="line-height:1">{5}</td><td style="line-height:1">{6}</td></tr>'.format(str(''),str(''),str(''),str(''),str(''),str(''),str(''))

			table_total = '<tr style="font-weight:bold;"><td style="line-height:1">{0}</td><td style="line-height:1">{1}</td><td style="line-height:1">{2}</td><td style="line-height:1">{3}</td><td style="line-height:1">{4}</td><td style="line-height:1">{5}</td><td style="line-height:1">{6}</td></tr>'.format(str('Total'),str(round(total_nt,2)),str(''),str(''),str(round(total_ot,2)),str(round(total_otf,2)),str(round(total_oth,2)))
			table_end = '</tbody></table>'

			# self.attendance_summary = ''
			self.attendance_summary = table_header + table_body + table_space + table_total + table_end
			
	

	def get_emp_and_leave_details(self):
		'''First time, load all the components from salary structure'''
		if self.employee:
			self.set("earnings", [])
			self.set("deductions", [])
			
			self.pull_emp_details()

			if not self.salary_slip_based_on_timesheet:
				self.get_date_details()
				
			self.validate_dates()
			joining_date, relieving_date = frappe.db.get_value("Employee", self.employee,
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


	def get_date_details(self):
		date_details = get_start_end_dates(self.payroll_frequency, self.start_date or self.posting_date)
		self.start_date = date_details.start_date
		self.end_date = date_details.end_date


	def check_sal_struct(self, joining_date, relieving_date):
		cond = ''
		if self.payroll_frequency:
			cond = """and payroll_frequency = '%(payroll_frequency)s'""" % {"payroll_frequency": self.payroll_frequency}


		st_name = frappe.db.sql("""select parent from `tabSalary Structure Employee`
			where employee=%s and (from_date <= %s or from_date <= %s)
			and (to_date is null or to_date >= %s or to_date >= %s)
			and parent in (select name from `tabSalary Structure`
				where is_active = 'Yes'%s)
			"""% ('%s', '%s', '%s','%s','%s', cond),(self.employee, self.start_date, joining_date, self.end_date, relieving_date))

		
		if st_name:
			if len(st_name) > 1:
				frappe.msgprint(_("Multiple active Salary Structures found for employee {0} for the given dates")
					.format(self.employee), title=_('Warning'))
			return st_name and st_name[0][0] or ''
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

	def process_salary_structure(self):
		'''Calculate salary after salary structure details have been updated'''
		if not self.salary_slip_based_on_timesheet:
			self.get_date_details()
		self.pull_emp_details()
		self.get_leave_details()
		self.calculate_net_pay()

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
				"amount": self.hour_rate * self.total_working_hours
			}
			doc.append('earnings', wages_row)

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
		

	def get_leave_details(self, joining_date=None, relieving_date=None, lwp=None):
	
		self.get_attendance_details()
		
		if not joining_date:
			joining_date, relieving_date = frappe.db.get_value("Employee", self.employee,
				["date_of_joining", "relieving_date"])

		holidays = self.get_holidays_for_employee(self.start_date, self.end_date)
		working_days = date_diff(self.end_date, self.start_date) + 1
		actual_lwp = self.calculate_lwp(holidays, working_days)
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
				and t2.is_lwp = 1
				and t1.docstatus < 2
				and t1.status in ('Approved','Back From Leave')
				and t1.employee = %(employee)s
				and CASE WHEN t2.include_holiday != 1 THEN %(dt)s not in ('{0}') and %(dt)s between from_date and to_date
				WHEN t2.include_holiday THEN %(dt)s between from_date and to_date
				END
				""".format(holidays), {"employee": self.employee, "dt": dt})
			if leave:
				lwp = cint(leave[0][1]) and (lwp + 0.5) or (lwp + 1)
		
		return lwp

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

	def sum_components(self, component_type, total_field):
	
		self.set(total_field, 0)
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
			self.calculate_leave_and_gratuity(salaryperday,joining_date,relieving_date)
			hourlyrate = flt(salaryperday)/ 9
			# self.salary_per_hour = hourlyrate
			# self.ot_rate,self.ot_friday_rate,self.ot_holiday_rate = frappe.db.get_value("Regulations", {"overtime_weekdays_rate", "overtime_fridays_rate", "overtime_holidays_rate"})
			
		elif component_type == 'deductions':
			self.check_loan_deductions()

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
				self.set(total_field, self.get(total_field) + flt(d.amount))


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
			if self.encash_leave:
				leave_encashment_amount,self.leave_calculation = self.calculate_leaveadvance(salaryperday, joining_date)
		# elif relieving_date <= getdate(self.end_date):
			# gratuity_encashment, self.gratuity_calculation, leave_encashment_amount = calculate_gratuity(self.employee,salaryperday,joining_date, relieving_date)

		
		self.set_salary_component('earnings','Leave Encashment',leave_encashment_amount)		
		# self.set_salary_component('earnings','Gratuity Encashment',gratuity_encashment)	
		


	def check_loan_deductions(self):
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
	
		self.set_salary_component('deductions','Loan Repayment',total_loan_deduction)			
			
		

		
	def calculate_net_pay(self):
		if self.salary_structure:
			self.calculate_component_amounts()

		
		
		self.sum_components('earnings', 'gross_pay')
		self.sum_components('deductions', 'total_deduction')
		
		# self.set_loan_repayment()

		# self.net_pay = flt(self.gross_pay) - (flt(self.total_deduction) + flt(self.total_loan_repayment))
		
		# disable_rounded_total = cint(frappe.db.get_value("Global Defaults", None, "disable_rounded_total"))
		# self.rounded_total = rounded(self.net_pay,
			# self.precision("net_pay") if disable_rounded_total else 0)
			
		self.net_pay = flt(self.gross_pay) - flt(self.total_deduction)
		self.rounded_total = ceil(self.net_pay)

	def set_loan_repayment(self):
		self.set('loans', [])
		self.total_loan_repayment = 0
		self.total_interest_amount = 0
		self.total_principal_amount = 0

		for loan in self.get_employee_loan_details():
			self.append('loans', {
				'employee_loan': loan.name,
				'total_payment': loan.total_payment,
				'interest_amount': loan.interest_amount,
				'principal_amount': loan.principal_amount,
				'employee_loan_account': loan.employee_loan_account,
				'interest_income_account': loan.interest_income_account
			})

			self.total_loan_repayment += loan.total_payment
			self.total_interest_amount += loan.interest_amount
			self.total_principal_amount += loan.principal_amount

	def get_employee_loan_details(self):
		return frappe.db.sql("""select rps.principal_amount, rps.interest_amount, el.name,
				rps.total_payment, el.employee_loan_account, el.interest_income_account
			from
				`tabRepayment Schedule` as rps, `tabEmployee Loan` as el
			where
				el.name = rps.parent and rps.payment_date between %s and %s and
				el.repay_from_salary = 1 and el.docstatus = 1 and el.employee = %s""",
			(self.start_date, self.end_date, self.employee), as_dict=True) or []

		


			
			
	def calculate_leaveadvance(self, salaryperday, joining_date):
		dt = add_days(self.start_date, self.total_working_days+2)
		
		leaveadvance = 0
		leave_calculation = ''
		
		leave = frappe.db.sql("""
			select from_date,to_date,leave_type
			from `tabLeave Application` t1
			where (t1.leave_type = 'Vacation Leave' OR t1.leave_type = 'Encash Leave')
			and t1.docstatus < 2
			and t1.status in ('Approved','Back From Leave')
			and t1.employee = %s
			and t1.from_date <= %s
			ORDER BY to_date DESC LIMIT 2""", (self.employee, dt), as_dict=True)
		
		
		if leave:
			if leave[0].leave_type == "Vacation Leave":
				end_date = leave[0].from_date
				# Relieving date should be decremented since leave applications include the first day
				end_date = end_date - timedelta(days=1)

				if end_date < getdate(self.start_date):
					self.encash_leave = 0
					frappe.msgprint(_("No leave applications found for this period. Please approve a leave application for this employee"))
					return leaveadvance,leave_calculation
					
				if date_diff(end_date, joining_date) < 365:
					frappe.msgprint(_("This employee has worked at the company for less than a year."))
				
				if len(leave)>1:
					joining_date = leave[1].to_date
					
					# Joining date should be incremented since leave applications include the last day
					joining_date = joining_date + timedelta(days=1)
					frappe.msgprint(_("Calculating Leave From Date {0} To Date {1}.").format(joining_date,end_date))
				else:
					frappe.msgprint(_("No previous application found for this employee. Using company joining date."))


			elif leave[0].leave_type == "Encash Leave":					
				end_date = leave[0].to_date
				joining_date = leave[0].from_date
				frappe.msgprint(_("Special Case: Leave Encashment application dated {0}.").format(end_date))
			else:
				self.encash_leave = 0
				frappe.msgprint(_("No VACATION/ENCASH leave applications found for this period. Change LEAVE WITHOUT PAY Applications to VACATION/ENCASH"))
				return leaveadvance,leave_calculation
		else:
			self.encash_leave = 0
			frappe.msgprint(_("No leave applications found for this period. Please approve a valid leave application for this employee"))
			return leaveadvance,leave_calculation
		
		payment_days = date_diff(end_date, joining_date)+1
		leavedaysdue = flt(payment_days)/365 * 30	
		leavedaysdue = ceil(leavedaysdue)
		if leavedaysdue < 30 and leavedaysdue + 2 >= 30:
			leavedaysdue = 30
		
		leaveadvance = flt(leavedaysdue)*flt(salaryperday)
		leaveadvance = rounded(leaveadvance,
			self.precision("net_pay"))
		
		from frappe.utils import formatdate

		joiningtext = "From Date: " + formatdate(joining_date) + " - To Date: " + formatdate(end_date) + " - Total Working Days: " + str(payment_days) 
		workingdaystext =  "Leave Days Due (Rounded): " + str(leavedaysdue)
		leavetext = "30 Days Leave Accumulated Every Year"
		leave_calculation = joiningtext + " - " + workingdaystext + "<br>" + leavetext + "<br>"
		
		return leaveadvance,leave_calculation
	


			

	def on_submit(self):
		if self.net_pay < 0:
			frappe.throw(_("Net Pay cannot be less than 0"))
		else:
			self.set_status()
			self.update_status(self.name)
			if(frappe.db.get_single_value("HR Settings", "email_salary_slip_to_employee")):
				self.email_salary_slip()

	def on_cancel(self):
		self.set_status()
		self.update_status()

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
			enqueue(method=frappe.sendmail, queue='short', timeout=300, async=True, **email_args)
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

	def get_status(self):
		if self.docstatus == 0:
			status = "Draft"
		elif self.docstatus == 1:
			status = "Submitted"
		elif self.docstatus == 2:
			status = "Cancelled"
		return status

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
	leave_type = "Vacation Leave"
	leavedaystaken = get_approved_leaves_for_period(employee, leave_type, 
			joining_date, relieving_date)
	leave_type = "Encash Leave"				
	leavedaystaken += flt(get_approved_leaves_for_period(employee, leave_type, joining_date, relieving_date))
	
	leave_type = "Leave Without Pay"
	leavedaystaken += flt(get_approved_leaves_for_period(employee, leave_type, joining_date, relieving_date))

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
