# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import cstr,time_diff,time_diff_in_seconds,getdate, get_datetime, get_time,flt,cint, nowdate
from frappe import _

class NegativeHoursError(frappe.ValidationError): pass

from frappe.model.document import Document
from erpnext.hr.utils import set_employee_name

class Attendance(Document):
	def validate_duplicate_record(self):
		res = frappe.db.sql("""select name from `tabAttendance` where employee = %s and attendance_date = %s
			and name != %s""",
			(self.employee, self.attendance_date, self.name))

		if res:
			frappe.throw(_("Attendance for employee {0} is already marked, date {1}").format(self.employee,self.attendance_date))

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
		if self.arrival_time == "#--:--" or self.arrival_time == "00:00" or self.arrival_time == "0:00:00":
			self.arrival_time = "00:00:00"
			
		if self.departure_time == "#--:--" or self.departure_time == "00:00" or self.departure_time == "0:00:00":
			self.departure_time = "00:00:00"
		
		
		try:
			totalworkhours = flt(time_diff_in_seconds(self.departure_time,self.arrival_time))/3600
		except:
			try:
				time = time_diff(self.departure_time,self.arrival_time)
				totalworkhours = flt(time.hour) + flt(time.minute)/60 + flt(time.second)/3600
			except:
				frappe.throw(_("Possible error in arrival time {0} or departure time {1} for employee {2}").format(self.arrival_time,self.departure_time,self.employee))

		
		
		
		if totalworkhours < 0:
			frappe.throw(_("Working time cannot be negative. Please check arrival time {0} or departure time {1} for employee {2}").format(self.arrival_time,self.departure_time,self.employee))
		elif totalworkhours > 24:
			frappe.throw(_("Working time cannot be greater than 24. Please check arrival time {0} or departure time {1} for employee {2}").format(self.arrival_time,self.departure_time,self.employee))

		self.working_time = totalworkhours

		weekday = get_datetime(self.attendance_date).weekday()
		
		if not self.department:
			self.department = frappe.db.get_value("Employee", self.employee, "department")
		
		working_hours = frappe.db.sql("""select working_hours from `tabWorking Hours`
				where %s >= from_date AND %s <= to_date and department = %s""", (self.attendance_date,self.attendance_date,self.department))

		if working_hours:
			self.normal_time = flt(working_hours[0][0])
		else:
			self.normal_time = flt(frappe.db.get_single_value("Regulations", "working_hours"))
			
		self.overtime = 0
		self.overtime_fridays = 0
		self.overtime_holidays = 0
		if self.status not in ["On Leave","Half Day"]:
			self.status = 'Present'
		
		if len(self.get_holidays_for_employee(self.attendance_date,self.attendance_date)):
			self.normal_time = 0
			self.overtime_holidays = flt(totalworkhours) - flt(self.normal_time)
		elif weekday == 4:
			self.normal_time = 0
			self.overtime_fridays = flt(totalworkhours) - flt(self.normal_time)
		else:		
			if totalworkhours > self.normal_time:
				self.overtime = flt(totalworkhours) - flt(self.normal_time)
				if self.status == "On Leave":
					frappe.throw(_("Employee on leave this day but has attendance. Please check the time for employee {0}, date {1}").format(self.employee,self.attendance_date))

			elif totalworkhours > 2:
				self.normal_time = totalworkhours
				if self.status == "On Leave":
					frappe.throw(_("Employee on leave this day but has attendance. Please check the time for employee {0}, date {1}").format(self.employee,self.attendance_date))

			elif totalworkhours > 0:
				frappe.throw(_("Work Hours under 2. Please check the time for employee {0}, date {1}").format(self.employee,self.attendance_date))
			elif totalworkhours < 0:
				frappe.throw(_("Work Hours negative. Please check the time for employee {0}, date {1}").format(self.employee,self.attendance_date))
			else:
				if self.arrival_time == "00:00:00" and self.departure_time == "00:00:00":
					self.normal_time = 0
					self.status = 'Absent'
				else:
					frappe.throw(_("Please check the time for employee {0}, date {1}").format(self.employee,self.attendance_date))



		
	def check_leave_record(self):

		leave_record = frappe.db.sql("""select name from `tabLeave Application`
			where employee = %s and %s between from_date and to_date and status = 'Approved'
			and docstatus < 2 and leave_type <> 'Encash Leave'""", (self.employee, self.attendance_date), as_dict=True)

		if leave_record:
			if leave_record[0].half_day:
				self.status = 'Half Day'
				frappe.msgprint(_("Employee {0} on Half day on {1}").format(self.employee, self.attendance_date))
			else:
				self.status = 'On Leave'
				self.leave_type = leave_record[0].leave_type
				frappe.msgprint(_("Employee {0} on Leave on {1}").format(self.employee, self.attendance_date))
		if self.status == "On Leave" and not leave_record:
			frappe.throw(_("No leave record found for employee {0} for {1}").format(self.employee, self.attendance_date))
		

	def validate_attendance_date(self):
		from datetime import timedelta
		date_of_joining = frappe.db.get_value("Employee", self.employee, "date_of_joining")

		if get_datetime(self.attendance_date) > get_datetime(nowdate()) + timedelta(days=30):
			frappe.throw(_("Attendance can not be marked for future dates for employee {0}, date {1}").format(self.employee,self.attendance_date))

		# if getdate(self.attendance_date) > getdate(nowdate()):
			# frappe.throw(_("Attendance can not be marked for future dates for employee {0}, date {1}").format(self.employee,self.attendance_date))				
		elif date_of_joining and getdate(self.attendance_date) < getdate(date_of_joining):
			frappe.throw(_("Attendance date can not be less than employee's joining date"))

	def validate_employee(self):
		emp = frappe.db.sql("select name from `tabEmployee` where name = %s and status = 'Active'",
		 	self.employee)
		if not emp:
			frappe.throw(_("Employee {0} is not active or does not exist").format(self.employee))

	def validate(self):
		self.validate_employee()
		from erpnext.controllers.status_updater import validate_status
		validate_status(self.status, ["Present", "Absent", "On Leave", "Half Day"])
		self.validate_attendance_date()
		self.validate_duplicate_record()
		self.check_leave_record()
		self.calculate_total_hours()
		if self.normal_time < 0:
			frappe.throw(_("Working Time cannot be less than 0, date {0}").format(self.attendance_date))

			

	def on_update(self):
		# this is done because sometimes user entered wrong employee name
		# while uploading employee attendance
		emp = frappe.db.sql("select employee_name,company,department from `tabEmployee` where name = %s",
		 	self.employee, as_dict = 1)
			
		if emp:
			employee_name = emp[0].employee_name
			frappe.db.set(self, 'employee_name', employee_name)
		
			employee_company = emp[0].company
			frappe.db.set(self, 'company', employee_company)
			
			department = emp[0].department
			frappe.db.set(self, 'department', department)

		naming_series = "ATT-"
		frappe.db.set(self, 'naming_series', naming_series)

