# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns()
	stock = get_total_stock(filters)
	data = []

	for i,s in enumerate(stock):
		removeIt = False
		if filters.get("hide_positive_qty") == 1:
			if s.actual_qty > 0:
				removeIt = True
		
		
		if filters.get("hide_negative_qty") == 1:
			if s.actual_qty < 0:
				removeIt = True
				
		if filters.get("hide_zero_qty") == 1:
			if s.actual_qty == 0:
				removeIt = True
				
		if not removeIt:
			data.append(s)
	
	
	return columns, data

def get_columns():
	columns = [
		_("Warehouse") + ":Link/Warehouse:150",
		_("Item Code") + ":Link/Item:150",
		_("Description") + "::300",
		_("Actual Qty") + ":Float:100",
	]

	return columns

def get_total_stock(filters):
	conditions = ""
	columns = ""
	
	if filters.get("hide_disabled") == 1:
		conditions += " AND warehouse.disabled = 0"
        conditions += " AND item.disabled = 0"

	if filters.get("company"):
		conditions += " AND warehouse.company = %s" % frappe.db.escape(filters.get("company"), percent=False)

	conditions += " GROUP BY ledger.warehouse, item.item_code"
	columns += "ledger.warehouse"
		
	return frappe.db.sql("""
			SELECT
				%s,
				item.item_code,
				item.description,
				sum(ledger.actual_qty) as actual_qty
			FROM
				`tabBin` AS ledger
			INNER JOIN `tabItem` AS item
				ON ledger.item_code = item.item_code
			INNER JOIN `tabWarehouse` warehouse
				ON warehouse.name = ledger.warehouse
			WHERE
				ledger.actual_qty != 0 %s""" % (columns, conditions),as_dict=True)
