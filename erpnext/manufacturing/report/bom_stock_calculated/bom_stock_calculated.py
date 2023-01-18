# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.data import comma_and

def execute(filters=None):
	data = []

	if not filters: filters = {}

	columns = get_columns()
	
	bom = filters.get("bom")
	if not bom: 
		return columns, data

	items = get_bom_stock(filters)
	qty_to_produce = filters.get("qty_to_produce", 1)

	manufacture_details = get_manufacturer_records()
	
	for item in items:
		bom_quantity = item.bom_quantity
		required_qty = qty_to_produce * item.required_qty/bom_quantity
		stock_qty =  qty_to_produce * item.stock_qty/bom_quantity
		last_pur_price = frappe.db.get_value("Item", item.item_code, "last_purchase_rate")

		can_build = 0
		actual_qty = item.actual_qty or 0
		
		try:
			can_build = actual_qty/stock_qty
		except:
			can_build = 0
			
		can_build = max(0,can_build)
		diff_qty = can_build - stock_qty
		
		data.append([item.item_code, item.description,
			# comma_and(manufacture_details.get(item.item_code, {}).get('manufacturer', [])),
			# comma_and(manufacture_details.get(item.item_code, {}).get('manufacturer_part', [])),
			actual_qty, 
			can_build,
			required_qty, 
			item.required_uom, 
			diff_qty, 
			last_pur_price])
		
	return columns, data

def get_report_data(last_pur_price, reqd_qty, row, manufacture_details):
	to_build = row.to_build if row.to_build > 0 else 0
	diff_qty = to_build - reqd_qty
	return [row.item_code, row.description,
		comma_and(manufacture_details.get(row.item_code, {}).get('manufacturer', [])),
		comma_and(manufacture_details.get(row.item_code, {}).get('manufacturer_part', [])),
		row.actual_qty, 
		str(to_build),
		reqd_qty, 
		diff_qty, 
		last_pur_price]

def get_columns():
	"""return columns"""
	columns = [
		_("Item") + ":Link/Item:100",
		_("Description") + "::150",
		# _("Manufacturer") + "::250",
		# _("Manufacturer Part Number") + "::250",
		_("In Stock Qty") + ":Float:150",
		_("Enough to Build") + ":Float:150",
		_("Required Qty")+ ":Float:150",
		_("Required UOM") + ":Link/UOM:150",
		_("Diff Stock Qty")+ ":Float:150",
		_("Last Purchase Price")+ ":Float:150",
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
				bom_item.item_code,
				bom_item.description,
				bom_item.{qty_field} AS required_qty,
				bom_item.{stock_qty_field} AS stock_qty,
				bom_item.{uom_field} AS required_uom,
				bom_item.{stock_uom_field} AS stock_uom,
				ifnull(sum(ledger.actual_qty), 0) as actual_qty,
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
			
def get_manufacturer_records():
	details = frappe.get_list('Item Manufacturer', fields = ["manufacturer", "manufacturer_part_no", "parent"])
	manufacture_details = frappe._dict()
	for detail in details:
		dic = manufacture_details.setdefault(detail.get('parent'), {})
		dic.setdefault('manufacturer', []).append(detail.get('manufacturer'))
		dic.setdefault('manufacturer_part', []).append(detail.get('manufacturer_part_no'))

	return manufacture_details