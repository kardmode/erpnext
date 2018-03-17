# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, flt, getdate, rounded
from erpnext.stock.utils import get_actual_qty
from erpnext.manufacturing.doctype.bom.bom import get_bom_items,get_default_bom
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


	
def get_data(filters,quotation_names,company = None):
	if filters.get("format") == "Sales Order":
		query = 'select item_code,item_name,description,item_group,stock_uom,SUM(qty) AS qty, brand, SUM(delivered_qty) AS delivered_qty from `tabSales Order Item` where  parent IN (%s) GROUP BY item_code' % quotation_names
	elif filters.get("format") == "Delivery Note":
		query = 'select item_code,item_name,description,item_group,stock_uom,SUM(qty) AS qty, brand from `tabDelivery Note Item` where parent IN (%s) GROUP BY item_code' % quotation_names
	else:
		query = 'select item_code,item_name,description,item_group,stock_uom,SUM(qty) AS qty, brand from `tabQuotation Item` where parent IN (%s) GROUP BY item_code' % quotation_names
	
	item_list = frappe.db.sql(query, as_dict = 1)
	project = filters["project"]
	
	all_bom_items = []
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
			actual_qty = get_actual_qty(item["item_code"])
			row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
			
			data.append(row)
		elif filters.get("bom_only") == "Combined":
			
			bom = get_default_bom(item["item_code"], project)			
			actual_qty = get_actual_qty(item["item_code"])
			row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
			if bom:
				bomitems = get_bom_items(bom, company=company,qty = item["qty"])
	
			data.append(row)
			
			if bomitems:
				row = [item["item_code"] + " BOM","", "","",""]
				data.append(row)
				for b in bomitems:
					actual_qty = get_actual_qty(b["item_code"])
					row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"],actual_qty]
					data.append(row)
				row = ["","", "","",""]
				data.append(row)
		elif filters.get("bom_only") == "Consolidate BOM":
			bom = get_default_bom(item["item_code"], project)
			if bom:
				bomitems = get_bom_items(bom, company=company,qty = item["qty"])
				for b in bomitems:
					actual_qty = get_actual_qty(b["item_code"])
					new_bom_item = {'item_code':b['item_code'],'item_name':b["item_name"],'description':b["description"],'stock_uom':b["stock_uom"],'qty':b["qty"],'actual_qty':actual_qty}
					all_bom_items.append(new_bom_item)
					
			
		else:
			bom = get_default_bom(item["item_code"], project)
			
			if bom:
				actual_qty = get_actual_qty(item["item_code"])
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
				bomitems = get_bom_items(bom, company=company,qty = item["qty"])
				
				data.append(row)

				if bomitems:
					row = [item["item_code"] + " BOM","", "","",""]
					data.append(row)
					for b in bomitems:
						actual_qty = get_actual_qty(b["item_code"])
						row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"],actual_qty]
						data.append(row)
					row = ["","", "","",""]
					data.append(row)
					
	if filters.get("bom_only") == "Consolidate BOM":
		merged_bom_items = merge(all_bom_items)
		
		for b in merged_bom_items:
			d = merged_bom_items[b]
			row = [d["item_code"],d["item_name"], d["description"],d["stock_uom"],d["qty"],d["actual_qty"]]
			data.append(row)
	
	return data
	

def merge(dicts):
	item_dict = {}
	for item in dicts:
		if item_dict.has_key(item["item_code"]):
			item_dict[item["item_code"]]["qty"] += flt(item["qty"])
		else:
			item_dict[item["item_code"]] = item
	
	return item_dict


def get_columns(filters):

	doctype = filters.get("format")
	if doctype == "Sales Order":
		columns = [_("Item Code") + ":Link/Item:250",
		_("Item Name") + "::150", _("Description") + "::250",_("UOM") + "::50",
		_("Qty") + "::80",_("Stock Qty") + "::80"
		]
	elif doctype == "Quotation":
		columns = [_("Item Code") + ":Link/Item:250",
		_("Item Name") + "::150", _("Description") + "::250",_("UOM") + "::50",
		_("Qty") + "::80",_("Stock Qty") + "::80"
		]
	elif doctype == "Delivery Note":
		columns = [_("Item Code") + ":Link/Item:250",
		_("Item Name") + "::150", _("Description") + "::250",_("UOM") + "::50",
		_("Qty") + "::80",_("Stock Qty") + "::80"
		]

		
	return columns
	
def get_quotation(conditions, filters):

	if filters.get("format") == "Sales Order":
		quotation_list = frappe.db.sql("""select * from `tabSales Order` where %s and docstatus < 2""" %
			conditions, filters, as_dict=1)
	elif filters.get("format") == "Quotation":
		quotation_list = frappe.db.sql("""select * from `tabQuotation` where %s and docstatus < 2""" %
			conditions, filters, as_dict=1)
	else:
		quotation_list = frappe.db.sql("""select * from `tabDelivery Note` where %s and docstatus < 2""" %
			conditions, filters, as_dict=1)
	
	return quotation_list

def get_conditions(filters):
	conditions = ""
	if not filters.get("project"):
		return conditions,filters
	
	if filters.get("project"): conditions = "project = %(project)s"


	return conditions, filters