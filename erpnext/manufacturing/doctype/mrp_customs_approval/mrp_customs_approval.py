# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.utils import cint, cstr, flt
from frappe.model.document import Document

class MRPCustomsApproval(Document):
	def validate(self):
		op_list = frappe.get_list('Operating Cost Type', fields=["name", "default_percent"], ignore_permissions=True,order_by='sort_order')
		
		self.summary = self.create_condensed_table(op_list)
	
	
	def create_condensed_table(self,operations):
		
		dict = self.items
		title = self.title		
		
		summary = ""		
		joiningtext = """<table class="table table-bordered table-condensed" style="text-align:center">"""
		joiningtext += """<thead>
				<tr>
					<th>Sr</th>
					<th class="text-center">Item Name</th>
					<th class="text-center">Qty</th>
					<th class="text-center" colspan='2'>Raw Material</th>"""
		
		if len(operations)>0:			
			joiningtext += """<th class="text-center" colspan='"""+str(len(operations))+"""'>Production Overheads</th>"""

					
		joiningtext += """<th class="text-center">Mfg cost</th>
					<th class="text-center">Ex</th>
					<th class="text-center">Selling price</th>
				</tr>
				<tr style>
					<th class="text-center" colspan='3'>""" + str(title) + """</th>
					<th class="text-center">Dutible</th>
					<th class="text-center">Non Dutible</th>"""
		
		for op in operations:
			joiningtext += """<th class="text-center">"""+str(op.name)+"""</th>"""
		
		joiningtext += """<th></th>
					<th class="text-center">-factory price</th>
					<th class="text-center">For Customs Purpose</th>
				</tr></thead><tbody>"""	
		
		for i, d in enumerate(dict):
			joiningtext += """<tr>
						<td>""" + str(i+1) + """</td>
						<td>""" + str(d.item_name) + """</td>
						<td>""" + str(1) +"""</td>
						<td>""" + str(round(flt(d.dutible),2)) +"""</td>
						<td>""" + str(round(flt(d.non_dutible),2)) + """</td>"""
			
			mrp_operating_costs = []
			if d.data:
				mrp_operating_costs = json.loads(d.data)
			
			mfg_cost = 0.0
			for op in operations:
				value = 0.0
				
				if d.force_use_default_production_overhead:
					value = flt(op.default_percent)/100 * (d.dutible+d.non_dutible)
				else:
					mrp_data = filter(lambda oc: oc['type'] == op.name, mrp_operating_costs)
					if mrp_data and len(mrp_data)>0:
						value = mrp_data[0]['amount'] or 0
					
				mfg_cost += value
				
				joiningtext += """<td>""" + str(round(flt(value),2))+"""</td>"""
			
			ex_factory_price = d.ex_factory_price
			customs_price = d.customs_price
			
			if not d.force_use_default_production_overhead:
				mfg_cost = ex_factory_price - d.dutible - d.non_dutible
			else:
				ex_factory_price = mfg_cost + d.dutible + d.non_dutible
				customs_price = (ex_factory_price * d.non_duty_percent/100)+d.dutible

			joiningtext += """<td>""" + str(round(flt(mfg_cost or 0),2))+"""</td>
						<td>""" + str(round(flt(ex_factory_price or 0),2))+"""</td>
						<td>""" + str(round(flt(customs_price or 0),2))+"""</td>
						</tr>"""
		joiningtext += """</tbody></table>"""
		summary += joiningtext
		return summary
