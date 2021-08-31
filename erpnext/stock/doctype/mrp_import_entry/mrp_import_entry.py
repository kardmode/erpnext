
# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, math
from frappe.utils import cint,flt
from frappe.utils import money_in_words
from frappe import throw, _
from frappe.model.document import Document
from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_best_bill,get_total_qty_for_item
from erpnext.stock.utils import validate_item_uoms

class MRPImportEntry(Document):
	def validate(self):
		self.validate_duplicate_doc()
		# validate_item_uoms(self)
		self.validate_items()
		self.validate_duplicate_items()
		self.create_summary()

	def on_submit(self):
		if not self.remarks:
			frappe.throw(_("Remarks are required.".format()))

		if not self.reference_number:
			frappe.throw(_("Reference is required.".format()))

		self.validate_duplicate_doc(True)
		self.validate_items(True)
		self.validate_duplicate_items(True)
		self.create_summary()
		
	def on_update_after_submit(self):
	
		if not self.remarks:
			frappe.throw(_("Remarks are required.".format()))

		if not self.reference_number:
			frappe.throw(_("Reference is required.".format()))
	
		self.validate_duplicate_doc(True)
		self.validate_items(True)
		self.validate_duplicate_items(True)
		self.create_summary()
		
	def on_trash(self):
		if self.docstatus == 2:
			if not frappe.session.user == 'Administrator':
				frappe.throw(_("Deletion of cancelled documents is not permitted.".format()))

	def validate_duplicate_doc(self,submit = False):
		

		if submit:
			if self.transaction_type in ["Addition"] and self.docstatus < 1:
				if "Stock Manager" not in frappe.get_roles(frappe.session.user):
					frappe.throw(_("Manager Approval Required to Submit Addition Import Entries").format(self.transaction_type))
			
			if self.transaction_type in ["Deduction"] and self.docstatus < 1:
				if "Stock Manager" not in frappe.get_roles(frappe.session.user):
					frappe.throw(_("Manager Approval Required to Submit Addition Import Entries").format(self.transaction_type))


		if self.transaction_type in ["Purchase Receipt","Delivery Note","MRP Production Order"]:
			if not self.reference_name:
				frappe.throw(_("Import Entry of transaction type {0} must have a reference.").format(self.transaction_type))

	
		if self.transaction_type == "Purchase Receipt" and self.reference_name:
			ref_doc = frappe.db.sql("""
					select name, docstatus
					from `tabPurchase Receipt`
					where
					name = %s
					and docstatus < 2
					""", (self.reference_name), as_dict=True)
		
			if submit:
				if not ref_doc:
					frappe.throw(_("Purchase receipt {0} doesn't exist.").format(self.reference_name))
				elif not ref_doc[0].docstatus == 1:
					frappe.throw(_("Purchase receipt {0} needs to be submitted before import entry.").format(self.reference_name))

		
			doc_details = frappe.db.sql("""
						select name
						from `tabMRP Import Entry`where
						name <> %s 
						and transaction_type = %s 
						and reference_name = %s
						and docstatus < 2
						""", (self.name,self.transaction_type,self.reference_name), as_dict=True)
						
			if doc_details:
				frappe.throw(_("Import Entry for purchase receipt {0} already exists.").format(self.reference_name))

		
		
		elif self.transaction_type == "Delivery Note" and self.reference_name:
			ref_doc = frappe.db.sql("""
					select name, docstatus
					from `tabDelivery Note`
					where
					name = %s
					and docstatus < 2
					""", (self.reference_name), as_dict=True)
			
			if submit:
				if not ref_doc:
					frappe.throw(_("Delivery Note {0} doesn't exist.").format(self.reference_name))
				elif not ref_doc[0].docstatus == 1:
					frappe.throw(_("Delivery Note {0} needs to be submitted before import entry.").format(self.reference_name))

			
			doc_details = frappe.db.sql("""
						select name 
						from `tabMRP Import Entry`
						where
						name <> %s 
						and transaction_type = %s 
						and reference_name = %s
						and docstatus < 2
						""", (self.name,self.transaction_type,self.reference_name), as_dict=True)
						
			if doc_details:
				frappe.throw(_("Import Entry for delivery note {0} already exists.").format(self.reference_name))
		
		elif self.transaction_type == "MRP Production Order" and self.reference_name:
			ref_doc = frappe.db.sql("""
					select name, docstatus
					from `tabMRP Production Order`
					where
					name = %s
					and docstatus < 2
					""", (self.reference_name), as_dict=True)
			
			if submit:
				if not ref_doc:
					frappe.throw(_("MRP Production Order {0} doesn't exist.").format(self.reference_name))
				elif not ref_doc[0].docstatus == 1:
					frappe.throw(_("MRP Production Order {0} needs to be submitted before import entry.").format(self.reference_name))

			doc_details = frappe.db.sql("""
						select name 
						from `tabMRP Import Entry`
						where
						name <> %s 
						and transaction_type = %s 
						and reference_name = %s
						and docstatus < 2
						""", (self.name,self.transaction_type,self.reference_name), as_dict=True)
						
			if doc_details:
				frappe.throw(_("Import Entry for production order {0} already exists.").format(self.reference_name))
	
	def validate_items(self,submit = False):
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
				d.available_qty = 0
				if submit:
					frappe.throw(_("Item {0} does not have an import bill.").format(d.item_code))

			
			if self.transaction_type in ["Purchase Receipt","Addition"]:
				d.balance_qty = flt(d.available_qty) + flt(d.stock_qty)
			else:
				d.balance_qty = flt(d.available_qty) - flt(d.stock_qty)
				
			d.amount = d.rate * d.qty
			
			self.total = self.total + d.amount
		
		self.grand_total = self.total
		self.in_words = money_in_words(self.grand_total)
		
		
	def validate_duplicate_items(self,submit = False):
		
		total_transaction_qty = 0
		total_balance_qty = 0
		
		item_dict = {}
		from copy import deepcopy
		
		for d in self.get("items"):
			item = deepcopy(d.as_dict())
			item_alt = item["item_alt"]
			item_code = item["item_code"]
			import_bill = item["import_bill"]
			
			if (item_code,item_alt,import_bill) in item_dict:
				item_dict[item_code,item_alt,import_bill]["stock_qty"] += flt(item["stock_qty"])
			else:
				item_dict[item_code,item_alt,import_bill] = item
		
		for item_code_key in item_dict:
			
			d = item_dict[item_code_key]

			available_qty = get_total_qty_for_item(d.import_bill,d.item_code,d.item_alt,self.posting_date,self.posting_time)
			if self.transaction_type in ["Purchase Receipt","Addition"]:
				balance_qty = flt(available_qty) + flt(d.stock_qty)
			else:
				balance_qty = flt(available_qty) - flt(d.stock_qty)
		
			if balance_qty < 0:
				if submit:
					frappe.throw(_("Import Bill {0} does not have enough balance for Item {1}.").format(d.import_bill,d.item_code))
		
			if d.stock_qty:
				total_transaction_qty = total_transaction_qty + d.stock_qty
			if balance_qty:
				total_balance_qty = total_balance_qty + balance_qty
		
		self.total_balance_qty = total_balance_qty
		self.total_transaction_qty = total_transaction_qty
				
	


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
			
		if data == None:
			return None
		
		get_date = 1 if not data.get('get_date') else data["get_date"] 

		document_details = frappe.db.get_value(purpose, {"name": document}, ["title", "posting_date"], as_dict=True)
				
		if not self.title or self.title == "":
			if document_details.get("title"):
				self.title = document_details.title
		
		if get_date == 1:
			self.posting_date = document_details.posting_date
			
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
					
			
			
			get_manufactured_items = 0 if not data.get('get_manufactured_items') else data["get_manufactured_items"] 
			merge_manufactured_items = 0 if not data.get('merge_manufactured_items') else data["merge_manufactured_items"] 
			
			if get_manufactured_items == 1:
				pro_doc = frappe.db.get_value("MRP Production Order", {"reference_doctype": "Delivery Note","reference_name":document
					, "docstatus":1}, ["name","reference_title"], as_dict=True)
				
				if pro_doc and pro_doc.reference_title:
					new_remarks = pro_doc.name + ' ' + pro_doc.reference_title
					self.remarks = self.remarks + ' - ' + new_remarks if self.remarks else new_remarks
			
			
				new_doc_items = []
				
				po_items = frappe.db.sql("""
						select t2.item_code, t2.qty, t2.uom
						from `tabMRP Production Order` t1,`tabMRP Production Plan Item` t2
						where
						t1.reference_doctype = "Delivery Note"
						and t1.reference_name = %s
						and t2.docstatus = 1
						and t2.parent = t1.name
						""", (document), as_dict=True)
				
				for d in doc_items:
					found = False
					for i,p in enumerate(po_items):
						if d.item_code == p.item_code and d.qty == p.qty and d.uom == p.uom:
							found = True;
							po_items.pop(i)
							break
							
					if not found:
						new_doc_items.append(d)
				
				mrp_se_item_details = frappe.db.sql("""
					select t3.item_code,t3.qty, t3.uom, t3.basic_rate as base_rate,t3.amount, t3.transfer_qty as stock_qty ,t3.stock_uom, t3.item_name, t3.conversion_factor
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

				if merge_manufactured_items == 1:
					merged_items = merge_items(doc_items)
					doc_items= []
					for key in merged_items:
						doc_items.append(merged_items[key])
				
		elif purpose == "MRP Production Order":
			doc_items = frappe.db.sql("""
					select t3.item_code,,t3.qty, t3.uom, t3.basic_rate as base_rate,t3.amount,t3.transfer_qty as stock_qty ,t3.stock_uom, t3.item_name, t3.conversion_factor
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
				
				# if purpose == "MRP Production Order" or 'stock_rate' in d:
					# newd.rate =  d.stock_rate * d.stock_qty/d.qty
					# newd.base_rate = newd.rate
					# newd.amount = newd.rate * newd.qty
					# newd.conversion_factor = d.qty/d.stock_qty
				
				newd.base_rate =  d.base_rate
				newd.rate =  d.rate or d.base_rate
				newd.amount = d.amount
				newd.conversion_factor = d.conversion_factor
				newd.customs_exit_rate = d.base_rate

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
					
	def create_summary(self):
		self.summary = create_condensed_table(merge_for_summary(self.items))
		
def merge_for_summary(dicts):
	item_dict = {}
	
	from copy import deepcopy

	new_list = deepcopy(dicts)
	for item in new_list:
		import_bill = item.import_bill
		uom = item.uom
		if (import_bill,uom) in item_dict:
			item_dict[import_bill,uom].stock_qty += flt(item.stock_qty)
			item_dict[import_bill,uom].qty += flt(item.qty)
		else:
			item_dict[import_bill,uom] = item
			
	return item_dict

def create_condensed_table(items):	
	joiningtext = """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>
				<th>Import Bill</th>
				<th>Total Qty</th>
				<th>UOM</th>
				<th></th>
			</tr></thead><tbody>"""
			
	for key in items:
		item = items[key]
		
		joiningtext += """<tr>
				<td>""" + str(item.import_bill) +"""</td>
				<td>""" + str(item.qty) +"""</td>
				<td>""" + str(item.uom) +"""</td>
				</tr>"""

	joiningtext += """</tbody></table>"""
	return joiningtext
	
def merge_items(dicts):
	item_dict = {}
	
	from copy import deepcopy

	new_list = deepcopy(dicts)
	for item in new_list:
		item_code = item["item_code"]
		uom = item["uom"]
		base_rate = item["base_rate"]
		if (item_code,uom,base_rate) in item_dict:
			item_dict[item_code,uom,base_rate]["stock_qty"] += flt(item["stock_qty"])
			item_dict[item_code,uom,base_rate]["qty"] += flt(item["qty"])
		else:
			item_dict[item_code,uom,base_rate] = item
			

	return item_dict
	
	
def update_import_entry(stock_entry, method):
	if stock_entry.doctype in ["Delivery Note","Purchase Receipt","MRP Production Order"]:
		import_entries = frappe.get_list("MRP Import Entry", fields=("name"), filters={"transaction_type": stock_entry.doctype, "reference_name":stock_entry.name, "docstatus": 1})
		if import_entries:
			frappe.throw(_("{0} - {1} has a linked and submitted MRP Import Entry.").format(stock_entry.doctype,stock_entry.name))

@frappe.whitelist()					
def get_item_det(item_code,uom=None,item_alt=None,company=None,posting_date=None,posting_time=None):
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

	if company and posting_date and posting_time:
		import_bill,highest_qty,enough_stock = get_best_bill(item_code,item_alt,company=company,posting_date=posting_date,posting_time=posting_time)
		details.import_bill = import_bill
	return details
	
@frappe.whitelist()					
def update_old_entries(type = "units", check=True):
	
	if type == "units":
		if check:
			stock_details = frappe.db.sql("""
							select t2.name, t2.stock_qty, t2.stock_uom, t2.qty,t2.uom
							from `tabMRP Import Entry Item` t2
							where uom is null
							""", as_dict=True)	
			if stock_details:
				for item in stock_details:
					frappe.msgprint(_("UOM {0} Stock UOM {1} Qty {2}, Stock Qty {3}").format(item.uom,item.stock_uom, item.qty,item.stock_qty))
			else:
				frappe.msgprint(_("None Found").format())
		else:
			frappe.db.sql("""update `tabMRP Import Entry Item` set uom = stock_uom, qty=stock_qty where uom is null""")
	elif type == "type":
		if check:
			stock_details = frappe.db.sql("""
							select t2.name, t2.transaction_type
							from `tabMRP Import Entry` t2
							where t2.transaction_type in ("Delivery Note","Purchase Receipt")
							""", as_dict=True)	
			if stock_details:
				for item in stock_details:
					frappe.msgprint(_("{0} - {1}").format(item.name,item.transaction_type))
			else:
				frappe.msgprint(_("None Found").format())
		else:
			frappe.db.sql("""update `tabMRP Import Entry` set reference_doctype = transaction_type where transaction_type in ("Delivery Note","Purchase Receipt")""")
	elif type == "transaction":
		if check:
			stock_details = frappe.db.sql("""
							select t2.name, t2.transaction_type
							from `tabMRP Import Entry` t2
							where t2.transaction_type in ("Delivery Note","Purchase Receipt")
							""", as_dict=True)	
			if stock_details:
				for item in stock_details:
					frappe.msgprint(_("{0} - {1}").format(item.name,item.transaction_type))
			else:
				frappe.msgprint(_("None Found").format())
		else:
			frappe.db.sql("""update `tabMRP Import Entry` set reference_doctype = transaction_type where transaction_type in ("Delivery Note","Purchase Receipt")""")

	