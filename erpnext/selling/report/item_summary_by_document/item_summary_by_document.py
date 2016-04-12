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
	if not quotation_list:
		return columns, data
	
	#project = filters["project"]

	quotation_names = ""
	
	for i, quotation in enumerate(quotation_list):
		quotation_names += str(quotation.name)
		if not i == len(quotation_list)-1:
			quotation_names += ","
			
	headers = ["header1","header2","header3"]

	if filters.get("format") == "SO":
		item_list = frappe.db.sql("select item_code,item_name,description,item_group,stock_uom, SUM(qty) AS qty,brand,SUM(delivered_qty) AS delivered_qty from `tabSales Order Item` t2 where t2.parent in (%s) GROUP BY item_code", quotation_names, as_dict = 1)

	else:
		item_list = frappe.db.sql("select item_code,item_name,description,item_group,stock_uom,SUM(qty) AS qty,brand from `tabQuotation Item` t2 where t2.parent in (%s) GROUP BY item_code", quotation_names, as_dict = 1)
	

	newlist = []
	for i,item in enumerate(item_list):
		if not item.item_group.lower() in headers:
			newlist.append(item)
			
	bomitems = {}		
	for item in newlist:
		
		from frappe.utils import strip_html_tags
		item["description"] = strip_html_tags(item["description"])
		
		if filters.get("format") == "SO":
			stock_details = frappe.db.sql("select actual_qty from `tabBin` where item_code = (%s)", item["item_code"], as_dict = 1)
			frappe.errprint(stock_details)
			actual_qty =flt(stock_details[0])
			row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"], item.delivered_qty, actual_qty]
		else:
			row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"]]
		
		from erpnext.manufacturing.doctype.bom.bom import get_bom_items
		bom = frappe.db.get_value("BOM", filters={"item": item["item_code"], "project": project}) or frappe.db.get_value("BOM", filters={"item": item["item_code"], "is_default": 1})
		
		frappe.errprint(bom)
		if filters.get("format") == "SO":
			bomitems = get_bom_items(bom, company="Al Maarifa Lab Supplies LLC",qty = item["qty"])
		else:
			bomitems = get_bom_items(bom, company="Al Maarifa Lab Supplies LLC",qty = item["qty"])

		if bomitems:
			row = [item["item_code"] + " BOM","", "","",""]
			data.append(row)
			for b in bomitems:
				row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"]]
				data.append(row)
			row = ["","", "","",""]
			data.append(row)
		
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
		columns = [_("Item Code") + "::150",
		_("Item Name") + "::150", _("Description") + "::340",_("UOM") + "::50",
		_("Qty") + "::80",_("Delivered Qty") + "::80",_("Actual Qty") + "::80"
		]
	else:
		columns = [_("Item Code") + "::150",
		_("Item Name") + "::150", _("Description") + "::340",_("UOM") + "::50",
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
	
	if filters.get("format") == "SO":
		if not filters.get("salesorder"):
			return conditions,filters
		conditions = "name = %(salesorder)s"
	else:
		if not filters.get("quotation"):
				return conditions,filters
		conditions = "name = %(quotation)s"	

	return conditions, filters