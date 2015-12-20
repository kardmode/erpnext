# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import getdate, get_datetime, get_time,flt, nowdate
from frappe import _

class NegativeHoursError(frappe.ValidationError): pass

from frappe.model.document import Document
from erpnext.hr.utils import set_employee_name

class Attendance(Document):
	def validate_duplicate_record(self):
		res = frappe.db.sql("""select name from `tabAttendance` where employee = %s and att_date = %s
			and name != %s and docstatus = 1""",
			(self.employee, self.att_date, self.name))
		if res:
			frappe.throw(_("Attendance for employee {0} is already marked").format(self.employee))

		set_employee_name(self)

	def validate_timings(self):
		if self.departure and self.arrival and get_datetime(self.departure) <= get_datetime(self.arrival):
			frappe.throw(_("Departure Time must be greater than Arrival Time"), NegativeHoursError)

	def calculate_total_hours(self):
		weekday = get_datetime(self.att_date).weekday()

		if weekday == 4:
			self.shift = 0
		
		from frappe.utils import time_diff_in_seconds
		totalworkhours = flt(time_diff_in_seconds(self.departure, self.arrival)) / 3600
		if totalworkhours > self.shift:
			self.overtime = flt(totalworkhours) - flt(self.shift)
		else:
			self.overtime = 0
			self.shift = totalworkhours
			
	def check_times(self):
		if self.arrival and self.departure:
			
			self.shift = 10

			from datetime import time

			if get_time(self.arrival) < time(5):
				frappe.throw(_("Arrival Time must be greater than 5"), NegativeHoursError)

			if time(23,55) < get_time(self.departure):
				frappe.throw(_("Departure Time must be less than 23:55"), NegativeHoursError)
				
			self.calculate_total_hours()
			
		else:
			self.status = 'Absent'

			
			

		

		
	def check_leave_record(self):
		if self.status == 'Present':
			leave = frappe.db.sql("""select name from `tabLeave Application`
				where employee = %s and %s between from_date and to_date and status = 'Approved'
				and docstatus = 1""", (self.employee, self.att_date))

			if leave:
				frappe.throw(_("Employee {0} was on leave on {1}. Cannot mark attendance.").format(self.employee,
					self.att_date))

	def validate_att_date(self):
		if getdate(self.att_date) > getdate(nowdate()):
			frappe.throw(_("Attendance can not be marked for future dates"))

	def validate_employee(self):
		emp = frappe.db.sql("select name from `tabEmployee` where name = %s and status = 'Active'",
		 	self.employee)
		if not emp:
			frappe.throw(_("Employee {0} is not active or does not exist").format(self.employee))

	def validate(self):
		from erpnext.controllers.status_updater import validate_status
		from erpnext.accounts.utils import validate_fiscal_year
		validate_status(self.status, ["Present", "Absent", "Half Day"])
		validate_fiscal_year(self.att_date, self.fiscal_year, _("Attendance Date"), self)
		self.validate_att_date()
		self.validate_duplicate_record()
		self.check_leave_record()
		self.check_times()
	

	def on_update(self):
		# this is done because sometimes user entered wrong employee name
		# while uploading employee attendance
		employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")
		frappe.db.set(self, 'employee_name', employee_name)
