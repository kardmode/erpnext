# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, flt, cint,nowtime, nowdate, add_days, comma_and, getdate
from frappe import msgprint, _

from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import validate_bom_no, get_default_bom
from erpnext.manufacturing.doctype.production_order.production_order import get_item_details
from erpnext.stock.get_item_details import get_conversion_factor_between_two_units,get_conversion_factor
from operator import itemgetter

from frappe.desk import query_report

class CustomProductionOrder(Document):
	def validate(self):
		if not self.per_item_summary:
			self.per_item_summary = "No per item summary"
		self.get_stock_entries()
		

	def get_items_from_dn(self):
		self.items = []
		if self.reference_doctype == "Delivery Note":
			dn = frappe.get_doc("Delivery Note", self.reference_name)
			for item in dn.get("items"):
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
				
				ch.bom = get_default_bom(item.item_code)
				
	def get_stock_entries(self):
		stock_entries = frappe.db.sql("""select name,docstatus,posting_date,title from `tabStock Entry` where custom_production_order=%s""", self.name, as_dict = 1)
		summary = 'No stock entries for this production order' 
		
		
		if not stock_entries:
			self.summary = summary
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
		self.summary = summary
		return summary
		
						
	def get_summary(self):
		final_items =[]
		final_summary = ""
		
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
				
				
				if bom.get("bomitems"):
					from erpnext.manufacturing.doctype.bom.bom import calculate_builder_items_dimensions, build_bom_ext
					updated_builder_items = calculate_builder_items_dimensions(bom.get("bomitems"),fg_item.depth,fg_item.depthunit,fg_item.width,fg_item.widthunit,fg_item.height,fg_item.heightunit)
					merged,summary,unmerged = build_bom_ext(updated_builder_items,qty)
				elif bom.get("items"):
					from erpnext.manufacturing.doctype.bom.bom import get_material_list
					qtyOriginal = bom.quantity
					merged,summary,unmerged = get_material_list(bom.get("items"),qty,qtyOriginal)
					
				final_items = final_items + unmerged
				
				
				
				fg_merged_items,fg_raw_material_cost = self.update_bom_builder(merged)
				fg_summary = create_condensed_table_exploded_items(fg_merged_items,self.company)
				
				final_summary = final_summary + '<br>' + str(fg_item.item_code) + ' ' + str(fg_item.qty) + ' ' + str(fg_item.uom) + '<br>' + fg_summary
		
		
		
		

		final_merged_items,raw_material_cost = self.update_bom_builder(merge_bom_items(final_items))
		
		
		self.get_exploded_items(final_merged_items)
		self.add_exploded_items()
		self.per_item_summary = final_summary
		
		
		
		if len(final_merged_items) > 0:
			return True
		else:
			return False
	
	
	def update_bom_builder(self,merged):
		items = []
		raw_material_cost = 0

		for item in sorted(merged):
			
			d = merged[item]
			# bom_no = get_default_bom(d["item_code"])
			ret_item = get_item_det(d["item_code"])
			
			
			
			d["stock_qty"] = d["qty"]
			# d["qty"] = flt(d["required_qty"])
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
					

			d["rate"] = rate
			d["base_rate"] = rate
			
			d["stock_uom"] = ret_item.stock_uom
			d["amount"] = flt(d["rate"])*flt(d["stock_qty"])
			d["uom"] = d["required_uom"]
			d["source_warehouse"] = ''
			# d["conversion_factor"] = ret_item["conversion_factor"]
			
			d["item_name"] = ret_item.item_name
			d["description"] = ret_item.description
			d["image"] = ret_item.image
			
			raw_material_cost = raw_material_cost + flt(d["rate"])

			items.append(frappe._dict(d))
			
		
		return items, raw_material_cost
	
		
	def get_exploded_items(self,items):
		""" Get all raw materials including items from child bom"""
		self.cur_exploded_items = {}
		for d in items:
			if d.bom_no:
				self.get_child_exploded_items(d.bom_no, d.stock_qty)
			else:
				self.add_to_cur_exploded_items(frappe._dict({
					'item_code'		: d.item_code,
					'item_name'		: d.item_name,
					'source_warehouse': d.source_warehouse,
					'description'	: d.description,
					'image'			: d.image,
					'stock_uom'		: d.stock_uom,
					'stock_qty'		: flt(d.stock_qty),
					'rate'			: d.base_rate,
					'required_uom'		: d.required_uom,
					'required_qty'		: flt(d.required_qty),
				}))
		
				
	def add_to_cur_exploded_items(self, args):
		if self.cur_exploded_items.get(args.item_code):
			self.cur_exploded_items[args.item_code]["stock_qty"] += args.stock_qty
			self.cur_exploded_items[args.item_code]["required_qty"] += args.required_qty
		else:
			self.cur_exploded_items[args.item_code] = args

	def get_child_exploded_items(self, bom_no, stock_qty):
		""" Add all items from Flat BOM of child BOM"""
		# Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
		child_fb_items = frappe.db.sql("""select bom_item.item_code, bom_item.item_name,
			bom_item.description, bom_item.source_warehouse,
			bom_item.stock_uom, bom_item.stock_qty, bom_item.rate,
			bom_item.stock_qty / ifnull(bom.quantity, 1) as qty_consumed_per_unit
			from `tabBOM Explosion Item` bom_item, tabBOM bom
			where bom_item.parent = bom.name and bom.name = %s and bom.docstatus = 1""", bom_no, as_dict = 1)

		for d in child_fb_items:
			self.add_to_cur_exploded_items(frappe._dict({
				'item_code'				: d['item_code'],
				'item_name'				: d['item_name'],
				'source_warehouse'		: d['source_warehouse'],
				'description'			: d['description'],
				'stock_uom'				: d['stock_uom'],
				'stock_qty'				: d['qty_consumed_per_unit'] * stock_qty,
				'rate'					: flt(d['rate']),
				'required_uom'		: d['stock_uom'],
				'required_qty'		: d['qty_consumed_per_unit'] * stock_qty,
			}))

	def add_exploded_items(self):
		exploded_items = {}
		for d in self.get('exploded_items'):
			exploded_items[d.item_code] = d
			
		self.set('exploded_items', [])

		from erpnext.stock.doctype.stock_entry.stock_entry import get_best_warehouse
		from erpnext.stock.stock_ledger import get_previous_sle
		posting_date = nowdate()
		posting_time = nowtime()
		
		
		for d in sorted(self.cur_exploded_items, key=itemgetter(0)):
			
			ch = self.append('exploded_items', {})
			for i in self.cur_exploded_items[d].keys():
				ch.set(i, self.cur_exploded_items[d][i])
			
			best_warehouse,enough_stock = get_best_warehouse(ch.item_code,ch.stock_qty,company = self.company)
			if best_warehouse:
				ch.actual_qty = get_previous_sle({
									"item_code": ch.item_code,
									"warehouse": best_warehouse,
									"posting_date": posting_date,
									"posting_time": posting_time
								}).get("qty_after_transaction") or 0
				
				
			else:
				ch.actual_qty = 0
			
			ch.source_warehouse = best_warehouse
			ch.amount = flt(ch.stock_qty) * flt(ch.rate)
			ch.qty_consumed_per_unit = flt(ch.stock_qty)
			if exploded_items.get(ch.item_code):
				ch.dutible = exploded_items[ch.item_code].dutible
		
				
	def make_stock_entries(self):
	
		from erpnext.stock.stock_ledger import NegativeStockError
		from erpnext.stock.doctype.stock_entry.stock_entry import IncorrectValuationRateError, \
			DuplicateEntryForProductionOrderError, OperationsNotCompleteError, get_best_warehouse
		
		
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
				
				stock_entry.posting_date = nowdate()
				stock_entry.posting_time = nowtime()
				
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
					
				if bom.get("bomitems"):
					from erpnext.manufacturing.doctype.bom.bom import calculate_builder_items_dimensions, build_bom_ext
					updated_builder_items = calculate_builder_items_dimensions(bom.get("bomitems"),fg_item.depth,fg_item.depthunit,fg_item.width,fg_item.widthunit,fg_item.height,fg_item.heightunit)
					merged,summary,unmerged = build_bom_ext(updated_builder_items,qty)
				elif bom.get("items"):
					from erpnext.manufacturing.doctype.bom.bom import get_material_list
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
			
		
			except (NegativeStockError, IncorrectValuationRateError, DuplicateEntryForProductionOrderError,
				OperationsNotCompleteError,OperationsNotCompleteError):
				frappe.db.rollback()
			except Exception as error:
				frappe.db.rollback()
				
		if len(stock_entry_list) > 0:
			return True
		else:
			return False
			
	def submit_entries(self):
	
		stock_entries = frappe.db.sql("""select name from `tabStock Entry` where custom_production_order=%s and docstatus < 1""", self.name, as_dict = 1)
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
def get_item_det(item_code):
	item = frappe.db.sql("""select name,depth,depthunit,width,widthunit,height,heightunit, item_name, docstatus, description, image,
		is_sub_contracted_item, stock_uom, default_bom, last_purchase_rate
		from `tabItem` where name=%s""", item_code, as_dict = 1)

	if not item:
		frappe.throw(_("Item: {0} does not exist in the system").format(item_code))
	

	return item[0]

	
def create_condensed_table(items):
	summary = ""
	
	joiningtext = """<table class="table table-bordered table-condensed">"""
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
	

	for i, d in enumerate(items):
		
		warehouse_summary = ""
		warehouses_details = get_warehouses_and_stock(d.item_code,company)
		if len(warehouses_details) == 0:
			warehouse_summary = "0"
		else:
			for warehouse_det in warehouses_details:
				warehouse_summary = warehouse_summary + '<div>' + str(warehouse_det.warehouse) + ': ' + str(warehouse_det.actual_qty) + '</div>'
				
		
		joiningtext += """<tr>
					<td>""" + str(d.item_code) +"""</td>
					<td>""" + str(warehouse_summary) +"""</td>
					<td>""" + str(d.stock_qty) +"""</td>
					<td>""" + str(d.stock_uom) +"""</td>
					</tr>"""
	joiningtext += """</tbody></table>"""
	summary += joiningtext
	return summary
	
