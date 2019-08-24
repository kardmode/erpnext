# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, now

def execute(filters=None):
	if not filters: filters = {}
	columns, data = [], []
	
	columns = get_columns()
	if filters.get("item_code") and filters.get("import_bill"):
		from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_items_in_bill
		items = get_items_in_bill(filters.get("import_bill"))
		
		for key in items:
			if filters.get("item_code") == key:
				item = items[key]
				
				row = [item["item_code"],item["import_bill"],item["stock_uom"],item["stock_qty"]]
				data.append(row)
			
			
	elif filters.get("item_code") and not filters.get("import_bill"):
		from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_bills_and_stock
		items = get_bills_and_stock(filters.get("item_code"),company = filters.get("company"))

		for key in items:
			item = items[key]
			
			row = [item["item_code"],item["import_bill"],item["stock_uom"],item["stock_qty"]]
			data.append(row)
			
			
	elif not filters.get("item_code") and filters.get("import_bill"):
	
		from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_items_in_bill
		items = get_items_in_bill(filters.get("import_bill"))
		
		for key in items:
			item = items[key]
			
			row = [item["item_code"],item["import_bill"],item["stock_uom"],item["stock_qty"]]
			data.append(row)
	
	
	elif not filters.get("item_code") and not filters.get("import_bill"):
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
		_("Import Bill")+":Link/MRP Import Bill:200",
		_("Stock UOM")+":Link/UOM:80",
		_("Balance Qty")+":Float:150"
	]

	return columns
	