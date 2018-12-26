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
	
	dn_item_list = get_data(conditions, filters)
	
	for dn in dn_item_list:
		docstatus = "Draft"
		if dn.docstatus == 1:
			docstatus = "Submitted"
		row = [dn.name,
		dn.posting_date,
		dn.customer,dn.project,
		dn.base_grand_total,"","",""]
		
		
		
		data.append(row)
		item_list = get_item_data(dn.name)
		for item in item_list:
			
			if filters.get("only_hscode"):
				if item.hs_code and item.hs_code != "":
					item_row = ["",
					"",
					"",
					"","",item.item_code,item.qty,item.hs_code]
					data.append(item_row)
			
			else:
				item_row = ["",
				"",
				"",
				"","",item.item_code,item.qty,item.hs_code]
				data.append(item_row)
				
	
	return columns, data
	
def get_columns(filters):


	columns = [_("DN No.") + ":Link/Delivery Note:150",_("DN Date") + ":Date:100",
	_("Customer") + ":Link/Customer:100",_("Project") + ":Link/Project:150", _("Base Grand Total") + ":Currency:100"
		,_("Item") + ":Link/Item:150",_("Qty") + ":Float:80",_("HS Code") + ":Link/Customs Tariff Number:150"]
		
	return columns
	
def get_data(conditions, filters):

	dn_item_list = frappe.db.sql("""select
		dn.name,
		dn.posting_date,
		dn.customer,
		dn.base_grand_total,
		dn.docstatus,
		dn.project
	from
		`tabDelivery Note` dn
	where %s
	order 
		by dn.name desc
	""" % conditions,filters, as_dict=1)
	return dn_item_list
	
def get_item_data(delivery_note):

	dn_item_list = frappe.db.sql("""select
		dn.item_code,
		dn.qty,
		dn.hs_code
	from
		`tabDelivery Note Item` dn
	where parent = %s
	order 
		by dn.name desc
	""",delivery_note, as_dict=1)
	return dn_item_list

def get_conditions(filters):
	conditions = ""
	
	if filters.get("docstatus") == "Draft":
		conditions += "dn.docstatus = 0"
	elif filters.get("docstatus") == "Submitted":
		conditions += "dn.docstatus = 1"
	elif filters.get("docstatus") == "Draft+Submitted": 
		conditions += "dn.docstatus < 2"
	
	if filters.get("from_date") and filters.get("to_date"): conditions += " and dn.posting_date between %(from_date)s and %(to_date)s"
	
	if filters.get("company"): conditions += " and dn.company = %(company)s"
	
	if filters.get("project"): conditions += " and dn.project = %(project)s"
	
	
	

	return conditions, filters