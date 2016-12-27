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
	
	project = quotation_list[0]["project"]
	company = quotation_list[0]["company"]

	# title = quotation_list[0]["title"]
	# name =  quotation_list[0]["name"]
	# row = [name,title,project,"",""]
	# data.append(row)
	
	quotation_names = ""
	
	for i, quotation in enumerate(quotation_list):
		quotation_names += str(quotation.name)
		if not i == len(quotation_list)-1:
			quotation_names += ","
			
	headers = ["header1","header2","header3"]

	if filters.get("format") == "Sales Order":
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
		item["description"] = item["description"][:55] + (item["description"][55:] and '..')
		
		
		if filters.get("bom_only") == "Without BOM":
			if filters.get("format") == "Sales Order":
				stock_details = frappe.db.sql("select actual_qty from `tabBin` where item_code = (%s)", item["item_code"], as_dict = 1)
				actual_qty = 0
				if stock_details:
					actual_qty =flt(stock_details[0])
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"], item.delivered_qty, actual_qty]
			else:
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"]]
		
			data.append(row)
		elif filters.get("bom_only") == "Combined":
			from erpnext.manufacturing.doctype.bom.bom import get_bom_items
			bom = frappe.db.get_value("BOM", filters={"item": item["item_code"], "project": project}) or frappe.db.get_value("BOM", filters={"item": item["item_code"], "is_default": 1})
			
			if filters.get("format") == "Sales Order":
				stock_details = frappe.db.sql("select actual_qty from `tabBin` where item_code = (%s)", item["item_code"], as_dict = 1)
				actual_qty = 0
				if stock_details:
					actual_qty =flt(stock_details[0])
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"], item.delivered_qty, actual_qty]
				if bom:
					bomitems = get_bom_items(bom, company=company,qty = item["qty"])

			else:
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"]]
				if bom:
					bomitems = get_bom_items(bom, company=company,qty = item["qty"])
	
			data.append(row)
			
			if bomitems:
				row = [item["item_code"] + " BOM","", "","",""]
				data.append(row)
				for b in bomitems:
					row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"]]
					data.append(row)
				row = ["","", "","",""]
				data.append(row)		
			
		else:
			from erpnext.manufacturing.doctype.bom.bom import get_bom_items
			bom = frappe.db.get_value("BOM", filters={"item": item["item_code"], "project": project}) or frappe.db.get_value("BOM", filters={"item": item["item_code"], "is_default": 1})
			
			if bom:
				if filters.get("format") == "Sales Order":
					stock_details = frappe.db.sql("select actual_qty from `tabBin` where item_code = (%s)", item["item_code"], as_dict = 1)
					actual_qty = 0
					if stock_details:
						actual_qty =flt(stock_details[0])
					row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"], item.delivered_qty, actual_qty]
					bomitems = get_bom_items(bom, company=company,qty = item["qty"])

				else:
					row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"]]
					bomitems = get_bom_items(bom, company=company,qty = item["qty"])
		
				data.append(row)
				
				if bomitems:
					row = [item["item_code"] + " BOM","", "","",""]
					data.append(row)
					for b in bomitems:
						row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"]]
						data.append(row)
					row = ["","", "","",""]
					data.append(row)		
				
	return columns, data
@frappe.whitelist()
def get_title(docname,doctype):

	if doctype == "Sales Order":
		doc = frappe.db.sql("""select title from `tabSales Order` where name = %s""", docname, as_dict=1)
	else:
		doc = frappe.db.sql("""select title from `tabQuotation` where name = %s""", docname, as_dict=1)
	if not doc:
		return ""
	title = docname + ' - ' + doc[0]["title"] 
	
	return title
	
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

	if filters.get("format") == "Sales Order":
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

	if filters.get("format") == "Sales Order":
		quotation_list = frappe.db.sql("""select * from `tabSales Order` where %s""" %
			conditions, filters, as_dict=1)
	else:
		quotation_list = frappe.db.sql("""select * from `tabQuotation` where %s""" %
			conditions, filters, as_dict=1)
	
	return quotation_list

def get_conditions(filters):
	conditions = ""
	
	if not filters.get("name"):
		return conditions,filters
	conditions = "name = %(name)s"	
		

	return conditions, filters