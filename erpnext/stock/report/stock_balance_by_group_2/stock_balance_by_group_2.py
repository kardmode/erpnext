# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate

def execute(filters=None):
	if not filters: filters = {}

	validate_filters(filters)

	columns = get_columns()
	item_map = get_item_details(filters)
	iwb_map = get_item_warehouse_map(filters)

	data = []
	
	if filters.get("report_style") == "By Item":

		for (company, item, warehouse) in sorted(iwb_map):
			if not company == filters.get("company"):
				continue
			qty_dict = iwb_map[(company, item, warehouse)]
			
			if qty_dict.bal_qty != 0:
				data.append([item, 
				# item_map[item]["item_name"],
					item_map[item]["item_group"]
					, warehouse
					,item_map[item]["stock_uom"]
					,qty_dict.bal_qty
					# ,qty_dict.bal_val
					# ,qty_dict.val_rate
				])
	else:
		
		columns = [
		_("Item Group")+":Link/Item Group:300",
		_("Balance Qty")+":Float:200",
		]
		
		item_dict = {}
		for (company, item, warehouse) in sorted(iwb_map):
			if not company == filters.get("company"):
				continue
			qty_dict = iwb_map[(company, item, warehouse)]
			if item_dict.has_key(item_map[item]["item_group"]):
				item_dict[item_map[item]["item_group"]]["bal_qty"] += flt(qty_dict.bal_qty)
				item_dict[item_map[item]["item_group"]]["bal_val"] += flt(qty_dict.bal_val)
			else:
				item_dict[item_map[item]["item_group"]] = qty_dict
				
		for key,item in sorted(item_dict.items()):
			
			report_data = [key,item.bal_qty]
			if item.bal_qty != 0:
				data.append(report_data)
			


	return columns, data

def get_columns():
	"""return columns"""

	columns = [
		_("Item")+":Link/Item:300",
		# _("Item Name")+"::150",
		_("Item Group")+":Link/Item Group:300",
		_("Warehouse")+":Link/Warehouse:200",
		_("Stock UOM")+":Link/UOM:100",
		_("Balance Qty")+":Float:200",
		# _("Balance Value")+":Float:100",
		# _("Valuation Rate")+":Float:90",
	]

	return columns

def get_conditions(filters):
	conditions = ""

	from frappe.utils import flt, today
	conditions += " and posting_date <= '%s'" % frappe.db.escape(today())

	if filters.get("item_group"):		
		ig_details = frappe.db.get_value("Item Group", filters.get("item_group"), 
			["lft", "rgt"], as_dict=1)
			
		if ig_details:
			conditions += """ 
				and exists (select name from `tabItem Group` ig 
				where ig.lft >= %s and ig.rgt <= %s and item.item_group = ig.name)
			""" % (ig_details.lft, ig_details.rgt)
		
	if filters.get("item_code"):
		conditions += " and sle.item_code = '%s'" % frappe.db.escape(filters.get("item_code"), percent=False)

	if filters.get("warehouse"):
		warehouse_details = frappe.db.get_value("Warehouse", filters.get("warehouse"), ["lft", "rgt"], as_dict=1)
		if warehouse_details:
			conditions += " and exists (select name from `tabWarehouse` wh \
				where wh.lft >= %s and wh.rgt <= %s and wh.disabled = 0 and sle.warehouse = wh.name)"%(warehouse_details.lft,
				warehouse_details.rgt)
		


	return conditions

def get_stock_ledger_entries(filters):
	conditions = get_conditions(filters)
	
	join_table_query = ""
	if filters.get("item_group"):
		join_table_query = "inner join `tabItem` item on item.name = sle.item_code"
	
	return frappe.db.sql("""
		select
			sle.item_code, warehouse, sle.posting_date, sle.actual_qty, sle.valuation_rate,
			sle.company, sle.voucher_type, sle.qty_after_transaction, sle.stock_value_difference
		from
			`tabStock Ledger Entry` sle force index (posting_sort_index) %s
		where sle.docstatus < 2 %s 
		order by sle.posting_date, sle.posting_time, sle.name""" %
		(join_table_query, conditions), as_dict=1)

def get_item_warehouse_map(filters):
	iwb_map = {}
	from frappe.utils import today

	from_date = getdate(today())
	to_date = getdate(today())

	sle = get_stock_ledger_entries(filters)

	for d in sle:
		key = (d.company, d.item_code, d.warehouse)
		if key not in iwb_map:
			iwb_map[key] = frappe._dict({
				"opening_qty": 0.0, "opening_val": 0.0,
				"in_qty": 0.0, "in_val": 0.0,
				"out_qty": 0.0, "out_val": 0.0,
				"bal_qty": 0.0, "bal_val": 0.0,
				"val_rate": 0.0, "uom": None
			})

		qty_dict = iwb_map[(d.company, d.item_code, d.warehouse)]

		if d.voucher_type == "Stock Reconciliation":
			qty_diff = flt(d.qty_after_transaction) - qty_dict.bal_qty
		else:
			qty_diff = flt(d.actual_qty)

		value_diff = flt(d.stock_value_difference)

		if d.posting_date < from_date:
			qty_dict.opening_qty += qty_diff
			qty_dict.opening_val += value_diff

		elif d.posting_date >= from_date and d.posting_date <= to_date:
			if qty_diff > 0:
				qty_dict.in_qty += qty_diff
				qty_dict.in_val += value_diff
			else:
				qty_dict.out_qty += abs(qty_diff)
				qty_dict.out_val += abs(value_diff)

		qty_dict.val_rate = d.valuation_rate
		qty_dict.bal_qty += qty_diff
		qty_dict.bal_val += value_diff

	return iwb_map

def get_item_details(filters):
	condition = ''
	value = ()
	if filters.get("item_code"):
		condition = "where item_code=%s"
		value = (filters["item_code"],)

	items = frappe.db.sql("""select name, item_name, stock_uom, item_group
		from tabItem {condition}""".format(condition=condition), value, as_dict=1)

	return dict((d.name, d) for d in items)

def validate_filters(filters):
	if not (filters.get("item_code") or filters.get("warehouse")):
		sle_count = flt(frappe.db.sql("""select count(name) from `tabStock Ledger Entry`""")[0][0])
		if sle_count > 500000:
			frappe.throw(_("Please set filter based on Item or Warehouse"))
