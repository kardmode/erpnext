# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cstr, flt, cint, nowdate, add_days, comma_and, getdate

def execute(filters=None):
    
	if not filters: 
		filters = {}

	data = []

	columns = get_columns()

	items = get_bom_stock(filters)
	qty = filters.get("qty") or 1

	for item in items:
		
		required_qty = qty * item.required_qty/item.bom_quantity
		stock_qty =  qty * item.stock_qty/item.bom_quantity
		can_build = 0
		actual_qty = item.actual_qty or 0
		
		try:
			can_build = actual_qty/stock_qty
		except:
			can_build = 0
		

		
		row = [item.item_code,item.description,required_qty,item.required_uom,stock_qty,item.stock_uom,item.actual_qty,can_build]
		data.append(row)

	return columns, data

def get_columns():
    """return columns"""
    columns = [
        _("Item") + ":Link/Item:250",
        _("Description") + "::100",
        _("Required Qty") + ":Float:100",
        _("Required UOM") + ":Link/UOM:100",
        _("Stock Qty") + ":Float:100",
		_("Stock UOM") + ":Link/UOM:100",
        _("Available Stock Qty") + ":Float:100",
        _("Can Build") + ":Float:150",
    ]

    return columns
	
	

def get_bom_stock(filters):
	conditions = ""
	bom = filters.get("bom")
	if not bom: 
		return []

	if filters.get("warehouse"):
		warehouse_details = frappe.db.get_value("Warehouse", filters.get("warehouse"), ["lft", "rgt"], as_dict=1)
		if warehouse_details:
			conditions += " and exists (select name from `tabWarehouse` wh \
				where wh.lft >= %s and wh.rgt <= %s and ledger.warehouse = wh.name)" % (warehouse_details.lft,
				warehouse_details.rgt)
		else:
			conditions += " and ledger.warehouse = '%s'" % frappe.db.escape(filters.get("warehouse"))

	else:
		conditions += ""
		

	return frappe.db.sql("""
			SELECT
				bom.quantity AS bom_quantity,
				bom_item.item_code AS item_code,
				bom_item.description AS description,
				bom_item.qty AS required_qty,
				bom_item.stock_qty AS stock_qty,
				bom_item.required_uom AS required_uom,
				bom_item.stock_uom AS stock_uom,
				sum(ledger.actual_qty) AS actual_qty
			FROM
				`tabBOM` AS bom,
				`tabBOM Item` AS bom_item
				LEFT JOIN `tabBin` AS ledger
				ON bom_item.item_code = ledger.item_code
				%s
			WHERE
				bom_item.parent = '%s' and bom_item.parenttype='BOM'
				and bom.name = '%s'

			GROUP BY bom_item.item_code""" % (conditions, bom,bom),as_dict=1)
