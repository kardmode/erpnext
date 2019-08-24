# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import throw, _
from frappe.utils import flt, cint, getdate, now

def execute(filters=None):
	if not filters: filters = {}
	columns, data = [], []
	
	if not filters.get("company"):
		return columns, data

	columns = get_columns()
	if filters.get("item_code") and filters.get("location"):
		from erpnext.stock.doctype.mrp_store_location.mrp_store_location import get_items_in_bill
		items = get_items_in_bill(filters.get("location"))
		
		for item in items:
			if filters.get("item_code") == item["item_code"]:
				# item = items[key]
				
				row = [item["item_code"],item["location"],item["uom"],item["qty"]]
				data.append(row)
			
			
	elif filters.get("item_code") and not filters.get("location"):
		from erpnext.stock.doctype.mrp_store_location.mrp_store_location import get_bills_and_stock
		items = get_bills_and_stock(filters.get("item_code"),company=filters.get("company"))

		for item in items:
			# item = items[key]
			
			row = [item["item_code"],item["location"],item["uom"],item["qty"]]
			data.append(row)
			
			
	elif not filters.get("item_code") and filters.get("location"):
	
		from erpnext.stock.doctype.mrp_store_location.mrp_store_location import get_items_in_bill
		items = get_items_in_bill(filters.get("location"))
		
		for item in items:
			# item = items[key]
			
			row = [item["item_code"],item["location"],item["uom"],item["qty"]]
			data.append(row)
	
	
	elif not filters.get("item_code") and not filters.get("location"):
	
		# items = frappe.db.sql("""
					# select t1.item_code, t2.location, t2.qty,t2.uom
					# from `tabMRP Store Item` t1,`tabMRP Store Item Detail` t2,`tabMRP Store Location` t3
					# where
					# t2.parent = t1.name
					# and t2.qty <> 0
					# and t3.name = t2.location 
					# and t3.company = %s
					# ORDER BY t2.qty DESC
					# """,(filters.get("company")), as_dict=True)		
				
		# for item in items:
			
			# row = [item["item_code"],item["location"],item["uom"],item["qty"]]
			# data.append(row)
	
		return columns, data
	
	
	return columns, data

def get_columns():
	"""return columns"""

	columns = [
		_("Item")+":Link/Item:250",
		# _("Item Name")+"::150",
		# _("Item Group")+"::120",
		# _("Brand")+"::90",
		# _("Description")+"::140",
		_("Store Location")+":Link/MRP Store Location:200",
		_("UOM")+":Link/UOM:80",
		_("Qty")+":Float:150"
	]

	return columns
	