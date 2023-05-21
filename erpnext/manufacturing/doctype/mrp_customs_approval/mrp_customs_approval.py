# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.utils import cint, cstr, flt
from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import validate_bom_no, get_default_bom, get_material_list
from operator import itemgetter

class MRPCustomsApproval(Document):
	def validate(self):
		# self.update_approval()
		self.update_cost_sheet()
	
	@frappe.whitelist()
	def update_approval(self):
		self.summary = self.create_condensed_table(self.items)
		
	@frappe.whitelist()
	def update_cost_sheet(self):
		self.cost_summary = self.create_condensed_table_cost(self.exploded)
		
	@frappe.whitelist()
	def get_exploded_items(self, reset_exploded = True):
		self.cur_exploded_items = {}

		final_unmerged_items =[]
		for i, item in enumerate(self.items):
			merged = []
			unmerged = []
			summary = ''
		
			if item.bom:
				bom = frappe.get_doc("BOM", item.bom)
				mrp_operating_costs = bom.get("mrp_operating_costs")
				total_overheads_pct = 0
				for oc in mrp_operating_costs:
					total_overheads_pct += oc.percent
				
				
				exploded_items = bom.get("exploded_items")
				qty = item.qty
				for d in exploded_items:
					self.add_to_cur_exploded_items(
						frappe._dict(
							{
								"item_code": d.item_code,
								"stock_uom": d.stock_uom,
								"stock_qty": flt(d.stock_qty)*qty,
								"uom": d.required_uom,
								"qty": flt(d.required_qty)*qty,
								"dutible": d.dutible,
								"amount": d.amount*qty,
								"total_overheads_pct": total_overheads_pct,
								"remarks": d.item_code,
							}
						)
					)
					
		self.required_materials = self.create_condensed_materials_summary()
		
		if reset_exploded:
			self.add_exploded_items()
			
		self.update_cost_sheet()
	
	def add_to_cur_exploded_items(self, args):
		key = (args.item_code)
		if key in self.cur_exploded_items:
			self.cur_exploded_items[key]["stock_qty"] += args.stock_qty
			self.cur_exploded_items[key]["qty"] += args.qty
			self.cur_exploded_items[key]["amount"] += args.amount
		else:
			self.cur_exploded_items[key] = args
			
	def add_exploded_items(self):
		self.set("exploded", [])
		
		for d in sorted(self.cur_exploded_items, key=itemgetter(0)):
			ch = self.append("exploded", {})
			for i in self.cur_exploded_items[d].keys():
				ch.set(i, self.cur_exploded_items[d][i])
	
	def create_condensed_table(self,items):
		title = self.title		
		operations = frappe.get_list('Operating Cost Type', fields=["name", "default_percent"],filters={"default_cost": 1}, ignore_permissions=True,order_by='sort_order')

		summary = ""		
		joiningtext = """<table class="table table-bordered table-condensed" style="text-align:center">"""
		joiningtext += """<thead>
				<tr>
					<th>Sr</th>
					<th class="text-center">Item Name</th>
					<th class="text-center">Qty</th>
					<th class="text-center" colspan='2'>Raw Material</th>
					<th class="text-center" colspan='1'>Overheads Pct</th>
					"""
		
		# if len(operations)>0:			
			# joiningtext += """<th class="text-center" colspan='"""+str(len(operations))+"""'>Production Overheads</th>"""

					
		joiningtext += """<th class="text-center">Mfg cost</th>
					<th class="text-center">Ex</th>
					<th class="text-center">Selling price</th>
				</tr>
				<tr style>
					<th class="text-center" colspan='3'>""" + str(title) + """</th>
					<th class="text-center">Dutiable</th>
					<th class="text-center">Non Dutiable</th>
					<th></th>
					"""
		
		# for op in operations:
			# joiningtext += """<th class="text-center">"""+str(op.name)+"""</th>"""
		
		joiningtext += """
					<th></th>
					<th class="text-center">-factory price</th>
					<th class="text-center">For Customs Purpose</th>
				</tr></thead><tbody>"""	
		
		for i, d in enumerate(items):
			if not d.bom:
				continue
			
			bom = frappe.get_doc("BOM", d.bom)
			mrp_operating_costs = bom.get("mrp_operating_costs")
			total_overheads_pct = 0.0
			ex_factory_price = bom.mrp_factory_price or 0.0
			customs_price = bom.total_duty or 0.0
			non_duty_percent = bom.non_duty_percent or 0.0
			mfg_cost = bom.mrp_total_production_overhead or 0.0
			
		
		
			dutible = bom.dutible or 0
			non_dutible = bom.non_dutible or 0
			joiningtext += """<tr>
						<td>""" + str(i+1) + """</td>
						<td>""" + str(d.item_name) + """</td>
						<td>""" + str(1) +"""</td>
						<td>""" + str(round(flt(dutible),2)) +"""</td>
						<td>""" + str(round(flt(non_dutible),2)) + """</td>"""
			
			

						
			if d.force_use_default_production_overhead:
				value = 0.0
				mfg_cost = 0.0

				for op in operations:
					total_overheads_pct += flt(op.default_percent)
					value = flt(op.default_percent)/100 * (dutible+non_dutible)
					
					# joiningtext += """<td>""" + str(round(flt(value),2))+"""</td>"""
					
					mfg_cost += value
				
				ex_factory_price = mfg_cost + dutible + non_dutible
				customs_price = (ex_factory_price * non_duty_percent/100)+dutible
	
			else:
				for oc in mrp_operating_costs:
					total_overheads_pct += oc.percent
					
					# joiningtext += """<td>""" + str(round(flt(value),2))+"""</td>"""
					
				
			joiningtext += """<td>""" + str(round(flt(total_overheads_pct),2))+"""</td>"""
			joiningtext += """<td>""" + str(round(flt(mfg_cost or 0),2))+"""</td>
						<td>""" + str(round(flt(ex_factory_price or 0),2))+"""</td>
						<td>""" + str(round(flt(customs_price or 0),2))+"""</td>
						</tr>"""
		joiningtext += """</tbody></table>"""
		summary += joiningtext
		return summary
		
	def create_condensed_table_cost(self,items):
		summary = ""		
		joiningtext = """<table class="table table-bordered table-condensed" style="text-align:center">"""
		joiningtext += """
				<thead>
				<tr>
					<th class="text-center">Duty Type</th>
					<th class="text-center">Year</th>
					<th class="text-center">Bill</th>
					<th class="text-center">Qty</th>
					<th class="text-center">UOM</th>
					<th class="text-center">Dutiable</th>
					<th class="text-center">Non Dutiable</th>
					<th class="text-center">Percent Added</th>
					<th class="text-center">Overheads/MFG cost</th>
					<th class="text-center">Activity</th>
				</tr></thead><tbody>"""	
		
		total_dutible= 0
		total_non_dutible=0
		total_overheads=0
		total_mfg_cost=0
		
		for i, d in enumerate(items):
			
			
			is_dutible = "Dutiable" if d.dutible else "LP"
			dutible = d.amount if d.dutible else 0
			non_dutible = d.amount if not d.dutible else 0
			
			overheads = d.amount*d.total_overheads_pct/100
			mfg_cost = overheads
			
			total_dutible += dutible
			total_non_dutible += non_dutible
			total_overheads += overheads
			total_mfg_cost += mfg_cost
			
			joiningtext += """<tr>
						<td>""" + str(is_dutible) + """</td>
						<td>""" + str(d.import_bill_date) +"""</td>
						<td>""" + str(d.import_bill) +"""</td>
						<td>""" + str(round(flt(d.qty),5)) +"""</td>
						<td>""" + str(d.uom) +"""</td>
						<td>""" + str(round(flt(dutible),2)) +"""</td>
						<td>""" + str(round(flt(non_dutible),2)) + """</td>
						<td>""" + str(round(flt(d.total_overheads_pct or 0),2))+"""</td>
						<td>""" + str(round(flt(overheads or 0),2))+"""</td>
						<td>""" + str(d.remarks)+"""</td>
						</tr>"""
						
		joiningtext += """<tr>
						<td></td>
						<td></td>
						<td></td>
						<td></td>
						<td></td>
						<td>""" + str(round(flt(total_dutible),2)) +"""</td>
						<td>""" + str(round(flt(total_non_dutible),2)) + """</td>
						<td></td>
						<td>""" + str(round(flt(total_overheads or 0),2))+"""</td>
						<td></td>
						</tr>"""
						
		joiningtext += """</tbody></table>"""
		summary += joiningtext
		return summary

	def create_condensed_materials_summary(self):
		summary = ""		
		joiningtext = """<table class="table table-bordered table-condensed" style="text-align:center">"""
		joiningtext += """
				<thead>
				<tr>
					<th class="text-center">Duty Type</th>
					<th class="text-center">Item</th>
					<th class="text-center">Qty</th>
					<th class="text-center">UOM</th>
					<th class="text-center">Dutiable</th>
					<th class="text-center">Non Dutiable</th>
					<th class="text-center">Percent Added</th>
					<th class="text-center">Overheads/MFG cost</th>
				</tr></thead><tbody>"""	
		
		total_dutible= 0
		total_non_dutible=0
		total_overheads=0
		total_mfg_cost=0
		
		for k in sorted(self.cur_exploded_items, key=itemgetter(0)):
			d = self.cur_exploded_items[k]
				
				
			is_dutible = "Dutiable" if d.dutible else "LP"
			dutible = d.amount if d.dutible else 0
			non_dutible = d.amount if not d.dutible else 0
			
			overheads = d.amount*d.total_overheads_pct/100
			mfg_cost = overheads
			
			total_dutible += dutible
			total_non_dutible += non_dutible
			total_overheads += overheads
			total_mfg_cost += mfg_cost
			
			joiningtext += """<tr>
						<td>""" + str(is_dutible) + """</td>
						<td>""" + str(d.item_code) + """</td>
						<td>""" + str(round(flt(d.qty),5)) +"""</td>
						<td>""" + str(d.uom) +"""</td>
						<td>""" + str(round(flt(dutible),2)) +"""</td>
						<td>""" + str(round(flt(non_dutible),2)) + """</td>
						<td>""" + str(round(flt(d.total_overheads_pct or 0),2))+"""</td>
						<td>""" + str(round(flt(overheads or 0),2))+"""</td>
						</tr>"""
							
		joiningtext += """<tr>
						<td></td>
						<td></td>
						<td></td>
						<td></td>
						<td>""" + str(round(flt(total_dutible),2)) +"""</td>
						<td>""" + str(round(flt(total_non_dutible),2)) + """</td>
						<td></td>
						<td>""" + str(round(flt(total_overheads or 0),2))+"""</td>
						</tr>"""
						
		joiningtext += """</tbody></table>"""
		summary += joiningtext
		return summary