# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, flt, cint,nowtime, nowdate, add_days, comma_and, getdate,get_link_to_form
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
			if not fg_item.uom:
				frappe.throw(_("Item {0} has missing uom").format(fg_item.item_code))	
			
			if fg_item.bom:
			
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
					
				
				uses_builder = False
				if bom.get("bomitems"):
					uses_builder = True
					updated_builder_items = calculate_builder_items_dimensions(bom.get("bomitems"),fg_item.depth,fg_item.depthunit,fg_item.width,fg_item.widthunit,fg_item.height,fg_item.heightunit)
					merged,summary,unmerged = build_bom_ext(updated_builder_items,qty,depthOriginal,widthOriginal,heightOriginal)
				elif bom.get("exploded_items"):
					merged,summary,unmerged = get_material_list(bom.get("exploded_items"),qty,bom.quantity)
					
				
				fg_merged_items,fg_raw_material_cost = self.update_bom_builder(merged)
				fg_summary = create_condensed_table_exploded_items(fg_merged_items,self.company)	
				
				final_per_item_summary = final_per_item_summary + '<br>' + get_link_to_form("Item", fg_item.item_code) + ' @ ' + str(fg_item.qty) + ' ' + str(fg_item.uom) + ' With BOM: ' + get_link_to_form("BOM", fg_item.bom) + '<br>' + fg_summary
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
				<th>Required Stock Qty</th>
				<th>Stock UOM</th>
			</tr></thead><tbody>"""
				
	from erpnext.stock.doctype.stock_entry.stock_entry import get_warehouses_and_stock
	from erpnext.stock.doctype.mrp_import_bill.mrp_import_bill import get_bills_and_stock
	from frappe.utils import get_link_to_form


	for i, d in enumerate(items):
		item_code = get_link_to_form("Item", d.item_code)
		warehouse_summary = ""
		warehouses_details = get_warehouses_and_stock(d.item_code,company)
		if len(warehouses_details) == 0:
			warehouse_summary = "0"
		else:
			for warehouse_det in warehouses_details:
				style = ''
				if warehouse_det.actual_qty <= 0:
					style = 'font-size:larger; color:red; font-weight:bold;'
				warehouse_summary = warehouse_summary + '<div'+' style="'+ style + '">' + str(warehouse_det.warehouse) + ': ' + str(warehouse_det.actual_qty) + '</div>'
				
		# import_bill_summary = ""
		# import_bill_details = get_bills_and_stock(d.item_code,company)
		# if len(import_bill_details) == 0:
			# import_bill_summary = "0"
		# else:
			# for key in import_bill_details:
				# d = import_bill_details[key]
				# import_bill_summary = import_bill_summary + '<div>' + str(d.import_bill) + ': ' + str(d.stock_qty) + '</div>'
				
		joiningtext += """<tr>
					<td>""" + str(item_code) +"""</td>
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
	
