# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, flt, getdate
from frappe import msgprint, _
from calendar import monthrange

def execute(filters=None):
	if not filters: filters = {}
	
	salary_slips = get_salary_slips(filters)
	
	if not salary_slips:
		return '', ''
	columns, earning_types, ded_types = get_columns(salary_slips)
	
	
	ss_earning_map = get_ss_earning_map(salary_slips)
	ss_ded_map = get_ss_ded_map(salary_slips)
	

	data = []
	for ss in salary_slips:
		row = []
		
		vars = frappe.db.sql("""select payroll_agent_id , payroll_agent_code, emirates_id, saif_id from `tabEmployee` where employee = %(employee)s LIMIT 1""", {"employee": ss.employee}, as_dict=1)	
		
		
		if vars:
			for d in vars:
				row += [d.payroll_agent_id]
		
		row += [ss.employee_name]

		basic_pay = 0
		variable_pay = 0

		basic_pay = 0
		variable_pay = 0

		for e in earning_types:
			if "salary" in e.lower():
				basic_pay += flt(ss_earning_map.get(ss.name, {}).get(e))
			
		import math
		basic_pay = math.ceil(basic_pay)			
		variable_pay = flt(ss.rounded_total) - flt(basic_pay)
		row += [basic_pay,variable_pay]
		
		data.append(row)
	
	return columns, data
	
def get_columns(salary_slips):
	columns = [
		_("Agent ID") + "::140",_("Employee Name") + "::140"
	]
	
		
	earning_types = frappe.db.sql_list("""select distinct e_type from `tabSalary Slip Earning`
		where e_modified_amount != 0 and parent in (%s)""" % 
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
	
	ded_types = frappe.db.sql_list("""select distinct d_type from `tabSalary Slip Deduction`
		where d_modified_amount != 0 and parent in (%s)""" % 
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
		
	columns = columns +	["Basic Pay:Currency:120", "Variable Pay:Currency:120"]

	return columns, earning_types, ded_types
	
	
	
	

def get_salary_slips(filters):
	conditions, filters = get_conditions(filters)
	salary_slips = frappe.db.sql("""select * from `tabSalary Slip` where docstatus < 2 %s
		order by employee_name, month""" % conditions, filters, as_dict=1)
	
	return salary_slips
	
def get_conditions(filters):
	conditions = ""
	if filters.get("month"):
		month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
			"Dec"].index(filters["month"]) + 1
		filters["month"] = month
		conditions += " and month = %(month)s"
	
	
	
	
	
	if filters.get("fiscal_year"): conditions += " and fiscal_year = %(fiscal_year)s"
	if filters.get("employee"): conditions += " and employee = %(employee)s"
	elif filters.get("company"): conditions += " and company = %(company)s"

	if frappe.db.get_value("Fiscal Year", filters.fiscal_year,"year_start_date"):
		year_start_date, year_end_date = frappe.db.get_value("Fiscal Year", filters.fiscal_year, 
			["year_start_date", "year_end_date"])
	else:
		msgprint(_("Please select a valid year"), raise_exception=1)

	
	if filters.month >= year_start_date.strftime("%m"):
		year = year_start_date.strftime("%Y")
	else:
		year = year_end_date.strftime("%Y")
	
	filters["total_days_in_month"] = monthrange(cint(year), filters.month)[1]
	
	return conditions, filters
	
def get_ss_earning_map(salary_slips):
	ss_earnings = frappe.db.sql("""select parent, e_type, e_modified_amount 
		from `tabSalary Slip Earning` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	
	ss_earning_map = {}
	for d in ss_earnings:
		ss_earning_map.setdefault(d.parent, frappe._dict()).setdefault(d.e_type, [])
		ss_earning_map[d.parent][d.e_type] = flt(d.e_modified_amount)
	
	return ss_earning_map

def get_ss_ded_map(salary_slips):
	ss_deductions = frappe.db.sql("""select parent, d_type, d_modified_amount 
		from `tabSalary Slip Deduction` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	
	ss_ded_map = {}
	for d in ss_deductions:
		ss_ded_map.setdefault(d.parent, frappe._dict()).setdefault(d.d_type, [])
		ss_ded_map[d.parent][d.d_type] = flt(d.d_modified_amount)
	
	return ss_ded_map