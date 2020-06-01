# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, flt, getdate, rounded, strip_html_tags
from frappe import msgprint, _
from erpnext.stock.utils import get_actual_qty
from erpnext import get_default_company
from erpnext.manufacturing.doctype.bom.bom import get_bom_items,get_default_bom
from erpnext.selling.doctype.product_bundle.product_bundle import has_product_bundle
from erpnext.stock.doctype.packed_item.packed_item import get_product_bundle_items


def execute(filters=None):
	if not filters: filters = {}

	
	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	data = []
	
	if not conditions:
		return columns, data
	
	doc_list = get_doc_list(conditions, filters)
	if not doc_list:
		return columns, data
	
	company = None

	if filters.get("consolidate") == "Separate By Document":
		for i, d in enumerate(doc_list):
			company = d.company
			doc_names = "'" + str(d.name) + "'"
			row = [d.name,d.title, "","",""]
			data.append(row)		
			data = data + get_data(filters,doc_names,company)
			row = ["","","","",""]
			data.append(row)		
		
		return columns, data		
	else:
		doc_names = ""
		for i, d in enumerate(doc_list):
			company = d.company
			doc_names += "'" + str(d.name) + "'"
			if not i == len(doc_list)-1:
				doc_names += ","

		data = data + get_data(filters,doc_names,company)
		return columns, data


	
def get_data(filters,doc_names,company = None):

	format = filters.get("format")
	
	original_item_list = frappe.db.sql("""select item_code, item_name, description, item_group, uom, qty, stock_uom, stock_qty 
				from `tab""" + filters.get("format") + """ Item` 
				where parent IN (%s)""" %
				doc_names, filters, as_dict=1)
	
	project = filters.get("project")
	
	all_bom_items = []
	data = []
	
	item_list = []
	for item in original_item_list:
		product_bundle = has_product_bundle(item.item_code,project)
		if product_bundle:
			doc_info = frappe.get_doc(format,item.name)

			if doc_info.get("packed_items"):
				for p in doc_info.get("packed_items"):
					if p.parent_detail_docname == item.name and p.parent_item == item.item_code:
						item_list.append(p)
			else:
				for i in get_product_bundle_items(item.item_code, project):
					i.qty = i.qty * item.qty
					item_list.append(i)
		else:
			item_list.append(item)
	
			
	for item in item_list:

		item_name = item.get("item_name") or item.item_code
		description = item.get("description") or item.item_code
		description = strip_html_tags(description)
		description = description[:55] + (description[55:] and '..')
		actual_qty = get_actual_qty(item.item_code)
		stock_uom = item.get("stock_uom") or 'Nos'
		uom = item.get("uom") or 'Nos'
		
		bom = item.get('bom') or item.get('bom_no') or get_default_bom(item.item_code, project) or None
		bomitems = []
		

		if filters.get("bom_only") in ["Without BOM","With BOM","Only BOM"]:
			if (filters.get("bom_only") == "Only BOM" and bom) or (not filters.get("bom_only") == "Only BOM"):
				row = [item.item_code,item_name, description, uom, item.qty, actual_qty]
				data.append(row)
		
		if filters.get("bom_only") in ["With BOM","Only BOM","Consolidate BOM"]:	
			if bom:
				bomitems = get_bom_items(bom, company=company,qty = item.get("stock_qty") or item.get("qty"))
				
		if filters.get("bom_only") in ["With BOM","Only BOM"]:	
			if bomitems:
				row = ["------", bom, "","",""]
				data.append(row)
				for b in bomitems:
					actual_qty = get_actual_qty(b["item_code"])
					row = [b["item_code"],b["item_name"], b["description"],b["uom"],b["qty"],actual_qty]
					data.append(row)
				row = ["------", "------", "","",""]
				data.append(row)
				
		elif filters.get("bom_only") == "Consolidate BOM":
			for b in bomitems:
				actual_qty = get_actual_qty(b['item_code'])
				all_bom_items.append({'item_code':b['item_code'],'item_name':b['item_name'],'description':b['description'],'uom':b['uom'],'qty':b['qty'],'actual_qty':actual_qty})


					
	if filters.get("bom_only") == "Consolidate BOM":
		merged_bom_items = merge(all_bom_items)
		for b in merged_bom_items:
			d = merged_bom_items[b]
			row = [d["item_code"],d["item_name"], d["description"],d["uom"],d["qty"],d["actual_qty"]]
			data.append(row)
	
	return data
	

def get_columns(filters):
	columns = [_("Item Code") + ":Link/Item:250",
		_("Item Name") + "::150", _("Description") + "::250",_("UOM") + "::50",
		_("Qty") + ":Float:80",_("Available Qty") + ":Float:80"
	]		
	return columns
	
def get_doc_list(conditions, filters):
	return frappe.db.sql("""select name, company from `tab""" + filters.get("format") + """` where  %s docstatus < 2""" % conditions, filters, as_dict=1)

def get_conditions(filters):
	conditions = ""	
	if filters.get("project"): conditions += "project = %(project)s and"
	return conditions, filters
	
def merge(dicts):
	item_dict = {}
	import copy
	new_list = copy.deepcopy(dicts)
	for item in new_list:
		if item_dict.has_key(item["item_code"]):
			item_dict[item["item_code"]]["qty"] += flt(item["qty"])
		else:
			item_dict[item["item_code"]] = item
	
	return item_dict