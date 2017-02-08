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
		
		vars = frappe.db.sql("""select payroll_agent_id , payroll_agent_code from `tabEmployee` where employee = %(employee)s LIMIT 1""", {"employee": ss.employee}, as_dict=1)	
		
		
		if vars:
			for d in vars:
				row += [d.payroll_agent_code,d.payroll_agent_id]
		
		row += [ss.employee_name]

		basic_pay = 0
		variable_pay = 0

		for e in earning_types:
			if "salary" in e.lower():
				basic_pay += flt(ss_earning_map.get(ss.name, {}).get(e))
			elif "benefit" in e.lower():
				if not filters.get("alternate"):
					basic_pay += flt(ss_earning_map.get(ss.name, {}).get(e))
	
			
		import math
		basic_pay = math.ceil(basic_pay)			
		variable_pay = flt(ss.rounded_total) - flt(basic_pay)
		if variable_pay < 0:
			basic_pay = basic_pay + variable_pay
			variable_pay = 0
			
		row += [basic_pay,variable_pay]
		
		data.append(row)
	
	return columns, data
	
def get_columns(salary_slips):
	columns = [
		_("Agent Code") + "::140",_("Agent ID") + "::140",_("Employee Name") + "::140"
	]
	
		
	salary_components = {_("Earning"): [], _("Deduction"): []}

	for component in frappe.db.sql("""select distinct sd.salary_component, sc.type
		from `tabSalary Detail` sd, `tabSalary Component` sc
		where sc.name=sd.salary_component and sd.amount != 0 and sd.parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1):
		salary_components[component.type].append(component.salary_component)
		
	columns = columns +	["Basic Pay:Currency:120", "Variable Pay:Currency:120"]

	return columns, salary_components[_("Earning")], salary_components[_("Deduction")]
	
	
	
	

def get_salary_slips(filters):
	conditions, filters = get_conditions(filters)
	salary_slips = frappe.db.sql("""select * from `tabSalary Slip` where docstatus < 2 %s
		order by employee_name""" % conditions, filters, as_dict=1)
	
	return salary_slips
	
def get_conditions(filters):
	conditions = ""
	if filters.get("from_date"): conditions += " and start_date >= %(from_date)s"
	if filters.get("to_date"): conditions += " and end_date <= %(to_date)s"
	
	
	if filters.get("employee"): conditions += " and employee = %(employee)s"
	elif filters.get("company"): conditions += " and company = %(company)s"
	
	return conditions, filters
	
def get_ss_earning_map(salary_slips):

	ss_earnings = frappe.db.sql("""select parent, salary_component, amount 
		from `tabSalary Detail` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)

	
	ss_earning_map = {}
	for d in ss_earnings:
		ss_earning_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		ss_earning_map[d.parent][d.salary_component] = flt(d.amount)
	
	return ss_earning_map

def get_ss_ded_map(salary_slips):
	ss_deductions = frappe.db.sql("""select parent, salary_component, amount 
		from `tabSalary Detail` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	
	ss_ded_map = {}
	for d in ss_deductions:
		ss_ded_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		ss_ded_map[d.parent][d.salary_component] = flt(d.amount)
	
	return ss_ded_map

def get_month_details(year, month):
	ysd = frappe.db.get_value("Fiscal Year", year, "year_start_date")
	if ysd:
		from dateutil.relativedelta import relativedelta
		import calendar, datetime
		diff_mnt = cint(month)-cint(ysd.month)
		if diff_mnt<0:
			diff_mnt = 12-int(ysd.month)+cint(month)
		msd = ysd + relativedelta(months=diff_mnt) # month start date
		month_days = cint(calendar.monthrange(cint(msd.year) ,cint(month))[1]) # days in month
		mid_start = datetime.date(msd.year, cint(month), 16) # month mid start date
		mid_end = datetime.date(msd.year, cint(month), 15) # month mid end date
		med = datetime.date(msd.year, cint(month), month_days) # month end date
		return frappe._dict({
			'year': msd.year,
			'month_start_date': msd,
			'month_end_date': med,
			'month_mid_start_date': mid_start,
			'month_mid_end_date': mid_end,
			'month_days': month_days
		})
	else:
		frappe.throw(_("Fiscal Year {0} not found").format(year))