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

	doctype = filters.get("format")
	if doctype == "Sales Order":
		item_list = frappe.db.sql("select item_code,item_name,description,item_group,stock_uom,warehouse, SUM(qty) AS qty,brand,actual_qty from `tabSales Order Item` t2 where t2.parent in (%s) GROUP BY item_code,warehouse", quotation_names, as_dict = 1)
	elif doctype == "Quotation":
		item_list = frappe.db.sql("select item_code,item_name,description,item_group,stock_uom,warehouse,SUM(qty) AS qty,brand,actual_qty from `tabQuotation Item` t2 where t2.parent in (%s) GROUP BY item_code,warehouse", quotation_names, as_dict = 1)
	elif doctype == "Delivery Note":
		item_list = frappe.db.sql("select item_code,item_name,description,item_group,stock_uom,warehouse,SUM(qty) AS qty,brand,actual_qty from `tabDelivery Note Item` t2 where t2.parent in (%s) GROUP BY item_code,warehouse", quotation_names, as_dict = 1)
	

	all_bom_items = []
	newlist = []
	for i,item in enumerate(item_list):
		if not item.item_group.lower() in headers:
			newlist.append(item)
	
	for item in newlist:
		
		from frappe.utils import strip_html_tags
		item["description"] = strip_html_tags(item["description"])
		item["description"] = item["description"][:55] + (item["description"][55:] and '..')
		
		
		if filters.get("bom_only") == "Without BOM":
			actual_qty = get_actual_qty(item["item_code"])

			if doctype == "Sales Order":
				
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
			else:
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
		
			data.append(row)
		elif filters.get("bom_only") == "With BOM":
			bom = get_default_bom(item["item_code"], project)
			actual_qty = get_actual_qty(item["item_code"])
			
			if doctype == "Sales Order":
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
			else:
				row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
	
			data.append(row)
			
			if bom:
				bomitems = get_bom_items(bom, company=company,qty = item["qty"])
			
				if bomitems:
					row = ["","---------", "","",""]
					data.append(row)
					for b in bomitems:
						actual_qty = get_actual_qty(b["item_code"])
						row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"],actual_qty]
						data.append(row)
					row = ["","---------", "","",""]
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
				
				if doctype == "Sales Order":
					row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
				else:
					row = [item["item_code"],item["item_name"], item["description"],item["stock_uom"],item["qty"],actual_qty]
		
				data.append(row)
				
				bomitems = get_bom_items(bom, company=company,qty = item["qty"])

				if bomitems:
					row = ["","---------", "","",""]
					data.append(row)
					for b in bomitems:
						actual_qty = get_actual_qty(b["item_code"])

						row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"],actual_qty]
						data.append(row)
					row = ["","---------", "","",""]
					data.append(row)			
	
	if filters.get("bom_only") == "Consolidate BOM":
		merged_bom_items = merge(all_bom_items)

		for b in merged_bom_items:
			d = merged_bom_items[b]
			row = [d["item_code"],d["item_name"], d["description"],d["stock_uom"],d["qty"],d["actual_qty"]]
			data.append(row)
	
	return columns, data
	
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
	doctype = filters.get("format")

	if doctype == "Sales Order":
		quotation_list = frappe.db.sql("""select * from `tabSales Order` where %s""" %
			conditions, filters, as_dict=1)
	elif doctype == "Quotation":
		quotation_list = frappe.db.sql("""select * from `tabQuotation` where %s""" %
			conditions, filters, as_dict=1)
	elif doctype == "Delivery Note":
		quotation_list = frappe.db.sql("""select * from `tabDelivery Note` where %s""" %
			conditions, filters, as_dict=1)
	
	return quotation_list

def get_conditions(filters):
	conditions = ""
	
	if not filters.get("name"):
		return conditions,filters
	conditions = "name = %(name)s"	
		

	return conditions, filters