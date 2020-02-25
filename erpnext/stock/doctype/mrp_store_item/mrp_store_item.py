
# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint,flt
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc

class MRPStoreItem(Document):
	def autoname(self):
		self.name = self.item_code
		
	def validate(self):
	
		self.validate_duplicates()
		self._get_item_det()
		self.calculate_total_qty()
		self.validate_name()
		
	def validate_duplicates(self):
		from copy import deepcopy
		
		item_dict = {}
		new_list = deepcopy(self.get("items"))
		for item in new_list:
			uom = item.uom
			location = item.location
			if item_dict.has_key(location):
				if uom in item_dict[location]:
					frappe.throw(_("Store Location {0} already exists with same units {1}").format(location, uom))
				else:
					item_dict[location].append(uom)
			else:
				item_dict[location] = [uom]
			

	
	def validate_name(self):
		if not self.get("__islocal"):
			if not self.name == self.item_code:
				frappe.rename_doc('MRP Store Item', self.name , self.item_code, force=True)
				
	def calculate_total_qty(self):
		
		
		from erpnext.stock.get_item_details import get_conversion_factor
		
		total_qty = 0
		qty_txt = ""
		item_dict = {}
		import copy
		
		if self.get("items"):
			new_list = copy.deepcopy(self.get("items"))
			for item in new_list:
				uom = item.uom
				qty = item.qty
				
				if self.stock_uom == uom:
					if item_dict.has_key(uom):
						item_dict[uom].qty += qty
					else:
						item_dict[uom] = item
				else:
					conversion_factor = get_conversion_factor(self.item_code, uom).get("conversion_factor") or 1
					if conversion_factor == 1:
						if item_dict.has_key(uom):
							item_dict[uom].qty += qty
						else:
							item_dict[uom] = item
					else:
						conversion_factor = flt(1/conversion_factor)
						new_qty = flt(qty) / flt(conversion_factor)
						if item_dict.has_key(self.stock_uom):
							item_dict[self.stock_uom].qty += new_qty
						else:
							item_dict[self.stock_uom] = item
							item_dict[self.stock_uom].qty = new_qty
				
		
			for key in item_dict:
				d = item_dict[key]
				display_uom = str(key)
				display_qty = str(d.qty)
				qty_txt += str(display_qty) + ' ' + str(display_uom) + ' | '
				total_qty = total_qty + flt(d.qty)
		else:
			qty_txt = "0"

		self.total_qty = qty_txt
		
	def _get_item_det(self):
		if self.item_code:
			from erpnext.stock.get_item_details import get_default_uom
			
			stock_details = frappe.db.sql("select t1.warehouse, t1.actual_qty from `tabBin` t1 where t1.item_code = %s AND t1.actual_qty <> 0 ORDER BY actual_qty DESC",(self.item_code),as_dict=1)

			actual_qty_txt = ""
			if stock_details:
				for d in stock_details:
					actual_qty_txt += str(d.warehouse) + ': ' + str(d.actual_qty) + ' | '
			else:
				actual_qty_txt = "0"
			from erpnext.stock.utils import get_actual_qty
			self.actual_qty = actual_qty_txt
			self.stock_uom = get_default_uom(self.item_code)
			
			
		