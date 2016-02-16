# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import cstr, add_days, date_diff
from frappe import _
from frappe.utils.csvutils import UnicodeWriter
from frappe.model.document import Document

class UploadItemListtoQuotation(Document):
	pass

@frappe.whitelist()
def get_template():
	if not frappe.has_permission("Quotation", "create"):
		raise frappe.PermissionError

	args = frappe.local.form_dict

	w = UnicodeWriter()
	w = add_header(w)

	# write out response as a type csv
	frappe.response['result'] = cstr(w.getvalue())
	frappe.response['type'] = 'csv'
	frappe.response['doctype'] = "Quotation"

def add_header(w):
	w.writerow(["Notes:"])
	w.writerow(["Please do not change the template headings"])
	w.writerow(["If you are overwriting existing records, 'ID' column mandatory"])
	w.writerow(["ID", "Item Code", "Quantity", "Page Break"])
	return w

def add_data(w, args):
	from erpnext.accounts.utils import get_fiscal_year

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
				get_fiscal_year(date)[0], employee.company,
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
	attendance = frappe.db.sql("""select name, att_date, employee, status, naming_series
		from `tabAttendance` where att_date between %s and %s and docstatus < 2""",
		(args["from_date"], args["to_date"]), as_dict=1)

	existing_attendance = {}
	for att in attendance:
		existing_attendance[tuple([att.att_date, att.employee])] = att

	return existing_attendance

def get_naming_series():
	series = frappe.get_meta("Attendance").get_field("naming_series").options.strip().split("\n")
	if not series:
		frappe.throw(_("Please setup numbering series for Attendance via Setup > Numbering Series"))
	return series[0]


@frappe.whitelist()
def upload():
	if not frappe.has_permission("Quotation", "create"):
		raise frappe.PermissionError

	from frappe.utils.csvutils import read_csv_content_from_uploaded_file
	from frappe.modules import scrub

	rows = read_csv_content_from_uploaded_file()
	rows = filter(lambda x: x and any(x), rows)
	if not rows:
		msg = [_("Please select a csv file")]
		return {"messages": msg, "error": msg}
	columns = [scrub(f) for f in rows[0]]
	columns[0] = "item_code"
	ret = []
	error = []
	start_row = 1
	total = len(rows)-1
	
	for i, row in enumerate(rows[start_row:]):
		
		row_idx = i + start_row
		d = frappe._dict(zip(columns, row))
		item = frappe.db.sql("""select name from `tabItem` where name = %s and docstatus < 2""",d.item_code, as_dict=1)
		
		if item:
			newitem = {}
			newitem["item_code"] = item[0].name
			newitem["qty"] = d.quantity
			ret.append(newitem)
		else:
			error.append('Error for row (#%d) %s : Invalid Item Code' % (row_idx,row[0]))		
		

	return {"messages": ret, "error": error}