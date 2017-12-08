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
				
	return columns, data

	
# def get_raw_materials(bom_dict,use_multi_level_bom = 0,only_raw_materials=0,include_subcontracted=0,non_stock_item=0):
	# """ Get raw materials considering sub-assembly items
		# {
			# "item_code": [qty_required, description, stock_uom, min_order_qty]
		# }
	# """
	# item_list = []

	# for bom, so_wise_qty in bom_dict.items():
		# bom_wise_item_details = {}
		# if use_multi_level_bom and only_raw_materials and include_subcontracted:
			# # get all raw materials with sub assembly childs
			# # Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
			# for d in frappe.db.sql("""select fb.item_code,
				# ifnull(sum(fb.qty/ifnull(bom.quantity, 1)), 0) as qty,
				# fb.description, fb.stock_uom, item.min_order_qty
				# from `tabBOM Explosion Item` fb, `tabBOM` bom, `tabItem` item
				# where bom.name = fb.parent and item.name = fb.item_code
				# and (item.is_sub_contracted_item = 0 or ifnull(item.default_bom, "")="")
				# """ + ("and item.is_stock_item = 1","")[non_stock_item] + """
				# and fb.docstatus<2 and bom.name=%(bom)s
				# group by fb.item_code, fb.stock_uom""", {"bom":bom}, as_dict=1):
					# bom_wise_item_details.setdefault(d.item_code, d)
		# else:
			# # Get all raw materials considering SA items as raw materials,
			# # so no childs of SA items
			# bom_wise_item_details = get_subitems(bom_wise_item_details, bom,1, \
				# use_multi_level_bom,only_raw_materials, include_subcontracted,non_stock_item)

		# for item, item_details in bom_wise_item_details.items():
			# for so_qty in so_wise_qty:
				# item_list.append([item, flt(item_details.qty) * so_qty[1], item_details.description,
					# item_details.stock_uom, item_details.min_order_qty, so_qty[0]])

	# item_dict = {}
	# for i in item_list:
		# item_dict.setdefault(i[0], []).append([flt(i[1]), i[2], i[3], i[4], i[5]])
	
	# return item_list

# def get_subitems(bom_wise_item_details, bom, parent_qty, include_sublevel, only_raw, supply_subs,non_stock_item=0):
	# items = frappe.db.sql("""
		# SELECT
			# bom_item.item_code,
			# default_material_request_type,
			# ifnull(%(parent_qty)s * sum(bom_item.qty/ifnull(bom.quantity, 1)), 0) as qty,
			# item.is_sub_contracted_item as is_sub_contracted,
			# item.default_bom as default_bom,
			# bom_item.description as description,
			# bom_item.stock_uom as stock_uom,
			# item.min_order_qty as min_order_qty
		# FROM
			# `tabBOM Item` bom_item,
			# `tabBOM` bom,
			# tabItem item
		# where
			# bom.name = bom_item.parent
			# and bom.name = %(bom)s
			# and bom_item.docstatus < 2
			# and bom_item.item_code = item.name
		# """ + ("and item.is_stock_item = 1", "")[non_stock_item] + """
		# group by bom_item.item_code""", {"bom": bom, "parent_qty": parent_qty}, as_dict=1)

	# for d in items:
		# if ((d.default_material_request_type == "Purchase"
			# and not (d.is_sub_contracted and only_raw and include_sublevel))
			# or (d.default_material_request_type == "Manufacture" and not only_raw)):

			# if d.item_code in bom_wise_item_details:
				# bom_wise_item_details[d.item_code].qty = bom_wise_item_details[d.item_code].qty + d.qty
			# else:
				# bom_wise_item_details[d.item_code] = d

		# if include_sublevel:
			# if ((d.default_material_request_type == "Purchase" and d.is_sub_contracted and supply_subs)
				# or (d.default_material_request_type == "Manufacture")):

				# my_qty = 0
				# projected_qty = self.get_item_projected_qty(d.item_code)

				# if self.create_material_requests_for_all_required_qty:
					# my_qty = d.qty
				# elif (bom_wise_item_details[d.item_code].qty - d.qty) < projected_qty:
					# my_qty = bom_wise_item_details[d.item_code].qty - projected_qty
				# else:
					# my_qty = d.qty

				# if my_qty > 0:
					# self.get_subitems(bom_wise_item_details,
						# d.default_bom, my_qty, include_sublevel, only_raw, supply_subs)

	# return bom_wise_item_details
	
	
# def merge(dicts):
	# from collections import defaultdict
	# dd = defaultdict(int)
	# for d in dicts:
		# dd[d['item_name'], d['description'], d['brand']] += d['qty']
		# dd[d['item_name'], d['description'], d['brand']] += d['delivered_qty']

	# frappe.errprint(dd)
	# list2 = [{'item_name': k[0], 'description': k[1],'brand': k[2], 'qty': v} for k, v in dd.iteritems()]
	# return list2


def get_columns(filters):
	doctype = filters.get("format")
	if doctype == "Sales Order":
		columns = [_("Item Code") + ":Link/Item:150",
		_("Item Name") + "::150", _("Description") + "::340",_("UOM") + "::50",
		_("Qty") + "::80",_("Total Qty") + "::80"
		]
	elif doctype == "Quotation":
		columns = [_("Item Code") + ":Link/Item:150",
		_("Item Name") + "::150", _("Description") + "::340",_("UOM") + "::50",
		_("Qty") + "::80",_("Total Qty") + "::80"
		]
	elif doctype == "Delivery Note":
		columns = [_("Item Code") + ":Link/Item:150",
		_("Item Name") + "::150", _("Description") + "::340",_("UOM") + "::50",
		_("Qty") + "::80",_("Total Qty") + "::80"
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