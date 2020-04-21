# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class MRPStoreLocation(Document):
	def autoname(self):
		if self.company:
			suffix = " - " + frappe.db.get_value("Company", self.company, "abbr")
			if not self.location_name.endswith(suffix):
				self.name = self.location_name + suffix
		else:
			self.name = self.location_name

	def on_update(self):
		if self.disabled:
			self.on_disable()
			
	def on_disable(self):
	
		bins = frappe.db.sql("select t1.item_code, t2.qty from `tabMRP Store Item Detail` t1. `tabMRP Store Item Detail` t2 where t2.location = %s and t1.name = t2.parent",
			self.name, as_dict=1)
		
		final_qty = 0
		for d in bins:
			final_qty = final_qty + flt(d['qty'])
		
		if final_qty != 0:
			frappe.throw(_("Store Location {0} can not be disabled as quantity exists for Item {1}").format(self.name, d['item_code']))
	


	def on_trash(self):
		# delete bin
		
		if self.check_if_sle_exists():
			frappe.throw(_("Store location cannot be deleted as MRP Store Item exists for this bill."))
			
		


	def check_if_sle_exists(self):
		return frappe.db.sql("""select name from `tabMRP Store Item Detail`
			where location = %s limit 1""", self.name)

	
	
def get_items_in_bill(store_location):

			
	stock_details = frappe.db.sql("""
					select t1.item_code,t2.location, t2.qty, t2.uom
					from `tabMRP Store Item` t1,`tabMRP Store Item Detail` t2
					where 
					t2.location = %s
					and t2.qty <> 0 
					and t1.name = t2.parent
					ORDER BY t2.qty DESC
					""", (store_location), as_dict=True)	
	
	# item_dict = {}
	# import copy
	# new_list = copy.deepcopy(stock_details)
	# for item in new_list:
		# item_code = item["item_code"]
		# if item_dict.has_key(item_code):
			# item_dict[item_code]["qty"] += flt(item["qty"])
		# else:
			# item_dict[item_code] = item
			

	return stock_details

@frappe.whitelist()
def get_total_qty_for_item(store_location,item_code):
	stock_details = frappe.db.sql("""
					select t1.name, t2.qty, t2.uom, t1.transaction_type
					from `tabMRP Store Item` t1,`tabMRP Store Item Detail` t2
					where t2.location = %s and t2.item_code = %s
					and t2.qty <> 0 and t1.name = t2.parent and t1.docstatus = 1
					ORDER BY t2.qty DESC
					""", (store_location,item_code), as_dict=True)	
					
	# and (t1.posting_date < %s or (t1.posting_date = %s and t1.posting_time < %s))

	total_qty = 0
	for d in stock_details:

		if d.transaction_type in ["Purchase Receipt","Addition"]:
			total_qty = total_qty + flt(d.qty)
			
		else:
			total_qty = total_qty - flt(d.qty)
			
	return total_qty
	
@frappe.whitelist()
def get_bills_and_stock(item_code=None,item_qty = 0, order_by_least = False,company = None):

	if not item_code or not company:
		return []


	stock_details = frappe.db.sql("""
					select t1.item_code, t2.location, t2.qty,t2.uom
					from `tabMRP Store Item` t1,`tabMRP Store Item Detail` t2,`tabMRP Store Location` t3
					where
					t1.item_code = %s
					and t2.parent = t1.name 
					and t3.name = t2.location 
					and t3.company = %s
					and t2.qty <> 0 ORDER BY t2.qty DESC
					""", (item_code,company), as_dict=True)		
	# best_warehouses = []
	
	# item_dict = {}
	# import copy
	# new_list = copy.deepcopy(stock_details)
	# for item in new_list:
		# store_location = item["store_location"]

		# if item_dict.has_key(store_location):
		
			# if item["transaction_type"] in ["Purchase Receipt","Addition"]:
				# item_dict[store_location]["qty"] += flt(item["qty"])
			# else:
				# item_dict[store_location]["qty"] -= flt(item["qty"])
		# else:
			# item_dict[store_location] = item
		

	return stock_details
	
@frappe.whitelist()
def get_best_bill(item_code=None,item_qty = 0, order_by_least = False,company = None):
	
	enough_stock = False
	
	best_warehouse = None

	if not item_code or not company:
		return best_warehouse,enough_stock
	
	item_dict = get_bills_and_stock(item_code,item_qty, order_by_least,company)
	
	highest_qty = 0
	best_warehouse = None
	
	for key in item_dict:
		warehouse_info =item_dict[key]
		if warehouse_info.qty > highest_qty:
			highest_qty = warehouse_info.qty
			best_warehouse = warehouse_info.store_location
			if flt(highest_qty) >= flt(item_qty):
				enough_stock = True
				
	return best_warehouse,highest_qty,enough_stock
	
		

@frappe.whitelist()	
def store_location_query(doctype, txt, searchfield, start, page_len, filters):

	best_warehouses = []
		
	if filters and filters.get('item_code'):
		item_code = frappe.db.escape(filters.get('item_code'))
	else:
		return best_warehouses
		
	if filters and filters.get('company'):
		company = frappe.db.escape(filters.get('company'))
	else:
		return best_warehouses
	

		
	stock_details = get_bills_and_stock(item_code,company = company)
	
	for key in stock_details:
		warehouse_info =stock_details[key]
		qty = warehouse_info.qty
		best_warehouse = warehouse_info.store_location
		best_warehouses.append((best_warehouse,))
		
	return best_warehouses

