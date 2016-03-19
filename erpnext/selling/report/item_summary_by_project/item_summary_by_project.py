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
	if not conditions:
		return columns, data
	
	quotation_list = get_quotation(conditions, filters)
	project_name = filters["project_name"]
	row = ["",project_name,"","", "" ,"", "","",""]
	data.append(row)
	total_item_list = []
	quotation_names = ""
	
	for i, quotation in enumerate(quotation_list):
		quotation_names += str(quotation.name)
		if not i == len(quotation_list)-1:
			quotation_names += ","

	if filters.get("format") == "SO":
		item_list = frappe.db.sql("select item_code,item_name,description,item_group,SUM(qty) AS qty,brand,SUM(delivered_qty) AS delivered_qty from `tabSales Order Item` t2 where t2.parent in (%s) GROUP BY item_code", quotation_names, as_dict = 1)
	
	else:
		item_list = frappe.db.sql("select item_code,item_name,description,item_group,SUM(qty) AS qty,brand from `tabQuotation Item` t2 where t2.parent in (%s) GROUP BY item_code", quotation_names, as_dict = 1)
	

	list1 = []
	for i,item in enumerate(item_list):
	
		if item.item_group.lower() in ["header1","header2","header3"]:
			item_list.pop(i)
			
		
	for item in item_list:
		
		from frappe.utils import strip_html_tags
		item["description"] = strip_html_tags(item["description"])
		
		if filters.get("format") == "SO":
			row = [item["item_name"], item["description"],item["qty"], item.delivered_qty]
		else:
			row = [item["item_name"], item["description"],item["qty"]]
		
		data.append(row)
				
			
	
				
				
	return columns, data
	
def merge(dicts):
	from collections import defaultdict
	dd = defaultdict(int)
	for d in dicts:
		dd[d['item_name'], d['description'], d['brand']] += d['qty']
		dd[d['item_name'], d['description'], d['brand']] += d['delivered_qty']

	frappe.errprint(dd)
	list2 = [{'item_name': k[0], 'description': k[1],'brand': k[2], 'qty': v} for k, v in dd.iteritems()]
	return list2


def get_columns(filters):

	if filters.get("format") == "SO":
		columns = [
		_("Item Name") + "::150", _("Description") + "::440",
		_("Qty") + "::80",_("Delivered Qty") + "::80"
		]
	else:
		columns = [
		_("Item Name") + "::150", _("Description") + "::440",
		_("Qty") + "::80"
		]

		
	return columns
	
def get_quotation(conditions, filters):

	if filters.get("format") == "SO":
		quotation_list = frappe.db.sql("""select * from `tabSales Order` where %s""" %
			conditions, filters, as_dict=1)
	else:
		quotation_list = frappe.db.sql("""select * from `tabQuotation` where %s""" %
			conditions, filters, as_dict=1)
			
	return quotation_list

def get_conditions(filters):
	conditions = ""
	if not filters.get("project_name"):
		return conditions,filters
	
	if filters.get("project_name"): conditions = "project_name = %(project_name)s"


	return conditions, filters