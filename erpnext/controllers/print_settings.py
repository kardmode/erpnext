# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint

def print_settings_for_item_table(doc):

	doc.print_templates = {
		"qty": "templates/print_formats/includes/item_table_qty.html"
	}
	

	
	doc.hide_in_print_layout = ["uom", "stock_uom"]

	doc.flags.compact_item_print = cint(frappe.db.get_value("Print Settings", None, "compact_item_print"))

	# if doc.doctype in ["Purchase Receipt Item"]:
		# doc.flags.compact_item_print=0
	
	if doc.flags.compact_item_print:
	
		# if doc.doctype in ["Quotation Item"]:
			# doc.print_templates["description"] = "templates/print_formats/includes/item_table_description.html"
			# doc.flags.compact_item_fields = ["description", "qty", "rate", "amount"]

		# elif doc.doctype in ["Purchase Order Item"]:
			# doc.print_templates["item_name"] = "templates/print_formats/includes/custom_item_table_description.html"
			# doc.flags.compact_item_fields = ["item_name", "qty", "rate", "amount"]

		# else:
			# doc.print_templates["description"] = "templates/print_formats/includes/buying_item_table_description.html"
			# doc.flags.compact_item_fields = ["description", "qty", "rate", "amount"]

		doc.print_templates["item_name"] = "templates/print_formats/includes/custom_item_table_description.html"
		doc.flags.compact_item_fields = ["item_name", "qty", "rate", "amount"]
		
		
		doc.flags.format_columns = format_columns
	doc.flags.format_columns_custom = format_columns_custom

def format_columns(display_columns, compact_fields):
	compact_fields = compact_fields + ["image", "item_code", "item_name"]
	final_columns = []
	for column in display_columns:
		if column not in compact_fields:
			final_columns.append(column)
	return final_columns
	
def format_columns_custom(display_columns, compact_fields):
	compact_fields = compact_fields + ["image", "item_code", "item_name"]
	final_columns = []
	for column in display_columns:
		if column.fieldname not in compact_fields:
			final_columns.append(column)
	return final_columns
