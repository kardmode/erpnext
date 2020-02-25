# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint

def print_settings_for_item_table(doc):

	doc.print_templates = {
		"total_weight": "templates/print_formats/includes/item_table_weight.html",
		"qty": "templates/print_formats/includes/item_table_qty.html",
		"tax_rate":"templates/print_formats/includes/item_table_tax_rate.html",
		"tax_amount":"templates/print_formats/includes/item_table_tax_rate.html"
	}
	
	doc.hide_in_print_layout = ["uom", "stock_uom","weight_uom"]


	doc.flags.compact_item_print = cint(frappe.db.get_single_value("Print Settings", "compact_item_print"))

	if doc.flags.compact_item_print:

		doc.print_templates["item_name"] = "templates/print_formats/includes/custom_item_table_description.html"
		doc.flags.compact_item_fields = ["item_name", "qty", "rate", "amount","tax_rate","tax_amount","total_amount","total_weight","net_weight","remarks"]
		
		
		doc.flags.format_columns = format_columns
	
	if doc.doctype == "Supplier Quotation Item":
		doc.flags.compact_item_fields = doc.flags.compact_item_fields + ["mrp_request_rate"]
	
	doc.flags.format_columns_custom = format_columns_custom

def format_columns(display_columns, compact_fields):
	compact_fields = compact_fields + ["image", "item_code"]
	final_columns = []
	for column in display_columns:
		if column not in compact_fields:
			final_columns.append(column)
	return final_columns

# gets the more info from print format builder	
def format_columns_custom(display_columns, compact_fields):
	compact_fields = compact_fields + ["image", "item_code"]
	final_columns = []
	for column in display_columns:
		if column.fieldname not in compact_fields:
			final_columns.append(column)
	return final_columns
