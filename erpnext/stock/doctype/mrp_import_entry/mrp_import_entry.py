
# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, math
from frappe.utils import cint,flt
from frappe import throw, _
from frappe.model.document import Document

class MRPImportEntry(Document):
	def validate(self):
		self.validate_duplicate_doc()
		self.validate_duplicate_items()

		self.validate_items()
		
	def validate_duplicate_doc(self):
		if self.transaction_type == "Purchase Receipt":
			doc_details = frappe.db.sql("""
						select name
						from `tabMRP Import Entry`where
						name <> %s 
						and transaction_type = %s 
						and reference_name = %s
						""", (self.name,self.transaction_type,self.reference_name), as_dict=True)
						
			if doc_details:
				frappe.throw(_("Import Entry for purchase receipt {0} already exists.").format(self.reference_name))

		
		
		elif self.transaction_type == "Delivery Note":
			doc_details = frappe.db.sql("""
						select name 
						from `tabMRP Import Entry`
						where
						name <> %s and transaction_type = %s and reference_name = %s
						""", (self.name,self.transaction_type,self.reference_name), as_dict=True)
						
			if doc_details:
				frappe.throw(_("Import Entry for delivery note {0} already exists.").format(self.reference_name))
		elif self.transaction_type == "Custom Production Order":
			doc_details = frappe.db.sql("""
						select name 
						from `tabMRP Import Entry`
						where
						name <> %s and transaction_type = %s and reference_name = %s
						""", (self.name,self.transaction_type,self.reference_name), as_dict=True)
						
			if doc_details:
				frappe.throw(_("Import Entry for production order {0} already exists.").format(self.reference_name))

	def validate_duplicate_items(self):		
		items = {}
		for d in self.get("items"):
			key = d.item_code
			if key in items:
				if d.import_bill in items[key]:
					frappe.throw(_("Duplicate Item Entries with the same Import Bill Are Not Allowed. Row {0} Item {1}").format(d.idx,d.item_code))
				else:
					items[key].append(d.import_bill)
			else:
				items[key] = [d.import_bill]


				
	def validate_items(self):
		from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill	import get_total_qty_for_item

		for d in self.get("items"):
		
			d.stock_qty = math.fabs(flt(d.stock_qty))
			
			if d.stock_qty == 0:
				frappe.throw(_("{0} ({1}) cannot have 0 quantity.").format(d.idx,d.item_code))

			if d.item_name == None or d.item_name == "":
				from erpnext.manufacturing.doctype.custom_production_order.custom_production_order import get_item_det
					
				item_dict = get_item_det(d.item_code)
				d.item_name = item_dict.item_name
				
			if d.import_bill:
				d.available_qty = get_total_qty_for_item(d.import_bill,d.item_code,self.posting_date,self.posting_time)
			
			if self.transaction_type in ["Purchase Receipt","Addition"]:
				d.balance_qty = flt(d.available_qty) + flt(d.stock_qty)
			else:
				d.balance_qty = flt(d.available_qty) - flt(d.stock_qty)
			
			

	def get_items_from(self,document,purpose,data=None):
		if purpose not in ["Purchase Receipt","Delivery Note","Custom Production Order"]:
			return None
		
		if not document:
			return None
			
		
		if purpose == "Purchase Receipt" and data == None:
			return None
			
		self.items = []
		self.transaction_type = purpose
		self.reference_name = document
		
		
		doc_details = []
		if purpose == "Purchase Receipt":
			
			doc_details = frappe.db.sql("""
					select t2.item_code,t2.stock_qty,t2.stock_uom, t2.item_name
					from `tabPurchase Receipt` t1,`tabPurchase Receipt Item` t2
					where
					t1.name = %s and t2.parent =  t1.name
					""", (document), as_dict=True)
		elif purpose == "Delivery Note":
			doc_details = frappe.db.sql("""
					select t2.item_code,t2.stock_qty,t2.stock_uom, t2.item_name
					from `tabDelivery Note` t1,`tabDelivery Note Item` t2
					where
					t1.name = %s and t2.parent =  t1.name
					""", (document), as_dict=True)
		# elif purpose == "Custom Production Order":
			# doc_details = frappe.db.sql("""
					# select t2.item_code,t2.stock_qty,t2.stock_uom, t2.item_name
					# from `tabCustom Production Order` t1,`tabCustom Production Order Item` t2
					# where
					# t1.name = %s and t2.parent =  t1.name
					# """, (document), as_dict=True)			
		
					
		
		from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill	import get_best_bill,get_total_qty_for_item
		for d in doc_details:
			newd = self.append('items')
			newd.item_code = d.item_code
			newd.item_name = d.item_name
			newd.stock_qty = d.stock_qty
			newd.stock_uom = d.stock_uom
			
			if purpose == "Delivery Note":
				import_bill,highest_qty,enough_stock = get_best_bill(d.item_code,company=self.company)
				if import_bill:
					newd.import_bill = import_bill
					newd.available_qty = highest_qty
					newd.balance_qty = newd.available_qty - newd.stock_qty
					
			else:
				newd.import_bill = data
				newd.available_qty = get_total_qty_for_item(d.import_bill,d.item_code,self.posting_date,self.posting_time)
				newd.balance_qty = flt(d.available_qty) + flt(d.stock_qty)
				
				
	def set_import_bill_for(self,purpose,data=None):
		if purpose not in ["Purchase Receipt","Delivery Note"]:
			return None
		
		if purpose == "Purchase Receipt" and data == None:
			return None
			
		from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill	import get_best_bill,get_total_qty_for_item

		for d in self.get("items"):
			if purpose == "Purchase Receipt":
				d.import_bill = data
				d.available_qty = get_total_qty_for_item(d.import_bill,d.item_code,self.posting_date,self.posting_time)
				d.balance_qty = flt(d.available_qty) + flt(d.stock_qty)
			else:
				import_bill,highest_qty,enough_stock = get_best_bill(d.item_code,company=self.company)
				if import_bill:
					newd.import_bill = import_bill
					newd.available_qty = highest_qty
					newd.balance_qty = newd.available_qty - newd.stock_qty
				
		