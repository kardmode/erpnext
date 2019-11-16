# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, now
from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_bills_and_stock,get_items_in_bill

def execute(filters=None):
	if not filters: filters = {}
	columns, data = [], []
	
	columns = get_columns()
	if filters.get("item_group") and not filters.get("item_code") and not filters.get("import_bill"):
		conditions = ""
		ig_details = frappe.db.get_value("Item Group", filters.get("item_group"), 
			["lft", "rgt"], as_dict=1)
			
		if ig_details:
			conditions += """ 
				exists (select name from `tabItem Group` ig 
				where ig.lft >= %s and ig.rgt <= %s and item.item_group = ig.name)
			""" % (ig_details.lft, ig_details.rgt)
		
		
		items_in_group = frappe.db.sql("""select item.item_code, item.item_group from `tabItem` item where %s""" % (conditions), as_dict=1)
		
		for d in items_in_group:
			items = get_bills_and_stock(d.item_code,company = filters.get("company"))
			item_group = d.item_group
			for key in items:
				item = items[key]					
				row = [item["item_code"],item["import_bill"],item["stock_uom"],item["stock_qty"],item_group]
				data.append(row)
	
	elif filters.get("item_code") and filters.get("import_bill"):

		items = get_items_in_bill(filters.get("import_bill"))
		
		for key in items:
			if filters.get("item_code") == key:
				item = items[key]
				
				item_group = frappe.db.get_value('Item', {'item_code': item["item_code"]},'item_group')
								
				row = [item["item_code"],item["import_bill"],item["stock_uom"],item["stock_qty"],item_group]
				data.append(row)
			
			
	elif filters.get("item_code") and not filters.get("import_bill"):

		items = get_bills_and_stock(filters.get("item_code"),company = filters.get("company"))

		for key in items:
			item = items[key]
			
			item_group = frappe.db.get_value('Item', {'item_code': item["item_code"]},'item_group')
				
			row = [item["item_code"],item["import_bill"],item["stock_uom"],item["stock_qty"],item_group]
			data.append(row)
			
			
	elif not filters.get("item_code") and filters.get("import_bill"):
		items = get_items_in_bill(filters.get("import_bill"))
		
		for key in items:
			item = items[key]
			
			item_group = frappe.db.get_value('Item', {'item_code': item["item_code"]},'item_group')
				
			row = [item["item_code"],item["import_bill"],item["stock_uom"],item["stock_qty"],item_group]
			data.append(row)
	
	
	elif not filters.get("item_code") and not filters.get("import_bill"):
		return columns, data
	
	
	return columns, data

def get_columns():
	"""return columns"""

	columns = [
		_("Item")+":Link/Item:250",
		# _("Item Name")+"::150",
		# _("Brand")+"::90",
		# _("Description")+"::140",
		_("Import Bill")+":Link/MRP Import Bill:200",
		_("Stock UOM")+":Link/UOM:80",
		_("Balance Qty")+":Float:150",
		_("Item Group")+":Link/Item Group:120"
	]

	return columns
	