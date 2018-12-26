# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, flt, getdate, rounded
from frappe import msgprint, _
def execute(filters=None):
	columns, data = [], []
	if not filters: filters = {}
	
	if not filters.get("docstatus"):
		return columns, data
	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	
	data = []

	
	po_item_list = get_data(conditions, filters)
	
	for i, item in enumerate(po_item_list):
		docstatus = "Draft"
		if item.docstatus == 1:
			docstatus = "Submitted"
		row = [item.name,item.transaction_date,
		item.supplier,docstatus,
		item.base_grand_total]
		data.append(row)		
	
	return columns, data		


	
def get_columns(filters):


	columns = [_("PO No.") + ":Link/Purchase Order:150",_("PO Date") + ":Date:80",
	_("Supplier") + "::100",_("Status") + "::80",
		_("Base Grand Total") + ":Currency:80"
		]
		
	return columns
	
def get_data(conditions, filters):

	po_item_list = frappe.db.sql("""select
		po.name,
		po.transaction_date,
		po.supplier,
		po.base_grand_total,
		po.docstatus
	from
		`tabPurchase Order` po
	where %s
	order 
		by po.name desc
	""" % conditions,filters, as_dict=1)
	return po_item_list

def get_conditions(filters):
	conditions = ""
	
	if filters.get("docstatus") == "Draft":
		conditions += "po.docstatus = 0"
	elif filters.get("docstatus") == "Submitted":
		conditions += "po.docstatus = 1"
	elif filters.get("docstatus") == "Draft+Submitted": 
		conditions += "po.docstatus < 2"
	
	if filters.get("from_date") and filters.get("to_date"): conditions += " and po.transaction_date between %(from_date)s and %(to_date)s"
	
	if filters.get("company"): conditions += " and po.company = %(company)s"
	
	
	

	return conditions, filters