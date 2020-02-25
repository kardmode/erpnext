# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, math
from frappe.utils import cstr, flt, cint,nowtime, nowdate, add_days, comma_and, getdate,get_time
from frappe import throw, _
from frappe.model.document import Document

class MRPImportBill(Document):
	def autoname(self):
		if self.company:
			suffix = " - " + frappe.db.get_value("Company", self.company, "abbr")
			if not self.document_name.endswith(suffix):
				self.name = self.document_name + suffix
		else:
			self.name = self.document_name
			
	def get_summary(self):
		items = get_items_in_bill(self.name)
		summary = self.create_condensed_table(items)
		
	
	def on_update(self):
		if self.disabled:
			self.on_disable()
			
	def on_disable(self):
	
		bins = frappe.db.sql("select * from `tabMRP Import Entry` where import_bill = %s",
			self.name, as_dict=1)
		
		final_qty = 0
		for d in bins:
			final_qty = final_qty + flt(d['stock_qty'])
		
		if final_qty != 0:
			throw(_("Import Bill {0} can not be disabled as quantity exists for Item {1}").format(self.name, d['item_code']))
	


	def on_trash(self):
		# delete bin
		
		if self.check_if_sle_exists():
			throw(_("Warehouse can not be deleted as MRP Import Entry exists for this bill."))
			
		


	def check_if_sle_exists(self):
		return frappe.db.sql("""select name from `tabMRP Import Entry`
			where import_bill = %s limit 1""", self.name)

	
					
					
def create_condensed_table(items):
	summary = ""
	
	joiningtext = """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>
				<th>Entry Name</th>
				<th>Item Code</th>
				<th>Total Qty</th>
				<th>Stock UOM</th>
				<th></th>
			</tr></thead><tbody>"""
				
	for key, value in items.iteritems():
		
		joiningtext += """<tr>
					<td>""" + str(key) +"""</td>
					<td>""" + str(value["item_code"]) +"""</td>
					<td>""" + str(value["stock_qty"]) +"""</td>
					<td>""" + str(value["stock_uom"]) +"""</td>
					</tr>"""
	joiningtext += """</tbody></table>"""
	summary += joiningtext
	return summary

def get_items_in_bill(import_bill,posting_date=None,posting_time=None):
	if not posting_date:
		posting_date = nowdate()
	if not posting_time:
		posting_time = nowtime()
	
	posting_time = get_time(posting_time)

	
	stock_details = frappe.db.sql("""select t1.item_code,t1.import_bill,t1.stock_qty,t1.stock_uom,t2.transaction_type,t2.reference_name 
									from `tabMRP Import Entry Item` t1, `tabMRP Import Entry` t2 
									where t1.import_bill = %s and t2.name = t1.parent and t2.docstatus = 1 
									and (t2.posting_date < %s or (t2.posting_date = %s and t2.posting_time < %s))
									ORDER BY t2.posting_date,t2.posting_time""", (import_bill,posting_date,posting_date,posting_time), as_dict=True)
	
	item_dict = {}
	import copy
	new_list = copy.deepcopy(stock_details)
	for item in new_list:
		item_code = item["item_code"]
		

		if not validate_ref_doc(item["transaction_type"],item["reference_name"]):
			continue
		
		if item_dict.has_key(item_code):
		
			if item["transaction_type"] in ["Purchase Receipt","Addition"]:
				item_dict[item_code]["stock_qty"] += flt(item["stock_qty"])
			else:
				item_dict[item_code]["stock_qty"] -= flt(item["stock_qty"])
			
		else:
			item_dict[item_code] = item
			if item["transaction_type"] in ["Purchase Receipt","Addition"]:
				item_dict[item_code]["stock_qty"] = flt(item["stock_qty"])
			else:
				item_dict[item_code]["stock_qty"] = -1 * flt(item["stock_qty"])
			

	return item_dict

@frappe.whitelist()
def get_total_qty_for_item(import_bill,item_code,posting_date=None,posting_time=None):

	stock_details = []
	
	if not posting_date:
		posting_date = nowdate()
	if not posting_time:
		posting_time = nowtime()
	
	posting_time = get_time(posting_time)

	stock_details = frappe.db.sql("""
					select t1.name, t2.stock_qty, t2.stock_uom, t1.transaction_type, t1.reference_name
					from `tabMRP Import Entry` t1,`tabMRP Import Entry Item` t2
					where t2.import_bill = %s and t2.item_code = %s
					and t2.stock_qty <> 0 and t1.name = t2.parent and t1.docstatus = 1
					and (t1.posting_date < %s or (t1.posting_date = %s and t1.posting_time < %s))
					ORDER BY t2.stock_qty DESC
					""", (import_bill,item_code,posting_date,posting_date,posting_time), as_dict=True)	
					
	
	total_qty = 0
	for item in stock_details:
		
		if not validate_ref_doc(item["transaction_type"],item["reference_name"]):
			continue
		
		if item.transaction_type in ["Purchase Receipt","Addition"]:
			total_qty = total_qty + flt(item.stock_qty)
			
		else:
			total_qty = total_qty - flt(item.stock_qty)
			
	return total_qty
	
@frappe.whitelist()
def get_bills_and_stock(item_code=None,company = None,posting_date=None,posting_time=None):

	if not item_code or not company:
		return []

	if not posting_date:
		posting_date = nowdate()
	if not posting_time:
		posting_time = nowtime()
	
	posting_time = get_time(posting_time)

	stock_details = frappe.db.sql("""
					select t1.name, t2.import_bill, t2.item_code,t2.stock_qty,t2.stock_uom, t2.item_name, t1.transaction_type,t1.reference_name
					from `tabMRP Import Entry` t1,`tabMRP Import Entry Item` t2
					where t1.company = %s 
					and t1.docstatus = 1
					and t2.parent =  t1.name 
					and t2.item_code = %s
					and t2.stock_qty <> 0
					and (t1.posting_date < %s or (t1.posting_date = %s and t1.posting_time < %s))
					ORDER BY t2.stock_qty DESC
					""", (company,item_code,posting_date,posting_date,posting_time), as_dict=True)		
	
	
	best_warehouses = []
	
	item_dict = {}
	import copy
	new_list = copy.deepcopy(stock_details)
	for item in new_list:
		import_bill = item["import_bill"]
		
		if not validate_ref_doc(item["transaction_type"],item["reference_name"]):
			continue

		if item_dict.has_key(import_bill):
		
			if item["transaction_type"] in ["Purchase Receipt","Addition"]:
				item_dict[import_bill]["stock_qty"] += flt(item["stock_qty"])
			else:
				item_dict[import_bill]["stock_qty"] -= flt(item["stock_qty"])
		else:
			item_dict[import_bill] = item
			if item["transaction_type"] in ["Purchase Receipt","Addition"]:
				item_dict[import_bill]["stock_qty"] = flt(item["stock_qty"])
			else:
				item_dict[import_bill]["stock_qty"] = -1 * flt(item["stock_qty"])
			
		

	return item_dict
	
@frappe.whitelist()
def get_best_bill(item_code=None,item_qty = 0, order_by_least = False,company = None,posting_date=None,posting_time=None):
	
	enough_stock = False
	
	best_warehouse = None

	if not item_code or not company:
		return best_warehouse,enough_stock
	
	item_dict = get_bills_and_stock(item_code,company=company,posting_date = posting_date,posting_time = posting_time)
	
	highest_qty = 0
	best_warehouse = None
	
	for key in item_dict:
		warehouse_info =item_dict[key]
		if warehouse_info.stock_qty > highest_qty:
			highest_qty = warehouse_info.stock_qty
			best_warehouse = warehouse_info.import_bill
			if flt(highest_qty) >= flt(item_qty):
				enough_stock = True
				
	return best_warehouse,highest_qty,enough_stock
	
		

@frappe.whitelist()	
def import_bill_query(doctype, txt, searchfield, start, page_len, filters):

	best_warehouses = []
		
	if filters and filters.get('item_code'):
		item_code = filters.get('item_code')
	else:
		return best_warehouses
		
	if filters and filters.get('company'):
		company = filters.get('company')
	else:
		return best_warehouses
		
	posting_date = None
	posting_time = None
	if filters and filters.get('posting_date'):
		posting_date = filters.get('posting_date')
		
	if filters and filters.get('posting_time'):
		posting_time = filters.get('posting_time')
		
	if filters and filters.get('filters'):
		filters = filters.get('filters')
		
	stock_details = get_bills_and_stock(item_code,company = company,posting_date = posting_date,posting_time = posting_time)
	
	for key in stock_details:
		warehouse_info =stock_details[key]
		qty = warehouse_info.stock_qty
		best_warehouse = warehouse_info.import_bill
		best_warehouses.append((best_warehouse,))
		
	return best_warehouses

@frappe.whitelist()
def get_item_rate_in_bill(import_bill,item_code,uom = None, posting_date=None,posting_time=None):

	stock_details = []
	
	if not posting_date:
		posting_date = nowdate()
	if not posting_time:
		posting_time = nowtime()
		
	posting_time = get_time(posting_time)

	
	stock_details = frappe.db.sql("""
					select t1.name, t2.stock_qty, t2.stock_uom, t1.transaction_type,t1.reference_name, t2.conversion_factor, t2.rate,t2.customs_exit_rate
					from `tabMRP Import Entry` t1,`tabMRP Import Entry Item` t2
					where t2.import_bill = %s and t2.item_code = %s and t2.stock_qty <> 0 
					and t1.name = t2.parent and t1.docstatus = 1
					and t1.transaction_type IN ('Purchase Receipt', 'Addition')
					and (t1.posting_date < %s or (t1.posting_date = %s and t1.posting_time < %s))
					ORDER BY t1.posting_date,t1.posting_time
					""", (import_bill,item_code,posting_date,posting_date,posting_time), as_dict=True)	
						
						
				

	if stock_details:
		from erpnext.stock.get_item_details import get_conversion_factor

		for item in stock_details:
			
			if not validate_ref_doc(item["transaction_type"],item["reference_name"]):
				continue
		

			stock_rate = flt(item.customs_exit_rate) * flt(item.conversion_factor)			

			if uom == None:
				return stock_rate
			else:
				conversion_factor = get_conversion_factor(item_code,uom).get("conversion_factor") or 1

				return (flt(stock_rate) / flt(conversion_factor))
	
	else:
		return 0	

def validate_ref_doc(transaction_type,reference_name):
	if transaction_type in ["Purchase Receipt","Delivery Note","MRP Production Order"]:
		doc_details = frappe.get_doc(transaction_type,reference_name)
		if doc_details.docstatus == 1:
			return True
		else:
			return False
	else:
		return True