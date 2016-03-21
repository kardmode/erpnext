# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import cstr,time_diff_in_seconds,getdate, get_datetime, get_time,flt, nowdate
from frappe import _

class NegativeHoursError(frappe.ValidationError): pass

from frappe.model.document import Document
from erpnext.hr.utils import set_employee_name

class Attendance(Document):
	def validate_duplicate_record(self):
		res = frappe.db.sql("""select name from `tabAttendance` where employee = %s and att_date = %s
			and name != %s""",
			(self.employee, self.att_date, self.name))
		if res:
			frappe.throw(_("Attendance for employee {0} is already marked").format(self.employee))

		set_employee_name(self)
	
	def get_holidays_for_employee(self, start_date, end_date):
		holidays = frappe.db.sql("""select t1.holiday_date
			from `tabHoliday` t1, tabEmployee t2
			where t1.parent = t2.holiday_list and t2.name = %s
			and t1.holiday_date between %s and %s""",
			(self.employee, start_date, end_date))
			
		if not holidays:
			holidays = frappe.db.sql("""select t1.holiday_date
				from `tabHoliday` t1, `tabHoliday List` t2
				where t1.parent = t2.name and t2.is_default = 1
				and t1.holiday_date between %s and %s""", 
				(start_date, end_date))
		
		holidays = [cstr(i[0]) for i in holidays]
		return holidays
	
	def calculate_total_hours(self):
		
		if self.arrival_time == "#--:--" or self.departure_time == "#--:--":
			self.arrival_time = "00:00:00"
			self.departure_time = "00:00:00"

		
		totalworkhours = flt(time_diff_in_seconds(self.departure_time,self.arrival_time))/3600
		self.working_time = totalworkhours
		weekday = get_datetime(self.att_date).weekday()
		self.normal_time = 10
		self.overtime = 0
		self.overtime_fridays = 0
		self.overtime_holidays = 0
		self.status = 'Present'
		
		if len(self.get_holidays_for_employee(self.att_date,self.att_date)):
			self.normal_time = 0
			self.overtime_holidays = flt(totalworkhours) - flt(self.normal_time)
		elif weekday == 4:
			self.normal_time = 0
			self.overtime_fridays = flt(totalworkhours) - flt(self.normal_time)
		else:		
			if totalworkhours > self.normal_time:
				self.overtime = flt(totalworkhours) - flt(self.normal_time)
			elif totalworkhours > 0:
				self.normal_time = totalworkhours
			elif totalworkhours < 0:
				self.normal_time = totalworkhours
				self.status = 'Absent'
			else:
				self.normal_time = 0
				self.status = 'Absent'


		
	def check_leave_record(self):
		if self.status == 'Present':
			leave = frappe.db.sql("""select name from `tabLeave Application`
				where employee = %s and %s between from_date and to_date and status = 'Approved'
				and docstatus < 2 and leave_type <> 'Encash Leave'""", (self.employee, self.att_date))

			if leave:
				frappe.throw(_("Employee {0} was on leave on {1}. Cannot mark attendance.").format(self.employee,
					self.att_date))

	def validate_att_date(self):
		pass
		#if getdate(self.att_date) > getdate(nowdate()):
		#	frappe.throw(_("Attendance can not be marked for future dates"))

	def validate_employee(self):
		emp = frappe.db.sql("select name from `tabEmployee` where name = %s and status = 'Active'",
		 	self.employee)
		if not emp:
			frappe.throw(_("Employee {0} is not active or does not exist").format(self.employee))

	def validate(self):
		from erpnext.controllers.status_updater import validate_status
		validate_status(self.status, ["Present", "Absent", "Half Day"])
		self.validate_att_date()
		self.validate_duplicate_record()
		self.check_leave_record()
		self.calculate_total_hours()
		if self.normal_time < 0:
			frappe.throw(_("Working Time cannot be less than 0"))

			

	def on_update(self):
		# this is done because sometimes user entered wrong employee name
		# while uploading employee attendance
		employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")
		frappe.db.set(self, 'employee_name', employee_name)
		
		employee_company = frappe.db.get_value("Employee", self.employee, "company")
		frappe.db.set(self, 'company', employee_company)

		naming_series = "ATT-"
		frappe.db.set(self, 'naming_series', naming_series)
