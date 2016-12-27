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
	
	company = quotation_list[0]["company"]

	
	if filters.get("consolidate") == "Consolidate By Document":
		for i, quotation in enumerate(quotation_list):
		
			quotation_names = "'" + str(quotation.name) + "'"
			row = [quotation.name,quotation.title, "","",""]
			data.append(row)		
			data = data + get_data(filters,quotation_names,company)
			row = ["","","","",""]
			data.append(row)		
		
		return columns, data		
	else:
		quotation_names = ""
		for i, quotation in enumerate(quotation_list):
			quotation_names += "'" + str(quotation.name) + "'"
			if not i == len(quotation_list)-1:
				quotation_names += ","

		data = data + get_data(filters,quotation_names,company)
		return columns, data

@frappe.whitelist()
def get_title(docname,doctype):
	
	doc = frappe.db.sql("""select status from `tabProject` where name = %s and docstatus < 2""", docname, as_dict=1)
	if not doc:
		return ""
	title = doc[0]["status"]
	
	return title
	
def get_data(filters,quotation_names,company = None):
	if filters.get("format") == "SO":
		query = 'select item_code,item_name,description,item_group,stock_uom,SUM(qty) AS qty, brand, SUM(delivered_qty) AS delivered_qty from `tabSales Order Item` where  parent IN (%s) GROUP BY item_code' % quotation_names
	else:
		query = 'select item_code,item_name,description,item_group,stock_uom,SUM(qty) AS qty, brand from `tabQuotation Item` where parent IN (%s) GROUP BY item_code' % quotation_names
	
	item_list = frappe.db.sql(query, as_dict = 1)
	project = filters["project"]
	
	
	newlist = []
	data = []
	headers = ["header1","header2","header3"]
	
	for i,item in enumerate(item_list):
		if not item.item_group.lower() in headers:
			newlist.append(item)
			
	bomitems = {}
	for item in newlist:

		from frappe.utils import strip_html_tags
		item["description"] = strip_html_tags(item["description"])
		item["description"] = item["description"][:55] + (item["description"][55:] and '..')
		
		if filters.get("bom_only") == "Without BOM":
		
			if filters.get("format") == "SO":
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
			frappe.errprint(bom)
			
			if bom:
				if filters.get("format") == "SO":
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
	return data
	

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
		quotation_list = frappe.db.sql("""select * from `tabSales Order` where %s and docstatus < 2""" %
			conditions, filters, as_dict=1)
	else:
		quotation_list = frappe.db.sql("""select * from `tabQuotation` where %s and docstatus < 2""" %
			conditions, filters, as_dict=1)
	
	return quotation_list

def get_conditions(filters):
	conditions = ""
	if not filters.get("project"):
		return conditions,filters
	
	if filters.get("project"): conditions = "project = %(project)s"


	return conditions, filters