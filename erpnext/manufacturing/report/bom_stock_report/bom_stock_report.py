# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	data = []

	if not filters: filters = {}

	columns = get_columns()
	
	bom = filters.get("bom")
	if not bom: 
		return columns, data

	items = get_bom_stock(filters)
	qty_to_produce = filters.get("qty_to_produce", 1)
	
	for item in items:
		bom_quantity = item.bom_quantity
		required_qty = qty_to_produce * item.required_qty/bom_quantity
		stock_qty =  qty_to_produce * item.stock_qty/bom_quantity
		can_build = 0
		actual_qty = item.actual_qty or 0
		last_pur_price = frappe.db.get_value("Item", item.item_code, "last_purchase_rate")

		try:
			can_build = actual_qty/stock_qty
		except:
			can_build = 0
			
		can_build = max(0,can_build)
		
		data.append([item.item_code,
			item.description,
			required_qty,
			item.required_uom,
			stock_qty,
			item.stock_uom,
			item.actual_qty,
			can_build])


	return columns, data

def get_columns():
    """return columns"""
    columns = [
		_("Item") + ":Link/Item:150",
		_("Description") + "::100",
        _("Required Qty") + ":Float:150",
        _("Required UOM") + ":Link/UOM:150",
        _("Required Stock Qty") + ":Float:150",
		_("Required Stock UOM") + ":Link/UOM:150",
		_("Available Qty in Stock UOM") + ":Float:150",
		_("Enough to Build in Stock UOM") + ":Float:150"
    ]

    return columns
	
	

def get_bom_stock(filters):
	conditions = ""
	bom = filters.get("bom")
	
	if not bom: 
		return []

	table = "`tabBOM Item`"
	qty_field = "qty"
	uom_field = "uom"
	stock_qty_field = "stock_qty"
	stock_uom_field = "stock_uom"
	
	qty_to_produce = filters.get("qty_to_produce", 1)
	if  int(qty_to_produce) <= 0:
		frappe.throw(_("Quantity to Produce can not be less than Zero"))

	if filters.get("show_exploded_view"):
		qty_field = "stock_qty"
		uom_field = "stock_uom"
		stock_qty_field = "stock_qty"
		stock_uom_field = "stock_uom"
		table = "`tabBOM Explosion Item`"

	if filters.get("warehouse"):
		warehouse_details = frappe.db.get_value("Warehouse", filters.get("warehouse"), ["lft", "rgt"], as_dict=1)
		if warehouse_details:
			conditions += " and exists (select name from `tabWarehouse` wh \
				where wh.lft >= %s and wh.rgt <= %s and ledger.warehouse = wh.name)" % (warehouse_details.lft,
				warehouse_details.rgt)
		else:
			conditions += " and ledger.warehouse = %s" % frappe.db.escape(filters.get("warehouse"))

	else:
		conditions += ""
		

	return frappe.db.sql("""
			SELECT
				bom_item.item_code AS item_code,
				bom_item.description AS description,
				bom_item.{qty_field} AS required_qty,
				bom_item.{stock_qty_field} AS stock_qty,
				bom_item.{uom_field} AS required_uom,
				bom_item.{stock_uom_field} AS stock_uom,
				sum(ledger.actual_qty) AS actual_qty,
				bom.quantity AS bom_quantity
			FROM
				`tabBOM` AS bom INNER JOIN {table} AS bom_item
					ON bom.name = bom_item.parent
				LEFT JOIN `tabBin` AS ledger
					ON bom_item.item_code = ledger.item_code
				{conditions}
			WHERE
				bom_item.parent = '{bom}' and bom_item.parenttype='BOM'
			GROUP BY bom_item.item_code""".format(
				qty_field=qty_field,
				stock_qty_field=stock_qty_field,
				uom_field=uom_field,
				stock_uom_field=stock_uom_field,
				table=table,
				conditions=conditions,
				bom=bom,
				qty_to_produce=qty_to_produce or 1)
			, as_dict=1)
