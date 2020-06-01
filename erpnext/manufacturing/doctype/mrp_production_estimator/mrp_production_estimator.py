# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, flt, cint,nowtime, nowdate, add_days, comma_and, getdate
from frappe import msgprint, _
from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import validate_bom_no, get_default_bom, get_material_list, \
	calculate_builder_items_dimensions, build_bom_ext,convert_units
from erpnext.selling.doctype.product_bundle.product_bundle import has_product_bundle
from erpnext.stock.doctype.packed_item.packed_item import get_product_bundle_items

from erpnext.stock.doctype.stock_entry.stock_entry import IncorrectValuationRateError, \
	DuplicateEntryForWorkOrderError, OperationsNotCompleteError, get_best_warehouse
from erpnext.stock.get_item_details import get_conversion_factor_between_two_units,get_conversion_factor
from operator import itemgetter

from frappe.desk import query_report

class MRPProductionEstimator(Document):
	def validate(self):
		self.get_summary()
		
		if not self.per_item_summary:
			self.per_item_summary = "No per item summary"
		
	def get_items_from(self,reference_doctype,reference_name):
		self.items = []
		dn = frappe.get_doc(reference_doctype, reference_name)
		
		self.project = dn.get("project")
			
		item_list = []
		for item in dn.get("items"):
			product_bundle = has_product_bundle(item.item_code,self.project)
			if product_bundle:
				if dn.has_key("packed_items"):
					for p in dn.get("packed_items"):
						if p.parent_detail_docname == item.name and p.parent_item == item.item_code:
							item_list.append(p)
				else:
					for i in get_product_bundle_items(item.item_code,self.project):
						i.qty = i.qty * item.qty
						item_list.append(i)
			else:
				item_list.append(item)

		
		for item in item_list:
			if item.item_code:
				ch = self.append('items', {})
				ch.item_code = item.item_code
				ch.qty = item.qty
				ch.uom = item.uom
				
				item_dict = get_item_det(item.item_code)
				ch.depth = item_dict.depth
				ch.depthunit = item_dict.depthunit
				ch.width = item_dict.width
				ch.widthunit = item_dict.widthunit
				ch.height = item_dict.height
				ch.heightunit = item_dict.heightunit

				ch.bom = item.get('bom_no') or get_default_bom(item.item_code, self.project) or None
				
	def get_stock_entries(self):
		stock_entries = frappe.db.sql("""select name,docstatus,posting_date,title from `tabStock Entry` where custom_production_order=%s""", self.name, as_dict = 1)
		summary = 'No stock entries for this production order' 
		
		if not stock_entries:
			return summary
		
		summary = ''
		items = []
		for se in stock_entries:
			dict = {}
			button = '<button id="' + str(se.name) + '" class="btn btn-primary btn-sm"><i class="visible-xs octicon octicon-check"></i><span class="hidden-xs">Submit</span></button>'
			status = "Draft"
			if se.docstatus == 1:
				status = "Submitted"
				button = ""
			elif se.docstatus == 2:
				status = "Cancelled"
				button = ""
				
			
			button = ""
			link = '<a href="#Form/Stock Entry/{0}">{0}</a><br>'.format(se.name)
			summary = summary + link
			
			dict['status'] = status
			dict['link'] = link
			dict['title'] = se.title
			dict['posting_date'] = se.posting_date
			dict['button'] = button
			items.append(dict)
		
		summary = create_condensed_table(items)
		return summary
		
						
	def get_summary(self,should_save = False):
		final_unmerged_items =[]
		final_per_item_summary = ""
		
		from erpnext.manufacturing.doctype.bom.bom import merge_bom_items
		
		for fg_item in self.get("items"):
			merged = []
			unmerged = []
			summary = ''

			if not fg_item.depth and not fg_item.width and not fg_item.height:
				frappe.throw(_("Item {0} needs all dimensions").format(fg_item.item_code))
			
			if not fg_item.bom:
				frappe.throw(_("Item {0} has missing bom").format(fg_item.item_code))
			elif not fg_item.uom:
				frappe.throw(_("Item {0} has missing uom").format(fg_item.item_code))	
			elif fg_item.bom:
			
				bom = frappe.get_doc("BOM", fg_item.bom)
				
				if not bom:
					frappe.throw(_("BOM {0} not found").format(fg_item.bom))
					
				if fg_item.uom == bom.uom:
					qty = fg_item.qty
				else:
					conversion_factor = get_conversion_factor_between_two_units(fg_item.item_code,fg_item.uom, bom.uom).get("conversion_factor")
				
					if not conversion_factor:
						conversion_factor = 1
						frappe.msgprint(_("Item {0} has no conversion factor for {1}").format(fg_item.item_code, bom.uom))
				
				
					qty = flt(fg_item.qty) * flt(conversion_factor)
				
				depthOriginal = convert_units(fg_item.depthunit,fg_item.depth)
				widthOriginal = convert_units(fg_item.widthunit,fg_item.width)
				heightOriginal = convert_units(fg_item.heightunit,fg_item.height)
					
				
				if bom.get("bomitems"):
					updated_builder_items = calculate_builder_items_dimensions(bom.get("bomitems"),fg_item.depth,fg_item.depthunit,fg_item.width,fg_item.widthunit,fg_item.height,fg_item.heightunit)
					merged,summary,unmerged = build_bom_ext(updated_builder_items,qty,depthOriginal,widthOriginal,heightOriginal)
				elif bom.get("items"):
					qtyOriginal = bom.quantity
					merged,summary,unmerged = get_material_list(bom.get("items"),qty,qtyOriginal)
					
				
				fg_merged_items,fg_raw_material_cost = self.update_bom_builder(merged)
				fg_summary = create_condensed_table_exploded_items(fg_merged_items,self.company)	
				
				final_per_item_summary = final_per_item_summary + '<br>' + str(fg_item.item_code) + ' @ ' + str(fg_item.qty) + ' ' + str(fg_item.uom) + '<br>' + fg_summary
				final_unmerged_items = final_unmerged_items + unmerged
		
		
		
		
		final_merged_items,raw_material_cost = self.update_bom_builder(merge_bom_items(final_unmerged_items))
		self.combined_summary = create_condensed_table_exploded_items(final_merged_items,self.company)
		self.per_item_summary = final_per_item_summary
		
		if should_save:
			self.save()
		
		if len(final_merged_items) > 0:
			return "True"
		else:
			return "False"
	
	
	def update_bom_builder(self,merged):
		items = []
		raw_material_cost = 0

		for item in sorted(merged):
			
			d = merged[item]
			
			# bom_no = get_default_bom(d["item_code"])
			ret_item = get_item_det(d["item_code"])
			d["bom_no"] = ret_item.default_bom
			
			rate = 0.0
			buying_price_list = frappe.db.get_value("Buying Settings", None, "buying_price_list")
			if buying_price_list:
				rate = frappe.db.get_value("Item Price", {"price_list": buying_price_list,
					"item_code": d["item_code"]}, "price_list_rate") or 0.0
	
				if rate == 0.0:
					rate = ret_item.last_purchase_rate or 0.0
					if rate == 0.0:
						from erpnext.manufacturing.doctype.bom.bom import get_valuation_rate
						rate = get_valuation_rate({"item_code": d["item_code"], "bom_no": d["bom_no"]})
					
			# d["stock_uom"] = d.stock_uom
			# d["uom"] = d.uom
			d["rate"] = rate
			d["base_rate"] = rate
			d["amount"] = flt(d["rate"])*flt(d["stock_qty"])
			d["source_warehouse"] = ''
			# d["conversion_factor"] = ret_item["conversion_factor"]
			
			d["item_name"] = ret_item.item_name
			d["description"] = ret_item.description
			
			raw_material_cost = raw_material_cost + flt(d["rate"])

			items.append(frappe._dict(d))
			
		
		return items, raw_material_cost
	
				
	def make_stock_entries(self):
	
		from erpnext.stock.stock_ledger import NegativeStockError

		
		
		stock_entry_list = []	
		items = self.get("items")
		if not items:
			return False
		
		for fg_item in items:
		
			prev_stock_entry = frappe.db.sql("""select name,docstatus from `tabStock Entry` where custom_production_order=%s and manufactured_item=%s and docstatus < 2""", (self.name,fg_item.item_code), as_dict = 1)
			if prev_stock_entry:
				break
			
			if not fg_item.depth or not fg_item.width or not fg_item.height:
				frappe.throw(_("Item {0} needs all dimensions").format(fg_item.item_code))
				
			if not fg_item.bom:
					frappe.throw(_("Item {0} has missing bom").format(fg_item.item_code))
			elif fg_item.bom:
				bom = frappe.get_doc("BOM", fg_item.bom)
				
			from erpnext.stock.utils import get_default_warehouse
			default_warehouses = get_default_warehouse(company = self.company)
		
			try:	
				stock_entry = frappe.new_doc("Stock Entry")
				stock_entry.purpose = "Manufacture"
				# stock_entry.sales_order = sales_order_no
				
				if self.reference_doctype == "Delivery Note":
					stock_entry.delivery_note_no = self.reference_name
				
				stock_entry.project = self.project
				stock_entry.company = self.company
				stock_entry.custom_production_order = self.name
				stock_entry.from_bom = 0
				stock_entry.use_multi_level_bom = 0
				stock_entry.manufactured_item = fg_item.item_code
				stock_entry.remarks = self.remarks
				
				stock_entry.posting_date = self.posting_date
				stock_entry.posting_time = self.posting_time or nowtime()
				
				conversion_factor = get_conversion_factor(fg_item.item_code,fg_item.uom).get("conversion_factor")
				if not conversion_factor:
					conversion_factor = 1
				
				stock_entry.fg_completed_qty = flt(fg_item.qty) * flt(conversion_factor)
				
				stock_entry.from_warehouse = default_warehouses.get("source_warehouse")
				stock_entry.to_warehouse = default_warehouses.get("fg_warehouse")
				stock_entry.title = 'Manufacture {0}'.format(fg_item.item_code)
					
				if fg_item.uom == bom.uom:
					qty = fg_item.qty
				else:
					conversion_factor = get_conversion_factor_between_two_units(fg_item.item_code,fg_item.uom, bom.uom).get("conversion_factor")
			
					if not conversion_factor:
						conversion_factor = 1
						frappe.msgprint(_("Item {0} has no conversion factor for {1}").format(fg_item.item_code, bom.uom))
			
			
					qty = flt(fg_item.qty) * flt(conversion_factor)
				
				depthOriginal = convert_units(fg_item.depthunit,fg_item.depth)
				widthOriginal = convert_units(fg_item.widthunit,fg_item.width)
				heightOriginal = convert_units(fg_item.heightunit,fg_item.height)
					
					
				if bom.get("bomitems"):
					updated_builder_items = calculate_builder_items_dimensions(bom.get("bomitems"),fg_item.depth,fg_item.depthunit,fg_item.width,fg_item.widthunit,fg_item.height,fg_item.heightunit)
					merged,summary,unmerged = build_bom_ext(updated_builder_items,qty,depthOriginal,widthOriginal,heightOriginal)

				elif bom.get("items"):
					
					qtyOriginal = bom.quantity
					merged,summary,unmerged = get_material_list(bom.get("items"),qty,qtyOriginal)
				else:
					raise Exception('Represents a hidden bug, do not catch this')
					
				exploded_items,raw_material_cost = self.update_bom_builder(merged)		
				
				for item in exploded_items:
					
					# item = frappe._dict(item)
					best_warehouse,enough_stock = get_best_warehouse(item.item_code,item.stock_qty,stock_entry.from_warehouse,company = stock_entry.company)
					stock_entry.add_to_stock_entry_detail({
						item.item_code: {
							"to_warehouse": "",
							"from_warehouse": best_warehouse,
							"qty": item.stock_qty,
							"item_name": item.item_name,
							"description": item.description,
							"stock_uom": item.stock_uom,
							"expense_account": None,
							"cost_center": None
						}
					})
	
				item_dict = get_item_det(fg_item.item_code)
				
				stock_entry.add_to_stock_entry_detail({
					fg_item.item_code: {
						"to_warehouse": stock_entry.to_warehouse,
						"from_warehouse": "",
						"qty": qty,
						"item_name": item_dict['item_name'],
						"description": item_dict['description'],
						"stock_uom": item_dict['stock_uom'],
						"expense_account": None,
						"cost_center": None,
						"basic_rate" : raw_material_cost
					}
				})
				

				# additional_costs = []
				# if purpose=="Manufacture" and add_operating_costs:
					
					# additional_costs.append({
						# "description": "Operating Cost as per Production Order / BOM",
						# "amount": self.operating_cost * flt(qty)
					# })
					
					# stock_entry.set("additional_costs", additional_costs)	
			

				stock_entry.get_stock_and_rate()
				# stock_entry.get_items()
				stock_entry.insert()
				frappe.db.commit()
			
				# if submit:
					# stock_entry.submit()
				link = ['<a href="#Form/Stock Entry/{0}">{0}</a>'.format(stock_entry.name)]
				stock_entry_list.append(link)
			
		
			except (NegativeStockError, IncorrectValuationRateError, DuplicateEntryForWorkOrderError,
				OperationsNotCompleteError,OperationsNotCompleteError):
				frappe.db.rollback()
			except Exception as error:
				frappe.db.rollback()
				
		if len(stock_entry_list) > 0:
			return True
		else:
			return False
			
	def submit_entries(self):
	
		items = self.get("items")
		if not items:
			return False
		
		for fg_item in items:
			stock_entries = frappe.db.sql("""select name from `tabStock Entry` where custom_production_order=%s and manufactured_item=%s and docstatus < 1""",  (self.name,fg_item.item_code), as_dict = 1)
			success = False
			
			for se in stock_entries:
				se_doc = frappe.get_doc("Stock Entry", se.name)
				if se_doc:
					try:
						se_doc.submit()
						success = True
					except:
						pass
		return success
		
	def delete_entries(self,delete_submitted =False,delete_draft = True):
		success = False
		if delete_draft and delete_submitted:
			condition = "docstatus < 2"
		elif delete_draft:
			condition = "docstatus = 0"
		elif delete_submitted:
			condition = "docstatus = 1"
		else:
			return success
			
		stock_entries = frappe.db.sql("""select name,docstatus from `tabStock Entry` where custom_production_order='%s' and %s""" %(self.name,condition), as_dict = 1)
		
		for se in stock_entries:
			se_doc = frappe.get_doc("Stock Entry", se.name)
			if se_doc:
				if se.docstatus == 1:
					try:	
						se_doc.cancel()
					except:
						pass
				try:
					frappe.delete_doc('Stock Entry', se.name)
					
					success = True
				except:
					pass
				
		return success

@frappe.whitelist()					
def get_item_det(item_code,uom=None):
	item = frappe.db.sql("""select name,depth,depthunit,width,widthunit,height,heightunit, item_name, docstatus, description, image,
		is_sub_contracted_item, stock_uom, default_bom, last_purchase_rate
		from `tabItem` where name=%s""", item_code, as_dict = 1)
	
	if not item:
		frappe.throw(_("Item: {0} does not exist in the system").format(item_code))
	
	details = item[0]
	details.uom = uom or details.stock_uom
	if uom:
		details.update(get_conversion_factor(item_code, uom))

	# from erpnext.stock.get_item_details import get_item_price
	
	# args = frappe._dict({"item_code":item_code,"price_list":"Buying","uom",details.uom})

	# details.price_list_rate = get_item_price(args, item_code)
	return details

	
def create_condensed_table(items):
	summary = ""
	
	joiningtext = """<table class="small table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>
				<th>Stock Entry</th>
				<th>Status</th>
				<th>Date</th>
				<th>Description</th>
				<th></th>
				</tr></thead><tbody>"""
				
	from frappe.utils import formatdate

	for i, d in enumerate(items):
		
		
		joiningtext += """<tr>
					<td>""" + str(d["link"]) +"""</td>
					<td>""" + str(d["status"]) +"""</td>
					<td>""" + formatdate(d["posting_date"]) +"""</td>
					<td>""" + str(d["title"]) +"""</td>
					<td>""" + str(d["button"]) +"""</td>
					</tr>"""
	joiningtext += """</tbody></table>"""
	summary += joiningtext
	return summary
	
def create_condensed_table_exploded_items(items,company):
	summary = ""
	
	joiningtext = """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>
				<th>Item Code</th>
				<th>Available Qty</th>
				<th>Stock Qty</th>
				<th>Stock UOM</th>
			</tr></thead><tbody>"""
				
	from erpnext.stock.doctype.stock_entry.stock_entry import get_warehouses_and_stock
	from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_bills_and_stock
	

	for i, d in enumerate(items):
		
		warehouse_summary = ""
		warehouses_details = get_warehouses_and_stock(d.item_code,company)
		if len(warehouses_details) == 0:
			warehouse_summary = "0"
		else:
			for warehouse_det in warehouses_details:
				warehouse_summary = warehouse_summary + '<div>' + str(warehouse_det.warehouse) + ': ' + str(warehouse_det.actual_qty) + '</div>'
				
		# import_bill_summary = ""
		# import_bill_details = get_bills_and_stock(d.item_code,company)
		# if len(import_bill_details) == 0:
			# import_bill_summary = "0"
		# else:
			# for key in import_bill_details:
				# d = import_bill_details[key]
				# import_bill_summary = import_bill_summary + '<div>' + str(d.import_bill) + ': ' + str(d.stock_qty) + '</div>'
				
		joiningtext += """<tr>
					<td>""" + str(d.item_code) +"""</td>
					<td>""" + str(warehouse_summary) +"""</td>
					<td>""" + str(d.stock_qty) +"""</td>
					<td>""" + str(d.stock_uom) +"""</td>
					</tr>"""
	joiningtext += """</tbody></table>"""
	summary += joiningtext
	return summary
	
	
def create_condensed_table_exploded_items_with_price(items,company):
	summary = ""
	
	joiningtext = """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>
				<th>Item Code</th>
				<th>Available Qty</th>
				<th>Stock Qty</th>
				<th>Stock UOM</th>
			</tr></thead><tbody>"""
				
	from erpnext.stock.doctype.stock_entry.stock_entry import get_warehouses_and_stock
	from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_bills_and_stock
	

	for i, d in enumerate(items):
		
		warehouse_summary = ""
		warehouses_details = get_warehouses_and_stock(d.item_code,company)
		if len(warehouses_details) == 0:
			warehouse_summary = "0"
		else:
			for warehouse_det in warehouses_details:
				warehouse_summary = warehouse_summary + '<div>' + str(warehouse_det.warehouse) + ': ' + str(warehouse_det.actual_qty) + '</div>'
				
		# import_bill_summary = ""
		# import_bill_details = get_bills_and_stock(d.item_code,company)
		# if len(import_bill_details) == 0:
			# import_bill_summary = "0"
		# else:
			# for key in import_bill_details:
				# d = import_bill_details[key]
				# import_bill_summary = import_bill_summary + '<div>' + str(d.import_bill) + ': ' + str(d.stock_qty) + '</div>'
		
		
		joiningtext += """<tr>
					<td>""" + str(d.item_code) +"""</td>
					<td>""" + str(warehouse_summary) +"""</td>
					<td>""" + str(d.stock_qty) +"""</td>
					<td>""" + str(d.stock_uom) +"""</td>
					</tr>"""
	joiningtext += """</tbody></table>"""
	summary += joiningtext
	return summary
	
