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

	
	stock_details = frappe.db.sql("""select t2.name,t1.item_code,t1.item_name,t1.item_alt,t1.import_bill,t1.stock_qty,t1.stock_uom,t2.transaction_type,t2.reference_name 
									from `tabMRP Import Entry Item` t1, `tabMRP Import Entry` t2 
									where t1.import_bill = %s and t2.name = t1.parent and t2.docstatus = 1 
									and (t2.posting_date < %s or (t2.posting_date = %s and t2.posting_time < %s))
									ORDER BY t2.posting_date,t2.posting_time""", (import_bill,posting_date,posting_date,posting_time), as_dict=True)
		
	item_dict = {}
	import copy
	new_list = copy.deepcopy(stock_details)
	for item in new_list:
		item_code = item["item_code"]
		item_alt = item["item_alt"]
		

		if not validate_ref_doc(item["transaction_type"],item["reference_name"]):
			continue
		

		if item_dict.has_key(item_code):

			if item_alt:

				if item_dict[item_code]["item_alts"].has_key(item_alt):

					if item["transaction_type"] in ["Purchase Receipt","Addition"]:
						item_dict[item_code]["item_alts"][item_alt]["stock_qty"] += flt(item["stock_qty"])
					else:
						item_dict[item_code]["item_alts"][item_alt]["stock_qty"] -= flt(item["stock_qty"])
						
				else:
					item_dict[item_code]["item_alts"] = {item_alt:{"item_code":item_alt,"stock_qty":0}}
					
					if item["transaction_type"] in ["Purchase Receipt","Addition"]:
						item_dict[item_code]["item_alts"][item_alt]["stock_qty"] = flt(item["stock_qty"])
					else:
						item_dict[item_code]["item_alts"][item_alt]["stock_qty"] = -1 * flt(item["stock_qty"])
					

			else:			
				if item["transaction_type"] in ["Purchase Receipt","Addition"]:
					item_dict[item_code]["stock_qty"] += flt(item["stock_qty"])
				else:
					item_dict[item_code]["stock_qty"] -= flt(item["stock_qty"])
			
		else:
			item["item_alts"] = {}
			item_dict[item_code] = item
			
			if item_alt:
				item_dict[item_code]["item_alts"] = {item_alt:{"item_code":item_alt,"stock_qty":0}}

				if item["transaction_type"] in ["Purchase Receipt","Addition"]:
					item_dict[item_code]["item_alts"][item_alt]["stock_qty"] = flt(item["stock_qty"])
				else:
					item_dict[item_code]["item_alts"][item_alt]["stock_qty"] = -1 * flt(item["stock_qty"])
			
				item_dict[item_code]["stock_qty"] = 0
			else:
				if item["transaction_type"] in ["Purchase Receipt","Addition"]:
					item_dict[item_code]["stock_qty"] = flt(item["stock_qty"])
				else:
					item_dict[item_code]["stock_qty"] = -1 * flt(item["stock_qty"])

	return item_dict

@frappe.whitelist()
def get_total_qty_for_item(import_bill,item_code,item_alt = None, posting_date=None,posting_time=None):

	stock_details = []
	
	if not posting_date:
		posting_date = nowdate()
	if not posting_time:
		posting_time = nowtime()
	
	posting_time = get_time(posting_time)

	stock_details = frappe.db.sql("""
					select t1.name,t2.item_alt, t2.stock_qty, t2.stock_uom, t1.transaction_type, t1.reference_name
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

		if item_alt == item.item_alt:

			if item.transaction_type in ["Purchase Receipt","Addition"]:
				total_qty += flt(item.stock_qty)
			else:
				total_qty -= flt(item.stock_qty)
	
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
					select t1.name, t2.import_bill, t2.item_code,t2.stock_qty,t2.stock_uom, t2.item_name,t2.item_alt, t1.transaction_type,t1.reference_name
					from `tabMRP Import Entry` t1,`tabMRP Import Entry Item` t2
					where t1.company = %s 
					and t1.docstatus = 1
					and t2.parent =  t1.name 
					and t2.item_code = %s
					and t2.stock_qty <> 0
					and (t1.posting_date < %s or (t1.posting_date = %s and t1.posting_time < %s))
					ORDER BY t2.stock_qty DESC
					""", (company,item_code,posting_date,posting_date,posting_time), as_dict=True)		
	

	item_dict = {}
	import copy
	new_list = copy.deepcopy(stock_details)
	for item in new_list:
		import_bill = item["import_bill"]
		item_alt = item["item_alt"]
		
		
		if not validate_ref_doc(item["transaction_type"],item["reference_name"]):
			continue

		if item_dict.has_key(import_bill):
			if item_alt:

				if item_dict[import_bill]["item_alts"].has_key(item_alt):

					if item["transaction_type"] in ["Purchase Receipt","Addition"]:
						item_dict[import_bill]["item_alts"][item_alt]["stock_qty"] += flt(item["stock_qty"])
					else:
						item_dict[import_bill]["item_alts"][item_alt]["stock_qty"] -= flt(item["stock_qty"])
						
				else:
					item_dict[import_bill]["item_alts"] = {item_alt:{"item_code":item_alt,"stock_qty":0}}
					
					if item["transaction_type"] in ["Purchase Receipt","Addition"]:
						item_dict[import_bill]["item_alts"][item_alt]["stock_qty"] = flt(item["stock_qty"])
					else:
						item_dict[import_bill]["item_alts"][item_alt]["stock_qty"] = -1 * flt(item["stock_qty"])
					

			else:			
				if item["transaction_type"] in ["Purchase Receipt","Addition"]:
					item_dict[import_bill]["stock_qty"] += flt(item["stock_qty"])
				else:
					item_dict[import_bill]["stock_qty"] -= flt(item["stock_qty"])
			
		else:
			item["item_alts"] = {}
			item_dict[import_bill] = item
			
			if item_alt:
				item_dict[import_bill]["item_alts"] = {item_alt:{"item_code":item_alt,"stock_qty":0}}

				if item["transaction_type"] in ["Purchase Receipt","Addition"]:
					item_dict[import_bill]["item_alts"][item_alt]["stock_qty"] = flt(item["stock_qty"])
				else:
					item_dict[import_bill]["item_alts"][item_alt]["stock_qty"] = -1 * flt(item["stock_qty"])
			
				item_dict[import_bill]["stock_qty"] = 0
			else:
				if item["transaction_type"] in ["Purchase Receipt","Addition"]:
					item_dict[import_bill]["stock_qty"] = flt(item["stock_qty"])
				else:
					item_dict[import_bill]["stock_qty"] = -1 * flt(item["stock_qty"])

	return item_dict
	
@frappe.whitelist()
def get_best_bill(item_code=None,item_alt=None, item_qty = 0, order_by_least = False,company = None,posting_date=None,posting_time=None):
	
	enough_stock = False
	
	best_import_doc = None

	if not item_code or not company:
		return best_import_doc,enough_stock
	
	item_dict = get_bills_and_stock(item_code,company=company,posting_date = posting_date,posting_time = posting_time)
	
	for key in item.item_alts:
		item_alt = item.item_alts[key]

	highest_qty = 0
	best_import_doc = None
	
	for key in item_dict:
		item = item_dict[key]
		
		if item_alt:
			for key in item.item_alts:
				stored_item_alt = item.item_alts[key]
				if stored_item_alt.item_code == item_alt:
					if stored_item_alt.stock_qty > highest_qty:
						highest_qty = stored_item_alt.stock_qty
						best_import_doc = item.import_bill
						if flt(highest_qty) >= flt(item_qty):
							enough_stock = True
		else:
			if item.stock_qty > highest_qty:
				highest_qty = item.stock_qty
				best_import_doc = item.import_bill
				if flt(highest_qty) >= flt(item_qty):
					enough_stock = True
				
		
	return best_import_doc,highest_qty,enough_stock
	
		

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
	
	item_alt = None
	if filters and filters.get('item_alt'):
		item_alt = filters.get('item_alt')
	
	posting_date = None
	posting_time = None
	if filters and filters.get('posting_date'):
		posting_date = filters.get('posting_date')
		
	if filters and filters.get('posting_time'):
		posting_time = filters.get('posting_time')
		
	if filters and filters.get('filters'):
		filters = filters.get('filters')
		
	item_dict = get_bills_and_stock(item_code,company = company,posting_date = posting_date,posting_time = posting_time)
	
	for key in item_dict:
		item = item_dict[key]
		
		if item_alt:
			for key in item.item_alts:
				stored_item_alt = item.item_alts[key]
				if stored_item_alt.item_code == item_alt:
					if stored_item_alt.stock_qty > 0:
						best_warehouse = item.import_bill
						best_warehouses.append((best_warehouse,))
		else:
			if item.stock_qty > 0:
				best_warehouse = item.import_bill
				best_warehouses.append((best_warehouse,))
		
	return best_warehouses

@frappe.whitelist()
def get_item_rate_in_bill(import_bill,item_code,item_alt=None,uom = None, posting_date=None,posting_time=None):
	rates = []
	stock_details = []
	
	if not posting_date:
		posting_date = nowdate()
	if not posting_time:
		posting_time = nowtime()
		
	posting_time = get_time(posting_time)

	
	stock_details = frappe.db.sql("""
					select t1.name, t1.transaction_type, t1.reference_name,
					t1.reference_number, t1.reference_date,
					t2.item_alt, t2.stock_qty, t2.stock_uom,
					t2.conversion_factor, t2.rate,
					t2.customs_exit_rate
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
		
			if item_alt:
				if not item_alt == item.item_alt:
					continue			
			
			rate_dict = {}
			
			stock_rate = flt(item.customs_exit_rate) * flt(item.conversion_factor)			

			if uom == None:
				rate_dict["rate"] = stock_rate
			else:
				conversion_factor = get_conversion_factor(item_code,uom).get("conversion_factor") or 1
				rate_dict["rate"] = (flt(stock_rate) / flt(conversion_factor))
				
			rates.append(rate_dict)
	
	else:
		rates.append({'rate':0})
	
	rate_summary = ''
	for r in rates:
		rate_text = str(r['rate'])
		if rate_summary == '':
			rate_summary = rate_text
		else:
			rate_summary = rate_summary + ', ' + rate_text
		
	return rates,rate_summary

def validate_ref_doc(transaction_type,reference_name):
	if transaction_type in ["Purchase Receipt","Delivery Note","MRP Production Order"]:
		doc_details = frappe.get_doc(transaction_type,reference_name)
		if doc_details.docstatus == 1:
			return True
		else:
			return False
	else:
		return True