# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff
import copy
import json
from frappe.model.document import Document


class EmployeeAttendanceTool(Document):
	def mark_employee_times(self):
		
		employee_list = get_employees_list(self.department,self.branch,self.company)
		#days = date_diff(self.date, self.date)+1
		days = date_diff(self.date, self.date)+1
		for d in range(days):
			dt = add_days(cstr(self.date), d)
			
			for e in employee_list:
				leave = frappe.db.sql("""
				select t1.name
				from `tabAttendance` t1
				where t1.docstatus < 2
				and t1.employee = %s
				and att_date = %s
				""", (e, dt))
				if leave:
					frappe.msgprint(_("Employee %s has a pre-existing attendance record for this date: %s").format(e,dt))
				else:
					attendance = frappe.new_doc("Attendance")
					attendance.employee = employee['employee']
					attendance.employee_name = employee['employee_name']
					attendance.att_date = self.date
					attendance.arrival_time = self.arrival_time
					attendance.departure_time = self.departure_time
					if self.company:
						attendance.company = self.company
					else:
						attendance.company = frappe.db.get_value("Employee", employee['employee'], "Company")
					attendance.submit()
		

@frappe.whitelist()
def get_employees_list(department=None, branch=None, company=None):
	attendance_not_marked = []
	attendance_marked = []
	conditions = {}
	conditions["status"] = "Active"
	if department:
		conditions["department"] = department;
	if branch:
		conditions["branch"] = branch;
	if company:
		conditions["company"] = company;
		
	employee_list = frappe.get_list("Employee", fields=["employee", "employee_name"], filters=conditions, order_by="employee_name")
	
	return employee_list
	
@frappe.whitelist()
def get_employees(date, department=None, branch=None, company=None):
	attendance_not_marked = []
	attendance_marked = []
	conditions = {}
	conditions["status"] = "Active"
	if department:
		conditions["department"] = department;
	if branch:
		conditions["branch"] = branch;
	if company:
		conditions["company"] = company;
		
	employee_list = frappe.get_list("Employee", fields=["employee", "employee_name"], filters=conditions, order_by="employee_name")
	marked_employee = {}
	for emp in frappe.get_list("Attendance", fields=["employee", "status"],
							   filters={"att_date": date}):
		marked_employee[emp['employee']] = emp['status']

	for employee in employee_list:
		employee['status'] = marked_employee.get(employee['employee'])
		if employee['employee'] not in marked_employee:
			attendance_not_marked.append(employee)
		else:
			attendance_marked.append(employee)
	return {
		"marked": attendance_marked,
		"unmarked": attendance_not_marked
	}


@frappe.whitelist()
def mark_employee_attendance(employee_list, status, date, company=None):
	employee_list = json.loads(employee_list)
	for employee in employee_list:
		attendance = frappe.new_doc("Attendance")
		attendance.employee = employee['employee']
		attendance.employee_name = employee['employee_name']
		attendance.att_date = date
		attendance.status = status
		if company:
			attendance.company = company
		else:
			attendance.company = frappe.db.get_value("Employee", employee['employee'], "Company")
		attendance.submit()

