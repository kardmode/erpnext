
# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, math
from frappe.utils import cint,flt
from frappe import throw, _
from frappe.model.document import Document
from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_best_bill,get_total_qty_for_item

class MRPImportEntry(Document):
	def validate(self):
		self.validate_duplicate_doc()
		self.validate_items()
		self.validate_duplicate_items()
	
	def on_update_after_submit(self):
		self.validate_duplicate_items()
		
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
		elif self.transaction_type == "MRP Production Order":
			doc_details = frappe.db.sql("""
						select name 
						from `tabMRP Import Entry`
						where
						name <> %s and transaction_type = %s and reference_name = %s
						""", (self.name,self.transaction_type,self.reference_name), as_dict=True)
						
			if doc_details:
				frappe.throw(_("Import Entry for production order {0} already exists.").format(self.reference_name))

	def validate_duplicate_items(self):
		
		total_transaction_qty = 0
		total_balance_qty = 0
		
		item_dict = {}
		from copy import deepcopy

		
		for d in self.get("items"):
			item = deepcopy(d.as_dict())
			item_alt = item["item_alt"]
			item_code = item["item_code"]
			
			import_bill = item["import_bill"]
			
			if (item_code,item_alt) in item_dict:
				if import_bill in item_dict[item_code]:
					item_dict[item_code,item_alt][import_bill]["stock_qty"] += flt(item["stock_qty"])
				else:
					item_dict[item_code,item_alt][import_bill] = item
				
			else:
				item_dict[item_code,item_alt] = {}
				item_dict[item_code,item_alt][import_bill] = item
		
		for item_code_key in item_dict:
			item_code_dict = item_dict[item_code_key]

			for import_bill_key in item_code_dict:
				
				d = item_code_dict[import_bill_key]
				# frappe.errprint(d)
				available_qty = get_total_qty_for_item(import_bill_key,d.item_code,d.item_alt,self.posting_date,self.posting_time)
				if self.transaction_type in ["Purchase Receipt","Addition"]:
					balance_qty = flt(available_qty) + flt(d.stock_qty)
				else:
					balance_qty = flt(available_qty) - flt(d.stock_qty)
			
				if balance_qty < 0:
					frappe.throw(_("Import Bill {0} does not have enough balance for Item {1}.").format(import_bill_key,item_code_key))
			
				if d.stock_qty:
					total_transaction_qty = total_transaction_qty + d.stock_qty
				if balance_qty:
					total_balance_qty = total_balance_qty + balance_qty
		
		self.total_balance_qty = total_balance_qty
		self.total_transaction_qty = total_transaction_qty
				
	def validate_items(self):
		from erpnext.manufacturing.doctype.mrp_production_order.mrp_production_order import get_item_det
		self.total = 0
		
		for d in self.get("items"):
		
			d.stock_qty = math.fabs(flt(d.stock_qty))
			
			
			if not d.uom:
				if d.stock_uom:
					d.uom = d.stock_uom
				else:
					frappe.throw(_("{0} ({1}) cannot have no units.").format(d.idx,d.item_code))
					
					
			item_dict = get_item_det(d.item_code,d.uom)
			
			if d.conversion_factor == 0:
				d.conversion_factor = item_dict.conversion_factor
			
			if d.stock_qty == 0 and d.qty == 0:
				frappe.throw(_("{0} ({1}) cannot have 0 quantity.").format(d.idx,d.item_code))
			elif d.stock_qty == 0:
				d.stock_qty = d.qty * d.conversion_factor
			elif d.qty == 0:
				d.qty = d.stock_qty / d.conversion_factor

			if d.item_name == None or d.item_name == "":
				d.item_name = item_dict.item_name
				
			if d.import_bill:
				d.available_qty = get_total_qty_for_item(d.import_bill,d.item_code,d.item_alt,self.posting_date,self.posting_time)
			else:
				frappe.throw(_("Item {1} does not have an import bill.").format(d.item_code))

			
			if self.transaction_type in ["Purchase Receipt","Addition"]:
				d.balance_qty = flt(d.available_qty) + flt(d.stock_qty)
			else:
				d.balance_qty = flt(d.available_qty) - flt(d.stock_qty)
				
			d.amount = d.rate * d.qty
			
			self.total = self.total + d.amount
		
		self.grand_total = self.total

	def update_items_for_pr(self,document,purpose,data=None):
		if purpose not in ["Purchase Receipt","Delivery Note","MRP Production Order"]:
			return None
		
		if not document:
			return None
			
			
		
		if purpose == "Purchase Receipt" and data == None:
			return None
			
		doc_details = []
		if purpose == "Purchase Receipt":
			doc_details = frappe.db.sql("""
					select t1.currency, t1.grand_total
					from `tabPurchase Receipt` t1
					where
					t1.name = %s
					""", (document), as_dict=True)
					
					
		if doc_details:

			for d in self.get("items"):
				if d.grand_total == 0:
					exchange_factor = 1
				else:
					exchange_factor = self.customs_entry_total/d.grand_total
				
				if exchange_factor == 0:
					exchange_factor = 1
				
				
				self.customs_exchange_rate = exchange_factor
				d.customs_exit_rate =  d.rate * exchange_factor
				d.import_bill = data["import_bill"]
				d.available_qty = get_total_qty_for_item(d.import_bill,d.item_code,d.item_alt,self.posting_date,self.posting_time)
				d.balance_qty = flt(d.available_qty) + flt(d.stock_qty)
					
	def get_items_from(self,document,purpose,data=None):
		if purpose not in ["Purchase Receipt","Delivery Note","MRP Production Order"]:
			return None
		
		if not document:
			return None
			
		
		if purpose == "Purchase Receipt" and data == None:
			return None
			
		
		if not self.title or self.title == "":
			document_details = frappe.get_doc(purpose,document)

			if document_details.get("title"):
				self.title = document_details.title
			
		self.items = []
		self.transaction_type = purpose
		self.reference_name = document
		self.customs_entry_total = 0
		
		doc_items = []
		if purpose == "Purchase Receipt":
			self.customs_entry_total = data["customs_entry_total"]
			doc_items = frappe.db.sql("""
					select t1.currency, t1.grand_total, t2.item_code,t2.qty,t2.uom,t2.base_rate, t2.rate,t2.amount, t2.stock_qty,t2.stock_uom, t2.item_name, t2.conversion_factor
					from `tabPurchase Receipt` t1,`tabPurchase Receipt Item` t2
					where
					t1.name = %s and t2.parent =  t1.name
					""", (document), as_dict=True)
		elif purpose == "Delivery Note":
			doc_items = frappe.db.sql("""
					select t2.item_code,t2.qty,t2.uom,t2.base_rate, t2.rate,t2.amount, t2.stock_qty,t2.stock_uom, t2.item_name, t2.conversion_factor
					from `tabDelivery Note` t1,`tabDelivery Note Item` t2
					where
					t1.name = %s and t2.parent =  t1.name
					""", (document), as_dict=True)
					
			new_doc_items = []
			
			if data == None or data == 0:
				pass
			elif data == 1:
				for d in doc_items:
					mrp_pro_details = frappe.db.sql("""
						select t2.item_code
						from `tabMRP Production Order` t1,`tabMRP Production Plan Item` t2
						where
						t1.reference_doctype = "Delivery Note"
						and t1.reference_name = %s
						and t2.docstatus = 1
						and t2.parent = t1.name
						and t2.item_code = %s
						""", (document,d.item_code), as_dict=True)
						
					if mrp_pro_details:
						pass
					else:
						new_doc_items.append(d)
				
				mrp_se_item_details = frappe.db.sql("""
					select t3.item_code,t3.qty, t3.uom, t3.basic_rate as stock_rate, t3.transfer_qty as stock_qty ,t3.stock_uom, t3.item_name
					from `tabMRP Production Order` t1,`tabStock Entry` t2, `tabStock Entry Detail` t3
					where
					t1.reference_doctype = "Delivery Note"
					and t1.reference_name = %s
					and t2.custom_production_order = t1.name
					and t2.docstatus = 1
					and t2.purpose = "Manufacture"
					and t3.parent = t2.name
					and t3.s_warehouse IS NOT NULL and (t3.t_warehouse IS NULL or t3.t_warehouse = '')
					""", (document), as_dict=True)	
					
						
				doc_items = new_doc_items + mrp_se_item_details
				merged_items = merge_items(doc_items)
				doc_items= []
				for key in merged_items:
					doc_items.append(merged_items[key])
				
		elif purpose == "MRP Production Order":
			doc_items = frappe.db.sql("""
					select t3.item_code,,t3.qty, t3.uom, t3.basic_rate as stock_rate,t3.transfer_qty as stock_qty ,t3.stock_uom, t3.item_name
					from `tabStock Entry` t2, `tabStock Entry Detail` t3
					where
					t2.custom_production_order = %s
					and t2.docstatus = 1
					and t2.purpose = "Manufacture"
					and t3.parent = t2.name
					and t3.s_warehouse IS NOT NULL and (t3.t_warehouse IS NULL or t3.t_warehouse = '')
					""", (document), as_dict=True)			
		
					
		for d in doc_items:
			newd = self.append('items')
			newd.item_code = d.item_code
			newd.item_name = d.item_name
			newd.qty = d.qty
			newd.uom = d.uom
			newd.stock_qty = d.stock_qty
			newd.stock_uom = d.stock_uom
			newd.available_qty = 0
			newd.balance_qty = 0
			
			if purpose in ["Delivery Note","MRP Production Order"]:					
				if purpose == "MRP Production Order":
					newd.rate =  d.stock_rate * d.stock_qty/d.qty
					newd.base_rate = newd.rate
					newd.amount = newd.rate * newd.qty
					newd.customs_exit_rate = newd.base_rate
					newd.conversion_factor = d.qty/d.stock_qty
				else:
					newd.rate =  d.rate
					newd.base_rate =  d.base_rate
					newd.amount = d.amount
					newd.customs_exit_rate = newd.base_rate
					newd.conversion_factor = d.conversion_factor

				
				import_bill,highest_qty,enough_stock = get_best_bill(d.item_code,d.item_alt,company=self.company,posting_date=self.posting_date,posting_time=self.posting_time)
				if import_bill:
					newd.import_bill = import_bill
					newd.available_qty = highest_qty
					newd.balance_qty = newd.available_qty - newd.stock_qty
					
			else:		
				if d.grand_total == 0:
					exchange_factor = 1
				else:
					exchange_factor = self.customs_entry_total/d.grand_total
				
				if exchange_factor == 0:
					exchange_factor = 1
				
				
				self.customs_exchange_rate = exchange_factor
				
				newd.rate =  d.rate
				newd.base_rate =  d.base_rate
				newd.amount = d.amount
				newd.customs_exit_rate =  d.rate * exchange_factor
				newd.conversion_factor = d.conversion_factor
				newd.import_bill = data["import_bill"]
				newd.available_qty = get_total_qty_for_item(newd.import_bill,newd.item_code,d.item_alt,self.posting_date,self.posting_time)
				newd.balance_qty = flt(newd.available_qty) + flt(newd.stock_qty)
				
	def set_import_bill_for(self,purpose,data=None):
		if purpose not in ["Purchase Receipt","Delivery Note"]:
			return None
		
		if purpose == "Purchase Receipt" and data == None:
			return None
			
		for d in self.get("items"):
			if purpose == "Purchase Receipt":
				d.import_bill = data
				d.available_qty = get_total_qty_for_item(d.import_bill,d.item_code,d.item_alt,self.posting_date,self.posting_time)
				d.balance_qty = flt(d.available_qty) + flt(d.stock_qty)
			else:
				import_bill,highest_qty,enough_stock = get_best_bill(d.item_code,d.item_alt,company=self.company,posting_date=self.posting_date,posting_time=self.posting_time)
				if import_bill:
					newd.import_bill = import_bill
					newd.available_qty = highest_qty
					newd.balance_qty = newd.available_qty - newd.stock_qty
				
def merge_items(dicts):
	item_dict = {}
	
	from copy import deepcopy

	new_list = deepcopy(dicts)
	for item in new_list:
		item_code = item["item_code"]
		if item_dict.has_key(item_code):
			item_dict[item_code]["stock_qty"] += flt(item["stock_qty"])
		else:
			item_dict[item_code] = item
			

	return item_dict
	
def merge_items_ext(dicts,main_key,keys_to_add):
	item_dict = {}
	from copy import deepcopy

	new_list = deepcopy(dicts)
	for item in new_list:
		if not item.has_key(main_key):
			frappe.errprint(_("Main Key {0} not found in list entry being merged.").format(main_key))
			continue
			# frappe.throw(_("Main Key {0} not found in list entry being merged.").format(main_key))

		item_code = item[main_key]
		if item_dict.has_key(item_code):
			for k in keys_to_add:
				item_dict[item_code][k] += flt(item[k])
		else:
			item_dict[item_code] = item
			

	return item_dict
	
def update_import_entry(stock_entry, method):
	if stock_entry.doctype in ["Delivery Note","Purchase Receipt","MRP Production Order"]:
		import_entries = frappe.get_list("MRP Import Entry", fields=("name"), filters={"transaction_type": stock_entry.doctype, "reference_name":stock_entry.name, "docstatus": 1})
		if import_entries:
			frappe.throw(_("{0} - {1} has a linked and submitted MRP Import Entry.").format(stock_entry.doctype,stock_entry.name))

@frappe.whitelist()					
def get_item_det(item_code,uom=None):
	item = frappe.db.sql("""select name,item_name, docstatus, description, image,
		is_sub_contracted_item, stock_uom, default_bom, last_purchase_rate
		from `tabItem` where name=%s""", item_code, as_dict = 1)
	
	if not item:
		frappe.throw(_("Item: {0} does not exist in the system").format(item_code))
	
	details = item[0]
	details.uom = uom or details.stock_uom
	if uom:
		from erpnext.stock.get_item_details import get_conversion_factor
		details.update(get_conversion_factor(item_code, uom))

	# from erpnext.stock.get_item_details import get_item_price
	
	# args = frappe._dict({"item_code":item_code,"price_list":"Buying","uom",details.uom})

	# details.price_list_rate = get_item_price(args, item_code)
	return details