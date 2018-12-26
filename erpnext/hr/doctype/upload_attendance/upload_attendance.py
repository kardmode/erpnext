# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt,cstr, add_days, date_diff, get_datetime,getdate,get_time,cstr
from frappe import _
from frappe.utils.csvutils import UnicodeWriter
from frappe.model.document import Document

class UploadAttendance(Document):
	pass

@frappe.whitelist()
def get_template():
	if not frappe.has_permission("Attendance", "create"):
		raise frappe.PermissionError

	args = frappe.local.form_dict

	w = UnicodeWriter()
	w = add_header(w)

	#w = add_data(w, args)

	# write out response as a type csv
	frappe.response['result'] = cstr(w.getvalue())
	frappe.response['type'] = 'csv'
	frappe.response['doctype'] = "Attendance"

def add_header(w):
	w.writerow(["Employee", "Attendance Date", "Arrival Time", "Departure Time"])


	return w

def add_data(w, args):
	dates = get_dates(args)
	employees = get_active_employees()
	existing_attendance_records = get_existing_attendance_records(args)
	for date in dates:
		for employee in employees:
			existing_attendance = {}
			if existing_attendance_records \
				and tuple([date, employee.name]) in existing_attendance_records:
					existing_attendance = existing_attendance_records[tuple([date, employee.name])]
			row = [
				existing_attendance and existing_attendance.name or "",
				employee.name, employee.employee_name, date,
				existing_attendance and existing_attendance.status or "",
				existing_attendance and existing_attendance.leave_type or "", employee.company,
				existing_attendance and existing_attendance.naming_series or get_naming_series(),
			]
			w.writerow(row)
	return w

def get_dates(args):
	"""get list of dates in between from date and to date"""
	no_of_days = date_diff(add_days(args["to_date"], 1), args["from_date"])
	dates = [add_days(args["from_date"], i) for i in range(0, no_of_days)]
	return dates

def get_active_employees():
	employees = frappe.db.sql("""select name, employee_name, company
		from tabEmployee where docstatus < 2 and status = 'Active'""", as_dict=1)
	return employees

def get_existing_attendance_records(args):
	attendance = frappe.db.sql("""select name, attendance_date, employee, status, leave_type, naming_series
		from `tabAttendance` where attendance_date between %s and %s and docstatus < 2""",
		(args["from_date"], args["to_date"]), as_dict=1)

	existing_attendance = {}
	for att in attendance:
		existing_attendance[tuple([att.attendance_date, att.employee])] = att

	return existing_attendance

def get_naming_series():
	series = frappe.get_meta("Attendance").get_field("naming_series").options.strip().split("\n")
	if not series:
		frappe.throw(_("Please setup numbering series for Attendance via Setup > Numbering Series"))
	return series[0]


@frappe.whitelist()
def upload(import_settings = None):
	if not frappe.has_permission("Attendance", "create"):
		raise frappe.PermissionError

	from frappe.utils.csvutils import read_csv_content_from_uploaded_file
	from frappe.modules import scrub

	rows = read_csv_content_from_uploaded_file()
	rows = filter(lambda x: x and any(x), rows)
	if not rows:
		msg = [_("Please select a csv file")]
		return {"messages": msg, "error": msg}
	#fixme error when importing certain header
	#columns = [scrub(f) for f in rows[0]]

	columns = ["employee","attendance_date","arrival_time","departure_time"]

	ret = []
	error = False
	started = False
	
	import json
	params = json.loads(frappe.form_dict.get("params") or '{}')
	
	
	if not params.get("import_settings"):
		import_settings = "default"
	else:
		import_settings = params.get("import_settings")
		
	

	from frappe.utils.csvutils import check_record, import_doc
	
	
	for i, row in enumerate(rows[1:]):
		if not row: continue
		started = True
		row_idx = i + 1
		d = frappe._dict(zip(columns, row))
		d["doctype"] = "Attendance"
		
		if d.arrival_time in ["#--:--","00:00","0:00:00","00:00:0"]:
			d.arrival_time = "00:00:00"
			
		if d.departure_time in ["#--:--","00:00","0:00:00","00:00:0"]:
			d.departure_time = "00:00:00"
			
		d.departure_time = get_time(d.departure_time).strftime("%H:%M:%S")
		d.arrival_time = get_time(d.arrival_time).strftime("%H:%M:%S")
		
		
		if import_settings == "ignore":
			attendance = frappe.db.sql("""select name,docstatus,attendance_date from `tabAttendance` where employee = %s and attendance_date = %s""",
			(d.employee, getdate(d.attendance_date)),as_dict=True)
			if attendance:

				ret.append('Ignored row (#%d) %s : %s' % (row_idx+1,
					len(row)>1 and row[1] or "", cstr(d.employee)))
			else:
				try:
					check_record(d)
					ret.append(import_doc(d, "Attendance", 1, row_idx, submit=False))
				except Exception, e:
					error = True
					ret.append('Error for row (#%d) %s : %s' % (row_idx+1,
						len(row)>1 and row[1] or "", cstr(e)))
					frappe.errprint(frappe.get_traceback())
				
				
		elif import_settings == "update":
			attendance = frappe.db.sql("""select name,docstatus,attendance_date from `tabAttendance` where employee = %s and attendance_date = %s""",
				(d.employee, getdate(d.attendance_date)),as_dict=True)
			
			if attendance:
				d["docstatus"] = attendance[0].docstatus
				d["name"] = attendance[0].name
				
	
		
			try:
				check_record(d)
				ret.append(import_doc(d, "Attendance", 1, row_idx, submit=False))
			except Exception, e:
				error = True
				ret.append('Error for row (#%d) %s : %s' % (row_idx+1,
					len(row)>1 and row[1] or "", cstr(e)))
				frappe.errprint(frappe.get_traceback())
		else:
			try:
				check_record(d)
				ret.append(import_doc(d, "Attendance", 1, row_idx, submit=False))
			except Exception, e:
				error = True
				ret.append('Error for row (#%d) %s : %s' % (row_idx+1,
					len(row)>1 and row[1] or "", cstr(e)))
				frappe.errprint(frappe.get_traceback())
	
	if not started:
		error = True
		ret.append('Error reading csv file')
	


	if error:
		frappe.db.rollback()
	else:
		frappe.db.commit()
	return {"messages": ret, "error": error}
	
@frappe.whitelist()
def update_attendance(start_date,end_date):

	if not start_date or not end_date:
		frappe.throw(_("Please enter both start date and end date"))
		
	attendances = frappe.db.sql("""select name from `tabAttendance` where attendance_date between %s and %s and docstatus < 2""",
		(start_date, end_date), as_dict=1)
	
	summary = ""
			
	
	for att in attendances:
		d = frappe.get_doc("Attendance", att.name)
		
		if d.arrival_time in ["#--:--","00:00","0:00:00","00:00:0"]:
			d.arrival_time = "00:00:00"
			
		if d.departure_time in ["#--:--","00:00","0:00:00","00:00:0"]:
			d.departure_time = "00:00:00"
			
		d.departure_time = get_time(d.departure_time).strftime("%H:%M:%S")
		d.arrival_time = get_time(d.arrival_time).strftime("%H:%M:%S")

		d.save()
		
		new_link = '<a href="#Form/Attendance/{0}">{0} - {1} - {2} - {3}</a><br>'.format(d.name,d.employee,d.employee_name,d.attendance_date)
		summary = summary + new_link
	
	return summary

		
