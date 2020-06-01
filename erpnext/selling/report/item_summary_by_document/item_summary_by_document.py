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
	columns = get_columns(filters)
	data = []

	
	format = filters.get("format")
	name = filters.get("name")
	
	if not name:
		return columns, data
	
	doc_info = frappe.get_doc(format,name)
	
	all_bom_items = []

	project = doc_info.get('project') or None
	company = doc_info.get('company') or get_default_company()
	
	item_list = []
	for item in doc_info.get("items"):
		product_bundle = has_product_bundle(item.item_code,project)
		if product_bundle:
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
					row = [b["item_code"],b["item_name"], b["description"],b["stock_uom"],b["qty"],actual_qty]
					data.append(row)
				row = ["------", "------", "","",""]
				data.append(row)
				
		elif filters.get("bom_only") == "Consolidate BOM":
			for b in bomitems:
				actual_qty = get_actual_qty(b['item_code'])
				all_bom_items.append({'item_code':b['item_code'],'item_name':b['item_name'],'description':b['description'],'stock_uom':b['stock_uom'],'qty':b['qty'],'actual_qty':actual_qty})


	
	if filters.get("bom_only") == "Consolidate BOM":
		merged_bom_items = merge(all_bom_items)

		for key in merged_bom_items:
			d = merged_bom_items[key]
			row = [d["item_code"],d["item_name"], d["description"],d["stock_uom"],d["qty"],d["actual_qty"]]
			data.append(row)
	
	return columns, data
			
def merge(dicts):
	item_dict = {}
	import copy
	new_list = copy.deepcopy(dicts)
	for item in new_list:
		if item_dict.has_key(item.item_code):
			item_dict[item.item_code]["qty"] += flt(item.qty)
		else:
			item_dict[item.item_code] = item
	
	return item_dict

def get_columns(filters):
	columns = [_("Item Code") + ":Link/Item:250",
		_("Item Name") + "::150", _("Description") + "::250",_("UOM") + "::50",
		_("Qty") + ":Float:80",_("Available Qty") + ":Float:80"
	]		
	return columns