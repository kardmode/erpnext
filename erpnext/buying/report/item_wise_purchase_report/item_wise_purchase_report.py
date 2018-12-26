# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, flt, getdate, rounded
from frappe import msgprint, _
def execute(filters=None):
	if not filters: filters = {}
	
	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	
	data = []

	
	po_item_list = get_data(conditions, filters)
	if not po_item_list:
		return columns, data
		
	for i, item in enumerate(po_item_list):
		docstatus = "Draft"
		if item.docstatus == 1:
			docstatus = "Submitted"
		row = [item.name,item.transaction_date,
		item.supplier,docstatus,
		item.project,item.item_code,
		item.item_group,item.uom,
		item.qty,item.base_amount]
		data.append(row)		
	
	return columns, data		


	
def get_columns(filters):


	columns = [_("PO No.") + ":Link/Purchase Order:150",_("PO Date") + ":Date:80",
		_("Supplier") + "::100",_("Status") + "::80",
		_("Project") + ":Link/Project:150",_("Item Code") + ":Link/Item:150",
		_("Group") + "::150",_("UOM") + "::50",
		_("Qty") + ":Float:80",_("Base Amount") + ":Currency:80"
		]
		
	return columns
	
def get_data(conditions, filters):

	po_item_list = frappe.db.sql("""select
		po_item.item_code,
		po_item.item_group,
		po_item.qty,
		po_item.uom,
		po_item.base_rate,
		po_item.base_amount,
		po_item.project,
		po.name,
		po.transaction_date,
		po.supplier,
		po.docstatus
	from
		`tabPurchase Order` po, `tabPurchase Order Item` po_item
	where 
		 po.name = po_item.parent %s
	order 
		by po.name desc
	""" % conditions,filters, as_dict=1)
	
	return po_item_list

def get_conditions(filters):
	conditions = ""
	
	if filters.get("docstatus") == "Draft":
		conditions += "and po.docstatus = 0"
	elif filters.get("docstatus") == "Submitted":
		conditions += "and po.docstatus = 1"
	elif filters.get("docstatus") == "Draft+Submitted": 
		conditions += "and po.docstatus < 2"
	
	if filters.get("from_date") and filters.get("to_date"): conditions += " and po.transaction_date between %(from_date)s and %(to_date)s"
	
	if filters.get("project"): conditions += " and po_item.project = %(project)s"
	
	if filters.get("item_group"): conditions += " and po_item.item_group = %(item_group)s"
	
	if filters.get("company"): conditions += " and po.company = %(company)s"
	
	

	return conditions, filters