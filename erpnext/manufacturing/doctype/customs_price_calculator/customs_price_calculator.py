# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, cstr, flt

from frappe.model.document import Document

class CustomsPriceCalculator(Document):
	def get_child_exploded_items(self, bom_no, stock_qty):
	
		self.operating_cost,scrap_material_cost = frappe.db.get_value('BOM',bom_no, ['operating_cost','scrap_material_cost'])

		""" Add all items from Flat BOM of child BOM"""
		# Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
		child_fb_items = frappe.db.sql("""select * from `tabBOM Explosion Item` where parent = %s""", bom_no, as_dict = 1)

		self.set('exploded_items', [])

		for d in sorted(child_fb_items):
			ch = self.append('exploded_items', {})
			ch.item_code = d['item_code']
			ch.item_name = d['item_name']
			ch.qty_consumed_per_unit = d['qty_consumed_per_unit']
			ch.stock_qty = d['stock_qty']
			ch.rate = flt(d['rate'])
			ch.amount = flt(d['amount'])
			ch.source_warehouse = d['source_warehouse']
			ch.description = d['description']
			ch.stock_uom =  d['stock_uom']
			

