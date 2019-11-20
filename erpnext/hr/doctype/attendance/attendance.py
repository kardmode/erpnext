# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import cstr,time_diff,time_diff_in_seconds,getdate, get_datetime, get_time,flt,cint, nowdate,formatdate
from frappe import _

class NegativeHoursError(frappe.ValidationError): pass

from frappe.model.document import Document
from frappe.utils import cstr

class Attendance(Document):
	def validate_duplicate_record(self):
		res = frappe.db.sql("""select name from `tabAttendance` where employee = %s and attendance_date = %s
			and name != %s and docstatus != 2""",
			(self.employee, self.attendance_date, self.name))
		if res:
			frappe.throw(_("Attendance for employee {0} is already marked").format(self.employee))
	
	
	def check_leave_record(self):

		leave_record = frappe.db.sql("""select leave_type, half_day, half_day_date from `tabLeave Application` t1, `tabLeave Type` t2
			where 
			t2.name = t1.leave_type
			and (t2.is_lwp = 1 or t2.is_present_during_period = 0)
			and t1.employee = %s and %s between t1.from_date and t1.to_date and t1.status in ('Approved','Back From Leave')
			and t1.docstatus < 2""", (self.employee, self.attendance_date), as_dict=True)

		if leave_record:
			for d in leave_record:
				if d.half_day_date == getdate(self.attendance_date):
					self.status = 'Half Day'
					frappe.msgprint(_("Employee {0} on Half day on {1}").format(self.employee, self.attendance_date))
				else:
					self.status = 'On Leave'
					self.leave_type = d.leave_type
					frappe.msgprint(_("Employee {0} is on Leave on {1}").format(self.employee, self.attendance_date))

		if self.status == "On Leave" and not leave_record:
			frappe.throw(_("No leave record found for employee {0} for {1}").format(self.employee, self.attendance_date))
		

	def validate_attendance_date(self):
		from datetime import timedelta
		date_of_joining = frappe.db.get_value("Employee", self.employee, "date_of_joining")

		if self.status not in ('On Leave', 'Half Day') and get_datetime(self.attendance_date) > get_datetime(nowdate()) + timedelta(days=30):
			frappe.throw(_("Attendance can not be marked for future dates for employee {0}, date {1}").format(self.employee,self.attendance_date))

		# leaves can be marked for future dates
		# if self.status not in ('On Leave', 'Half Day') and getdate(self.attendance_date) > getdate(nowdate()):
			# frappe.throw(_("Attendance can not be marked for future dates"))
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
	
		if self.arrival_time in ["#--:--","00:00","0:00:00","00:00:0"]:
			self.arrival_time = "00:00:00"
			
		if self.departure_time in ["#--:--","00:00","0:00:00","00:00:0"]:
			self.departure_time = "00:00:00"
		
		try:
			self.departure_time = get_time(self.departure_time ).strftime("%H:%M:%S")
		except Exception, e:
			frappe.throw(_("Possible error in departure time {0} for employee {1}: {2}").format(self.departure_time,self.employee, cstr(e)))
		except ValueError, e:
			frappe.throw(_("Possible error in departure time {0} for employee {1}: {2}").format(self.departure_time,self.employee, cstr(e)))
		except:
			frappe.throw(_("Possible error in departure time {0} for employee {1}: {2}").format(self.departure_time,self.employee))
		
		try:
			self.arrival_time = get_time(self.arrival_time).strftime("%H:%M:%S")
		except Exception, e:
			frappe.throw(_("Possible error in arrival time {0} for employee {1}").format(self.arrival_time,self.employee, cstr(e)))
		except ValueError, e:
			frappe.throw(_("Possible error in arrival time {0} for employee {1}").format(self.arrival_time,self.employee, cstr(e)))
		except:
			frappe.throw(_("Possible error in arrival time {0} for employee {1}").format(self.arrival_time,self.employee))
			
		
		totalworkhours = 0
		try:
			totalworkhours = flt(time_diff_in_seconds(self.departure_time,self.arrival_time))/3600
		except:
			try:
				time = time_diff(self.departure_time,self.arrival_time)
				totalworkhours = flt(time.hour) + flt(time.minute)/60 + flt(time.second)/3600
			except:
				frappe.throw(_("Possible error in arrival time {0} or departure time {1} for employee {2}").format(self.arrival_time,self.departure_time,self.employee))

		
		
		
		if totalworkhours < 0:
			frappe.throw(_("Working time cannot be negative. Please check arrival time {0} or departure time {1} for employee {2} on date {3}").format(self.arrival_time,self.departure_time,self.employee,self.attendance_date))
		elif totalworkhours > 24:
			frappe.throw(_("Working time cannot be greater than 24. Please check arrival time {0} or departure time {1} for employee {2} on date {3}").format(self.arrival_time,self.departure_time,self.employee,self.attendance_date))

		self.working_time = totalworkhours

		weekday = get_datetime(self.attendance_date).weekday()
		
		if not self.department:
			self.department = frappe.db.get_value("Employee", self.employee, "department")
		
		working_hours = frappe.db.sql("""select working_hours from `tabWorking Hours`
				where %s >= from_date AND %s <= to_date and (department = %s or ISNULL(NULLIF(department, '')))""", (self.attendance_date,self.attendance_date,self.department))

		if working_hours:
			self.normal_time = flt(working_hours[0][0])
		else:
			self.normal_time = flt(frappe.db.get_single_value("Regulations", "working_hours"))
			
		self.overtime = 0
		self.overtime_fridays = 0
		self.overtime_holidays = 0
		self.mrp_overtime = 0
		self.mrp_overtime_type = "Weekdays"
		
		if self.status not in ["On Leave","Half Day"]:
			self.status = 'Present'
		
		if len(self.get_holidays_for_employee(self.attendance_date,self.attendance_date)):
			self.normal_time = 0
			self.overtime_holidays = flt(totalworkhours) - flt(self.normal_time)
			self.mrp_overtime = flt(totalworkhours) - flt(self.normal_time)
			self.mrp_overtime_type = "Holidays"
		elif weekday == 4:
			self.normal_time = 0
			self.overtime_fridays = flt(totalworkhours) - flt(self.normal_time)
			self.mrp_overtime = flt(totalworkhours) - flt(self.normal_time)
			self.mrp_overtime_type = "Weekends"
		else:		
			if totalworkhours > self.normal_time:
				self.overtime = flt(totalworkhours) - flt(self.normal_time)
				self.mrp_overtime = flt(totalworkhours) - flt(self.normal_time)
				self.mrp_overtime_type = "Weekdays"
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
					self.working_time = 0
					if self.status != "On Leave":
						self.status = 'Absent'
				else:
					frappe.throw(_("Work Hours equal 0. Please check the time for employee {0}, date {1}, arrival time {2}, departure time {3}").format(self.employee,self.attendance_date,self.arrival_time,self.departure_time))



@frappe.whitelist()
def get_events(start, end, filters=None):
	events = []

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user})

	if not employee:
		return events

	from frappe.desk.reportview import get_filters_cond
	conditions = get_filters_cond("Attendance", filters, [])
	add_attendance(events, start, end, conditions=conditions)
	return events

def add_attendance(events, start, end, conditions=None):
	query = """select name, attendance_date, status
		from `tabAttendance` where
		attendance_date between %(from_date)s and %(to_date)s
		and docstatus < 2"""
	if conditions:
		query += conditions

	for d in frappe.db.sql(query, {"from_date":start, "to_date":end}, as_dict=True):
		e = {
			"name": d.name,
			"doctype": "Attendance",
			"date": d.attendance_date,
			"title": cstr(d.status),
			"docstatus": d.docstatus
		}
		if e not in events:
			events.append(e)


def mark_absent(employee, attendance_date, shift=None):
	employee_doc = frappe.get_doc('Employee', employee)
	if not frappe.db.exists('Attendance', {'employee':employee, 'attendance_date':attendance_date, 'docstatus':('!=', '2')}):
		doc_dict = {
			'doctype': 'Attendance',
			'employee': employee,
			'attendance_date': attendance_date,
			'status': 'Absent',
			'company': employee_doc.company,
			'shift': shift
		}
		attendance = frappe.get_doc(doc_dict).insert()
		attendance.submit()
		return attendance.name
