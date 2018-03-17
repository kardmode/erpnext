# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe.utils import cint, cstr, flt
from frappe import _
from erpnext.setup.utils import get_exchange_rate
from erpnext.stock.get_item_details import get_conversion_factor
from frappe.website.website_generator import WebsiteGenerator

from operator import itemgetter

form_grid_templates = {
	"items": "templates/form_grid/item_grid.html"
}

class BOM(WebsiteGenerator):
	website = frappe._dict(
		# page_title_field = "item_name",
		condition_field = "show_in_website",
		template = "templates/generators/bom.html"
	)

	def autoname(self):
		names = frappe.db.sql_list("""select name from `tabBOM` where item=%s""", self.item)

		if names:
			# name can be BOM/ITEM/001, BOM/ITEM/001-1, BOM-ITEM-001, BOM-ITEM-001-1

			# split by item
			names = [name.split(self.item)[-1][1:] for name in names]

			# split by (-) if cancelled
			names = [cint(name.split('-')[-1]) for name in names]

			idx = max(names) + 1
		else:
			idx = 1

		self.name = 'BOM-' + self.item + ('-%.3i' % idx)

	def validate(self):
		self.route = frappe.scrub(self.name).replace('_', '-')
		self.clear_operations()
		self.validate_main_item()

		self.validate_currency()
		self.set_conversion_rate()
		self.validate_uom_is_interger()
		self.update_stock_qty()
		self.set_bom_material_details()
		self.validate_materials()
		self.validate_operations()
		self.calculate_cost()

	def get_context(self, context):
		context.parents = [{'name': 'boms', 'title': _('All BOMs') }]

	def on_update(self):
		self.check_recursion()
		self.update_stock_qty()
		self.update_exploded_items()

	def on_submit(self):
		self.manage_default_bom()

	def on_cancel(self):
		frappe.db.set(self, "is_active", 0)
		frappe.db.set(self, "is_default", 0)

		# check if used in any other bom
		self.validate_bom_links()
		self.manage_default_bom()

	def on_update_after_submit(self):
		self.validate_bom_links()
		self.manage_default_bom()

	def get_item_det(self, item_code):
		item = frappe.db.sql("""select name, item_name, docstatus, description, image,
			is_sub_contracted_item, stock_uom, default_bom, last_purchase_rate
			from `tabItem` where name=%s""", item_code, as_dict = 1)

		if not item:
			frappe.throw(_("Item: {0} does not exist in the system").format(item_code))

		return item

	def validate_rm_item(self, item):
		if (item[0]['name'] in [it.item_code for it in self.items]) and item[0]['name'] == self.item:
			frappe.throw(_("BOM #{0}: Raw material cannot be same as main Item").format(self.name))

	def set_bom_material_details(self):
		for item in self.get("items"):
			self.validate_bom_currecny(item)

			ret = self.get_bom_material_detail({
				"item_code": item.item_code,
				"item_name": item.item_name,
				"bom_no": item.bom_no,
				"stock_qty": item.stock_qty
			})
			for r in ret:
				if not item.get(r):
					item.set(r, ret[r])

	def get_bom_material_detail(self, args=None):
		""" Get raw material details like uom, desc and rate"""
		if not args:
			args = frappe.form_dict.get('args')

		if isinstance(args, basestring):
			import json
			args = json.loads(args)

		item = self.get_item_det(args['item_code'])
		self.validate_rm_item(item)

		args['bom_no'] = args['bom_no'] or item and cstr(item[0]['default_bom']) or ''
		args.update(item[0])
		
		if 'required_uom' in args:
			required_uom = args['required_uom'] or item and args['stock_uom'] or ''
		else:
			required_uom = item and args['stock_uom'] or ''
		conversion_factor = get_conversion_factor(args['item_code'], required_uom).get("conversion_factor") or 1.0

		rate = self.get_rm_rate(args)

		ret_item = {

			'item_name'	: item and args['item_name'] or '',
			'description'  : item and args['description'] or '',
			'image'		: item and args['image'] or '',
			'stock_uom'	: item and args['stock_uom'] or '',
			'uom'		: item and args['stock_uom'] or '',
			'required_uom'	: required_uom,
			'conversion_factor'	: conversion_factor,
			'bom_no'	: args['bom_no'],
			'rate'			: rate / self.conversion_rate if self.conversion_rate else rate,
			'qty'			: args.get("qty") or args.get("stock_qty") or 1,
			'stock_qty'	: args.get("qty") or args.get("stock_qty") or 1,
			'base_rate'	: rate
		}
		return ret_item

	def validate_bom_currecny(self, item):
		if item.get('bom_no') and frappe.db.get_value('BOM', item.get('bom_no'), 'currency') != self.currency:
			frappe.throw(_("Row {0}: Currency of the BOM #{1} should be equal to the selected currency {2}")
				.format(item.idx, item.bom_no, self.currency))

	def get_rm_rate(self, arg):
		"""	Get raw material rate as per selected method, if bom exists takes bom cost """
		rate = 0

		if arg.get('scrap_items'):
			rate = self.get_valuation_rate(arg)
		elif arg:
			if arg.get('bom_no') and self.set_rate_of_sub_assembly_item_based_on_bom:
				rate = self.get_bom_unitcost(arg['bom_no'])
			else:
				if self.rm_cost_as_per == 'Valuation Rate':
					rate = self.get_valuation_rate(arg)
				elif self.rm_cost_as_per == 'Last Purchase Rate':
					rate = arg.get('last_purchase_rate') \
						or frappe.db.get_value("Item", arg['item_code'], "last_purchase_rate")
				elif self.rm_cost_as_per == "Price List":
					if not self.buying_price_list:
						frappe.throw(_("Please select Price List"))
					rate = frappe.db.get_value("Item Price", {"price_list": self.buying_price_list,
						"item_code": arg["item_code"]}, "price_list_rate")

					price_list_currency = frappe.db.get_value("Price List",
						self.buying_price_list, "currency")
					if price_list_currency != self.company_currency():
						rate = flt(rate * self.conversion_rate)

				if not rate:
					frappe.msgprint(_("{0} not found for Item {1}")
						.format(self.rm_cost_as_per, arg["item_code"]))

		return flt(rate)

	def update_cost(self, update_parent=True, from_child_bom=False, update_child = True):
		if self.docstatus == 2:
			return

		existing_bom_cost = self.total_cost

		for d in self.get("items"):

			
			
			if d.bom_no:
				if update_child:
					bom_no = frappe.get_doc("BOM", d.bom_no)
					bom_no.update_cost(update_parent=False)
		
		
			
			stock_uom = frappe.db.get_value("Item", d.item_code, "stock_uom")
			if d.stock_uom != stock_uom:
				d.stock_uom = stock_uom
				
				
				if d.uom and d.qty:
					d.conversion_factor = flt(get_conversion_factor(d.item_code, d.uom)['conversion_factor'])
					d.stock_qty = flt(d.conversion_factor)*flt(d.qty)
				if not d.uom and d.stock_uom:
					d.uom = d.stock_uom
					d.qty = d.stock_qty
				
			rate = self.get_rm_rate({"item_code": d.item_code, "bom_no": d.bom_no})
			if rate:
				d.base_rate = flt(rate)
				d.rate = d.base_rate / flt(self.conversion_rate)

		if self.docstatus == 1:
			self.flags.ignore_validate_update_after_submit = True
			self.calculate_cost()

		self.update_exploded_items()
		self.save()

		frappe.msgprint(_("{0}'s Cost Updated").format(self.item))


		# update parent BOMs
		if self.total_cost != existing_bom_cost and update_parent:
			parent_boms = frappe.db.sql_list("""select distinct parent from `tabBOM Item`
				where bom_no = %s and docstatus=1 and parenttype='BOM'""", self.name)

			for bom in parent_boms:
				frappe.get_doc("BOM", bom).update_cost(from_child_bom=True)

		if not from_child_bom:
			frappe.msgprint(_("Cost Updated"))

	def get_bom_unitcost(self, bom_no):
		bom = frappe.db.sql("""select name, base_total_cost/quantity as unit_cost from `tabBOM`
			where is_active = 1 and name = %s""", bom_no, as_dict=1)
		return bom and bom[0]['unit_cost'] or 0

	def get_valuation_rate(self, args):
		""" Get weighted average of valuation rate from all warehouses """

		total_qty, total_value, valuation_rate = 0.0, 0.0, 0.0
		for d in frappe.db.sql("""select actual_qty, stock_value from `tabBin`
			where item_code=%s""", args['item_code'], as_dict=1):
				total_qty += flt(d.actual_qty)
				total_value += flt(d.stock_value)

		if total_qty:
			valuation_rate =  total_value / total_qty

		if valuation_rate <= 0:
			last_valuation_rate = frappe.db.sql("""select valuation_rate
				from `tabStock Ledger Entry`
				where item_code = %s and valuation_rate > 0
				order by posting_date desc, posting_time desc, name desc limit 1""", args['item_code'])

			valuation_rate = flt(last_valuation_rate[0][0]) if last_valuation_rate else 0

		if not valuation_rate:
			valuation_rate = frappe.db.get_value("Item", args['item_code'], "valuation_rate")

		return valuation_rate

	def manage_default_bom(self):
		""" Uncheck others if current one is selected as default,
			update default bom in item master
		"""
		if self.is_default and self.is_active:
			from frappe.model.utils import set_default
			set_default(self, "item")
			item = frappe.get_doc("Item", self.item)
			if item.default_bom != self.name:
				item.default_bom = self.name
				item.save(ignore_permissions = True)
		else:
			frappe.db.set(self, "is_default", 0)
			item = frappe.get_doc("Item", self.item)
			if item.default_bom == self.name:
				item.default_bom = None
				item.save(ignore_permissions = True)

	def clear_operations(self):
		if not self.with_operations:
			self.set('operations', [])

	def validate_main_item(self):
		""" Validate main FG item"""
		item = self.get_item_det(self.item)
		if not item:
			frappe.throw(_("Item {0} does not exist in the system or has expired").format(self.item))
		else:
			ret = frappe.db.get_value("Item", self.item, ["description", "stock_uom", "item_name",
			"depth","width","height","depthunit","widthunit","heightunit"])
			self.description = ret[0]
			self.uom = ret[1]
			self.item_name= ret[2]
			
			depth = flt(ret[3]) or 0.0
			width = flt(ret[4]) or 0.0
			height = flt(ret[5]) or 0.0
			
			if depth > 0.0:
				if not self.depth or self.depth == 0.0:
					self.depth = depth
					self.depthunit = ret[6]
					
			if width > 0.0:
				if not self.width or self.width == 0.0:
					self.width = width
					self.widthunit = ret[7]
			if height > 0.0:
				if not self.height or self.height == 0.0:
					self.height= height
					self.heightunit= ret[8]


		if not self.quantity:
			frappe.throw(_("Quantity should be greater than 0"))
			
	def get_main_item_dimensions(self):
		""" Validate main FG item"""
		item = self.get_item_det(self.item)
		if not item:
			frappe.throw(_("Item {0} does not exist in the system or has expired").format(self.item))
		else:
			ret = frappe.db.get_value("Item", self.item, ["description", "stock_uom", "item_name",
			"depth","width","height","depthunit","widthunit","heightunit"])
		
			depth = flt(ret[3]) or 0.0
			width = flt(ret[4]) or 0.0
			height = flt(ret[5]) or 0.0
			self.depth = depth
			self.depthunit = ret[6]
			self.width = width
			self.widthunit = ret[7]
			self.height= height
			self.heightunit= ret[8]

					

	def validate_currency(self):
		if self.rm_cost_as_per == 'Price List':
			price_list_currency = frappe.db.get_value('Price List', self.buying_price_list, 'currency')
			if price_list_currency not in (self.currency, self.company_currency()):
				frappe.throw(_("Currency of the price list {0} must be {1} or {2}")
					.format(self.buying_price_list, self.currency, self.company_currency()))

	def update_stock_qty(self):
		for m in self.get('items'):
			if not m.conversion_factor:
				m.conversion_factor = flt(get_conversion_factor(m.item_code, m.uom)['conversion_factor'])
			if m.uom and m.qty:
				m.stock_qty = flt(m.conversion_factor)*flt(m.qty)
			if not m.uom and m.stock_uom:
				m.uom = m.stock_uom
				m.qty = m.stock_qty

	def validate_uom_is_interger(self):
		from erpnext.utilities.transaction_base import validate_uom_is_integer
		validate_uom_is_integer(self, "uom", "qty", "BOM Item")
		validate_uom_is_integer(self, "stock_uom", "stock_qty", "BOM Item")

	def set_conversion_rate(self):
		if self.currency == self.company_currency():
			self.conversion_rate = 1
		elif self.conversion_rate == 1 or flt(self.conversion_rate) <= 0:
			self.conversion_rate = get_exchange_rate(self.currency, self.company_currency())

	def validate_materials(self):
		""" Validate raw material entries """

		def get_duplicates(lst):
			seen = set()
			seen_add = seen.add
			for item in lst:
				if item.item_code in seen or seen_add(item.item_code):
					yield item

		if not self.get('items'):
			frappe.throw(_("Raw Materials cannot be blank."))
		check_list = []
		for m in self.get('items'):
			if m.bom_no:
				validate_bom_no(m.item_code, m.bom_no)
			if flt(m.qty) <= 0:
				frappe.throw(_("Quantity required for Item {0} in row {1}").format(m.item_code, m.idx))
			check_list.append(m)

		duplicate_items = list(get_duplicates(check_list))
		if duplicate_items:
			li = []
			for i in duplicate_items:
				li.append("{0} on row {1}".format(i.item_code, i.idx))
			duplicate_list = '<br>' + '<br>'.join(li)

			frappe.throw(_("Same item has been entered multiple times. {0}").format(duplicate_list))

	def check_recursion(self):
		""" Check whether recursion occurs in any bom"""

		check_list = [['parent', 'bom_no', 'parent'], ['bom_no', 'parent', 'child']]
		for d in check_list:
			bom_list, count = [self.name], 0
			while (len(bom_list) > count ):
				boms = frappe.db.sql(" select %s from `tabBOM Item` where %s = %s and parenttype='BOM'" %
					(d[0], d[1], '%s'), cstr(bom_list[count]))
				count = count + 1
				for b in boms:
					if b[0] == self.name:
						frappe.throw(_("BOM recursion: {0} cannot be parent or child of {2}").format(b[0], self.name))
					if b[0]:
						bom_list.append(b[0])

	def update_cost_and_exploded_items(self, bom_list=[]):
		bom_list = self.traverse_tree(bom_list)
		for bom in bom_list:
			bom_obj = frappe.get_doc("BOM", bom)
			bom_obj.on_update()

		return bom_list

	def traverse_tree(self, bom_list=None):
		def _get_children(bom_no):
			return [cstr(d[0]) for d in frappe.db.sql("""select bom_no from `tabBOM Item`
				where parent = %s and ifnull(bom_no, '') != '' and parenttype='BOM'""", bom_no)]

		count = 0
		if not bom_list:
			bom_list = []

		if self.name not in bom_list:
			bom_list.append(self.name)

		while(count < len(bom_list)):
			for child_bom in _get_children(bom_list[count]):
				if child_bom not in bom_list:
					bom_list.append(child_bom)
			count += 1
		bom_list.reverse()
		return bom_list

	def calculate_cost(self):
		"""Calculate bom totals"""
		self.calculate_rm_cost()
		self.calculate_op_cost()
		self.calculate_sm_cost()
		self.total_cost = self.operating_cost + self.raw_material_cost - self.scrap_material_cost
		self.base_total_cost = self.base_operating_cost + self.base_raw_material_cost - self.base_scrap_material_cost
		

	def calculate_total_duty(self):
		dutible = 0.0
		non_dutible = 0.0
		for d in self.get('exploded_items'):
			if d.dutible == 1:
				dutible = dutible + flt(d.amount)
			else:
				non_dutible = non_dutible + flt(d.amount)

	
		customs_price = 0.0
		duty_percent = 0.0
		if dutible > 0.0:
			duty_percent = self.duty
			customs_price = (flt(duty_percent)/100 * flt(dutible + non_dutible + self.operating_cost)) + self.operating_cost + dutible
		else:
			duty_percent = self.non_duty_percent
			customs_price = flt(duty_percent)/100 * flt(dutible + non_dutible + self.operating_cost)

		self.total_duty = customs_price
		self.base_total_duty = flt(customs_price) * flt(self.conversion_rate)
		self.dutible = dutible
		self.non_dutible = non_dutible
		
		
		
	def calculate_op_cost(self):
		"""Update workstation rate and calculates totals"""
		self.operating_cost = 0
		self.base_operating_cost = 0
		for d in self.get('operations'):
			if d.workstation:
				if not d.hour_rate:
					d.hour_rate = flt(frappe.db.get_value("Workstation", d.workstation, "hour_rate"))
			if self.raw_material_cost:
				d.time_in_mins = self.raw_material_cost
			if d.hour_rate and d.time_in_mins:
				d.operating_cost = flt(d.hour_rate)/100 * flt(d.time_in_mins)
			d.base_operating_cost = d.operating_cost * self.conversion_rate


			self.operating_cost += flt(d.operating_cost)
			self.base_operating_cost += flt(d.base_operating_cost)

	def calculate_rm_cost(self):
		"""Fetch RM rate as per today's valuation rate and calculate totals"""
		total_rm_cost = 0
		base_total_rm_cost = 0

		for d in self.get('items'):
			d.base_rate = flt(d.rate) * flt(self.conversion_rate)
			# d.amount = flt(d.rate, d.precision("rate")) * flt(d.stock_qty, d.precision("qty"))
			d.amount = flt(d.rate)* flt(d.stock_qty)
			d.base_amount = d.amount * flt(self.conversion_rate)
			# d.qty_consumed_per_unit = flt(d.stock_qty, d.precision("stock_qty")) \
				# / flt(self.quantity, self.precision("quantity"))	
			d.qty_consumed_per_unit = flt(d.stock_qty) / flt(self.quantity)

			total_rm_cost += d.amount
			base_total_rm_cost += d.base_amount

		self.raw_material_cost = total_rm_cost
		self.base_raw_material_cost = base_total_rm_cost

	def calculate_sm_cost(self):
		"""Fetch RM rate as per today's valuation rate and calculate totals"""
		total_sm_cost = 0
		base_total_sm_cost = 0

		for d in self.get('scrap_items'):
			d.base_rate = d.rate * self.conversion_rate
			# d.amount = flt(d.rate, d.precision("rate")) * flt(d.stock_qty, d.precision("stock_qty"))
			d.amount = flt(d.rate)* flt(d.stock_qty)
			d.base_amount = d.amount * self.conversion_rate
			total_sm_cost += d.amount
			base_total_sm_cost += d.base_amount

		self.scrap_material_cost = total_sm_cost
		self.base_scrap_material_cost = base_total_sm_cost

	def update_exploded_items(self):
		""" Update Flat BOM, following will be correct data"""
		self.get_exploded_items()
		self.add_exploded_items()
		self.calculate_total_duty()

	def get_exploded_items(self):
		""" Get all raw materials including items from child bom"""
		self.cur_exploded_items = {}
		for d in self.get('items'):
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
				}))

	def company_currency(self):
		return erpnext.get_company_currency(self.company)

	def add_to_cur_exploded_items(self, args):
		if self.cur_exploded_items.get(args.item_code):
			self.cur_exploded_items[args.item_code]["stock_qty"] += args.stock_qty
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
			}))

	def add_exploded_items(self):
		"Add items to Flat BOM table"
		frappe.db.sql("""delete from `tabBOM Explosion Item` where parent=%s""", self.name)
		
		exploded_items = {}
		for d in self.get('exploded_items'):
			exploded_items[d.item_code] = d
			
		self.set('exploded_items', [])

		for d in sorted(self.cur_exploded_items, key=itemgetter(0)):		
			ch = self.append('exploded_items', {})
			for i in self.cur_exploded_items[d].keys():
				ch.set(i, self.cur_exploded_items[d][i])
			ch.amount = flt(ch.stock_qty) * flt(ch.rate)
			ch.qty_consumed_per_unit = flt(ch.stock_qty) / flt(self.quantity)
			if exploded_items.get(ch.item_code):
				ch.dutible = exploded_items[ch.item_code].dutible
			ch.docstatus = self.docstatus
			ch.db_insert()
			

	def validate_bom_links(self):
		if not self.is_active:
			act_pbom = frappe.db.sql("""select distinct bom_item.parent from `tabBOM Item` bom_item
				where bom_item.bom_no = %s and bom_item.docstatus = 1 and bom_item.parenttype='BOM'
				and exists (select * from `tabBOM` where name = bom_item.parent
					and docstatus = 1 and is_active = 1)""", self.name)

			if act_pbom and act_pbom[0][0]:
				frappe.throw(_("Cannot deactivate or cancel BOM as it is linked with other BOMs"))

	def validate_operations(self):
		if self.with_operations and not self.get('operations'):
			frappe.throw(_("Operations cannot be left blank"))

		if self.with_operations:
			for d in self.operations:
				if not d.description:
					d.description = frappe.db.get_value('Operation', d.operation, 'description')
		self.operation_summary = self.update_operation_summary()
	def update_operation_summary(self):
		
						
		dicts = []
		for d in self.get('operations'):
			doc_a = frappe.get_doc("Workstation",d.workstation)
			for t in doc_a.get("operating_costs"):
				dicts.append({
								'type':t.type,
								'percent':t.percent
							})
			
		
			
		from collections import defaultdict
		dd = defaultdict(int)
		for d in dicts:
			dd[d['type']] += d['percent']

		list = [{'type': k, 'percent': v} for k, v in dd.iteritems()]
		
		
		summary = ""
		joiningtext = """<table class="table table-bordered table-condensed">
						<tr>
						<th>Sr</th>
						<th width="50%">Description</th>
						<th>Percent</th>
						<th>Operating Cost</th>
						</tr>"""
		
		for i, d in enumerate(list):
			operating_cost = flt(d['percent'])/100 * flt(self.raw_material_cost)
				
			joiningtext += """<tr>
						<td>""" + str(i+1) +"""</td>
						<td>""" + str(d['type']) +"""</td>
						<td>""" + str(d['percent']) +"""</td>
						<td>""" + str(round(flt(operating_cost),2)) +"""</td>
						</tr>"""
		joiningtext += """</table><br>"""
		summary = summary + joiningtext
		return(summary)

		

	def build_bom(self):
		
		bomitems = self.bomitems
		if not (bomitems):
			frappe.throw(_("No items provided"))
		
		depthOriginal = self.depth
		widthOriginal = self.width
		heightOriginal = self.height
		qtyOriginal = self.quantity or 1
		
		
		edgebanding = []
		laminate = []
		mdf = []
		custom = []
		# glue = []
		
		for i, d in enumerate(bomitems):

			length = d.length
			width = d.width
			side = d.side
			
			perimeter = 2*flt(length)+2*flt(width)
			farea = flt(length)*flt(width)
				
			if not side:
				frappe.throw(_("No part provided"))
				
			
			bb_item = d.bb_item
			bb_qty = d.bb_qty
			requom = d.requom			
			calculation = frappe.db.get_value("BOM Part", side,["calculation"])

			d_edging = d.edging
			edging_sides = d.edgebanding
			d_laminate = d.laminate
			laminate_sides = d.laminate_sides
					
		
			
						
			bb_qty = flt(bb_qty)*flt(qtyOriginal)
			required_qty = bb_qty
			qty = flt(bb_qty)
			
	
			item = frappe.db.sql("""select stock_uom,depth,depthunit,width,widthunit,height,heightunit from `tabItem` where name=%s""", bb_item, as_dict = 1)
			if not item:
				frappe.throw(_("Item {0} does not exist").format(bb_item))

			conversion_factor = 1.0
			stock_uom = item[0].stock_uom
			required_uom = requom
			
			
			

			if calculation in ["nos"]:
				required_qty = bb_qty
				conversion_factor = get_conversion_factor(bb_item, required_uom).get("conversion_factor")
				
				if not conversion_factor:
					frappe.throw(_("Item {0} has no conversion factor for {1}").format(bb_item,required_uom))
				
				conversion_factor = flt(1/conversion_factor)
				
				qty = flt(required_qty)/flt(conversion_factor)
				newitem = {"side":side,"item_code":bb_item,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
				custom.append(newitem)
			elif calculation in ["height-profile","depth-profile","width-profile"]:
				if calculation in ["width-profile"]:
					required_qty = width * bb_qty
				elif calculation in ["height-profile","depth-profile"]:
					required_qty = length * bb_qty
				else:
					required_qty = length * bb_qty
					
				
				conversion_factor = get_conversion_factor(bb_item, required_uom).get("conversion_factor") 
				
				if not conversion_factor:
					frappe.throw(_("Item {0} has no conversion factor for {1}").format(bb_item,required_uom))
				
				conversion_factor = flt(1/conversion_factor)
				
				qty = flt(required_qty)/flt(conversion_factor)
				newitem = {"side":side,"item_code":bb_item,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
				mdf.append(newitem)

			elif calculation in ["perimeter","perimeter-width","perimeter-length"]:

				if calculation in ["perimeter-width"]:
					required_qty = (perimeter - width) * bb_qty
				elif calculation in ["perimeter-length"]:
					required_qty = (perimeter - length) * bb_qty
				else:
					required_qty = perimeter * bb_qty
					
				conversion_factor = get_conversion_factor(bb_item, required_uom).get("conversion_factor")
				
				if not conversion_factor:
					frappe.throw(_("Item {0} has no conversion factor for {1}").format(bb_item,required_uom))
				
				conversion_factor = flt(1/conversion_factor)
				
				qty = flt(required_qty)/flt(conversion_factor)
				newitem = {"side":side,"item_code":bb_item,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
				mdf.append(newitem)
				
				new_edging = process_edging(bb_item,bb_qty,side,d_edging,edging_sides,length,width,perimeter)
				if new_edging:
					edgebanding.append(new_edging)
			
			elif calculation in ["circle-perimeter"]:
				from math import pi
				perimeter = pi*flt(length)
				required_qty = perimeter * bb_qty
				
				conversion_factor = get_conversion_factor(bb_item, required_uom).get("conversion_factor")
				
				if not conversion_factor:
					frappe.throw(_("Item {0} has no conversion factor for {1}").format(bb_item,required_uom))
				
				conversion_factor = flt(1/conversion_factor)
				
				qty = flt(required_qty)/flt(conversion_factor)
				newitem = {"side":side,"item_code":bb_item,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
				mdf.append(newitem)
				
				new_edging = process_edging(bb_item,bb_qty,side,d_edging,edging_sides,length,width,perimeter)
				if new_edging:
					edgebanding.append(new_edging)
			
			elif calculation in ["circle-area"]:
			
				from math import pi

			
				perimeter = pi*flt(length)
				farea = pi * flt(length/2)*flt(length/2)
				
				required_qty = farea * bb_qty
				
				conversion_factor = get_conversion_factor(bb_item, required_uom).get("conversion_factor")
				
				if not conversion_factor:
					frappe.throw(_("Item {0} has no conversion factor for {1}").format(bb_item,required_uom))
				
				conversion_factor = flt(1/conversion_factor)
				
				# calculate stock required_qty using dimensions of item
				qty = flt(required_qty) / flt(conversion_factor)
				
				newitem = {"side":side,"item_code":bb_item,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
				mdf.append(newitem)
				
				new_laminate = process_laminate(bb_item,bb_qty,side,d_laminate,laminate_sides,length,width,farea)
				if new_laminate:
					laminate.append(new_laminate)

				new_edging = process_edging(bb_item,bb_qty,side,d_edging,edging_sides,length,width,perimeter)
				if new_edging:
					edgebanding.append(new_edging)

				
			elif calculation in ["area"]:

				required_qty = farea * bb_qty
				
				conversion_factor = get_conversion_factor(bb_item, required_uom).get("conversion_factor")
		
				if not conversion_factor:
					frappe.throw(_("Item {0} has no conversion factor for {1}").format(bb_item,required_uom))
				
				conversion_factor = flt(1/conversion_factor)
				
				# calculate stock required_qty using dimensions of item
				qty = flt(required_qty) / flt(conversion_factor)
				
				newitem = {"side":side,"item_code":bb_item,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
				mdf.append(newitem)
				
				new_laminate = process_laminate(bb_item,bb_qty,side,d_laminate,laminate_sides,length,width,farea)
				if new_laminate:
					laminate.append(new_laminate)

				new_edging = process_edging(bb_item,bb_qty,side,d_edging,edging_sides,length,width,perimeter)
				if new_edging:
					edgebanding.append(new_edging)

				
				
		
		summary = ""
		if len(custom)> 0 :
			summary = str(create_condensed_table(custom))
				
		materials = mdf + laminate + edgebanding
		if len(materials)> 0 :
			summary = str(summary) + str(create_custom_table(materials))
		
		merged = merge(custom + materials)
		
		self.update_bom_builder(merged)
		self.set('summary',summary)
		
		
		
		return merged,summary
		
	
	def update_bom_builder(self,merged):
		self.set('items', [])

		for item in sorted(merged):
			
			d = merged[item]

			newd = self.append('items')
			newd.item_code = d["item_code"]
			newd.stock_qty = d["qty"]
			
			bom_no = get_default_bom(d["item_code"],self.project)
			ret_item = self.get_bom_material_detail({"item_code": d["item_code"], "bom_no": bom_no,"stock_qty": d["qty"],"required_uom":d["required_uom"]})
			
			newd.rate = flt(ret_item["rate"])
			newd.base_rate = flt(ret_item["base_rate"])
			newd.stock_uom = ret_item["stock_uom"]
			
			newd.amount = flt(ret_item["rate"])*flt(d["qty"])
			
			newd.qty = flt(d["required_qty"])
			
			# from previous changes
			newd.required_uom = d["required_uom"]
			newd.uom = d["required_uom"]
			
			newd.conversion_factor = ret_item["conversion_factor"]
			
			newd.bom_no = ret_item["bom_no"]
			newd.item_name = ret_item["item_name"]
			newd.description = ret_item["description"]
			
	
		# self.check_recursion()
		# self.update_exploded_items()
			
		


def get_list_context(context):
	context.title = _("Bill of Materials")
	# context.introduction = _('Boms')

def get_bom_items_as_dict(bom, company, qty=1, fetch_exploded=1, fetch_scrap_items=0):
	item_dict = {}

	# Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
	query = """select
				bom_item.item_code,
				bom_item.idx,
				item.item_name,
				sum(bom_item.stock_qty/ifnull(bom.quantity, 1)) * %(qty)s as qty,
				item.description,
				item.image,
				item.stock_uom,
				item.default_warehouse,
				item.expense_account as expense_account,
				item.buying_cost_center as cost_center
				{select_columns}
			from
				`tab{table}` bom_item, `tabBOM` bom, `tabItem` item
			where
				bom_item.docstatus < 2
				and bom.name = %(bom)s
				and bom_item.parent = bom.name
				and item.name = bom_item.item_code
				and is_stock_item = 1
				{where_conditions}
				group by item_code, stock_uom
				order by idx"""

	if fetch_exploded:
		query = query.format(table="BOM Explosion Item",
			where_conditions="",
			select_columns = ", bom_item.source_warehouse, (Select idx from `tabBOM Item` where item_code = bom_item.item_code and parent = %(parent)s ) as idx")
		items = frappe.db.sql(query, { "parent": bom, "qty": qty,	"bom": bom }, as_dict=True)
	elif fetch_scrap_items:
		query = query.format(table="BOM Scrap Item", where_conditions="", select_columns=", bom_item.idx")
		items = frappe.db.sql(query, { "qty": qty, "bom": bom }, as_dict=True)
	else:
		query = query.format(table="BOM Item", where_conditions="",
			select_columns = ", bom_item.source_warehouse, bom_item.idx")
		items = frappe.db.sql(query, { "qty": qty, "bom": bom }, as_dict=True)

	for item in items:
		if item_dict.has_key(item.item_code):
			item_dict[item.item_code]["qty"] += flt(item.qty)
		else:
			item_dict[item.item_code] = item

	for item, item_details in item_dict.items():
		for d in [["Account", "expense_account", "default_expense_account"],
			["Cost Center", "cost_center", "cost_center"], ["Warehouse", "default_warehouse", ""]]:
				company_in_record = frappe.db.get_value(d[0], item_details.get(d[1]), "company")
				if not item_details.get(d[1]) or (company_in_record and company != company_in_record):
					item_dict[item][d[1]] = frappe.db.get_value("Company", company, d[2]) if d[2] else None

	return item_dict
	


def convert_units(unit,value):
	if unit == "ft":
		finalvalue = flt(value) * flt(.3048)
	elif unit == "cm":
		finalvalue = flt(value) * flt(.01)
	elif unit == "mm":
		finalvalue = flt(value) * flt(0.001)
	elif unit == "in":
		finalvalue = flt(value) * flt(.0254)
	else:
		finalvalue = flt(value)
	return finalvalue	
		
def merge(dicts):
	item_dict = {}
	for item in dicts:
		if item_dict.has_key(item["item_code"]):
			item_dict[item["item_code"]]["qty"] += flt(item["qty"])
			item_dict[item["item_code"]]["required_qty"] += flt(item["required_qty"])
		else:
			item_dict[item["item_code"]] = item
	
	return item_dict

def sbv0(adict,reverse=False):
    ''' proposed at Digital Sanitation Engineering
    http://blog.modp.com/2007/11/sorting-python-dict-by-value.html '''
    return sorted(adict.iteritems(), key=lambda (k,v): (v,k), reverse=reverse)

@frappe.whitelist()
def get_bom_items(bom, company, qty=1, fetch_exploded=1):
	items = get_bom_items_as_dict(bom, company, qty, fetch_exploded).values()
	items.sort(lambda a, b: a.item_code > b.item_code and 1 or -1)
	return items

def validate_bom_no(item, bom_no):
	"""Validate BOM No of sub-contracted items"""
	bom = frappe.get_doc("BOM", bom_no)
	if not bom.is_active:
		frappe.throw(_("BOM {0} must be active").format(bom_no))
	if bom.docstatus != 1:
		if not getattr(frappe.flags, "in_test", False):
			frappe.throw(_("BOM {0} must be submitted").format(bom_no))
	if item and not (bom.item.lower() == item.lower() or \
		bom.item.lower() == cstr(frappe.db.get_value("Item", item, "variant_of")).lower()):
		frappe.throw(_("BOM {0} does not belong to Item {1}").format(bom_no, item))

@frappe.whitelist()
def get_children(doctype, parent=None, is_tree=False):
	if not parent:
		frappe.msgprint(_('Please select a BOM'))
		return

	if frappe.form_dict.parent:
		return frappe.db.sql("""select
			bom_item.item_code,
			bom_item.bom_no as value,
			bom_item.stock_qty,
			if(ifnull(bom_item.bom_no, "")!="", 1, 0) as expandable,
			item.image,
			item.description
			from `tabBOM Item` bom_item, tabItem item
			where bom_item.parent=%s
			and bom_item.item_code = item.name
			order by bom_item.idx
			""", frappe.form_dict.parent, as_dict=True)


@frappe.whitelist()
def get_product_bundle_items(item_code):
	new_dict = frappe.db.sql("""select t1.bb_item, t1.bb_qty, t1.side, t1.requom, t1.edging,t1.edgebanding,t1.laminate,t1.laminate_sides
		from `tabBOM Builder Item` t1, `tabBOM Collection` t2
		where t2.collection_name=%s and t1.parent = t2.name order by t1.idx""", item_code, as_dict=1)
	return new_dict
	
@frappe.whitelist()
def get_part_details(part=None,item_code=None):
	plane = ""
	required_uom = "Nos"
	
	if part:
		plane,required_uom = frappe.db.get_value("BOM Part", part,["plane", "required_uom"])
		
		
		if required_uom in ['Nos']:
			if item_code:
				from erpnext.stock.get_item_details import get_default_uom
				required_uom = get_default_uom(item_code)
			
	return plane,required_uom

def process_edging(bb_item,bb_qty,side,d_edging,edging_sides,length,width,perimeter):
	if edging_sides and edging_sides != "None" and d_edging:
		edginginfo = frappe.db.sql("""select stock_uom from `tabItem` where name=%s""", d_edging, as_dict = 1)
		if not edginginfo:
			frappe.msgprint(_("Item {0} not found").format(d_edging))
			return None
			
		required_qty = 0
		
		# if edging_sides in ["2L+2W"]:
			# required_qty = perimeter* flt(bb_qty)

		# elif edging_sides in ["2L"]:
			# required_qty = 2*length* flt(bb_qty)
			
		# elif edging_sides in ["2W"]:
			# required_qty = 2*width* flt(bb_qty)
		
		# elif edging_sides in ["L"]:
			# required_qty = length* flt(bb_qty)
			
		# elif edging_sides in ["W"]:
			# required_qty = width* flt(bb_qty)
			
		# elif edging_sides in ["2L+W"]:
			# required_qty = (2*length+width)* flt(bb_qty)
			
		# elif edging_sides in ["2W+L"]:
			# required_qty = (2*width+length)* flt(bb_qty)
			
		# elif edging_sides in ["L+W"]:
			# required_qty = (length+width)* flt(bb_qty)

			
		if edging_sides in ["All Sides"]:
			required_qty = perimeter* flt(bb_qty)

				
		elif edging_sides in ["Front Side","Front Only","Back Only"]:
			required_qty = width* flt(bb_qty)
			
			
			
		elif edging_sides in ["Front & Back"]:
			required_qty = 2 * width * flt(bb_qty)
			

			
		elif edging_sides in ["Sides Only"]:
			required_qty = 2 * length* flt(bb_qty)

			
			
		elif edging_sides in ["FrontAndSides","Front & Sides"]:
			required_qty = ( flt(perimeter) - flt(width) )* flt(bb_qty)
			
			
		if side in ["door frame"]:
			required_qty = flt(2*length + width)* flt(bb_qty)
		elif side in ["frame"]:
			required_qty = flt(perimeter)* flt(bb_qty)
		elif side in ["single door","AngledSingleDoor"]:
			required_qty = flt(perimeter)* flt(bb_qty)
		elif side in ["double door","AngledDoubleDoor"]:
			required_qty = ( 2*flt(length) + flt(perimeter))* flt(bb_qty)
			
		required_uom = "m"
		stock_uom = edginginfo[0].stock_uom
		conversion_factor = get_conversion_factor(d_edging, required_uom).get("conversion_factor")
		
		if not conversion_factor:
			frappe.throw(_("Item {0} has no conversion factor for {1}").format(d_edging,required_uom))
		
		conversion_factor = flt(1/conversion_factor)
				
		qty = flt(required_qty)/flt(conversion_factor)
		detail = side + " " + edging_sides

		
		newitem = {"side":detail,"item_code":d_edging,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
		return newitem
	else:
		return None
		
def process_laminate(bb_item,bb_qty,side,d_laminate,laminate_sides,length,width,farea):
	if laminate_sides and laminate_sides != "None" and d_laminate:
		required_qty = 0
					
		laminate_info = frappe.db.sql("""select stock_uom from `tabItem` where name=%s""", d_laminate, as_dict = 1)
		
		if not laminate_info:
			frappe.msgprint(_("Item {0} not found").format(d_laminate))
			return None
		
		
		required_qty =  bb_qty * farea
		if laminate_sides == "Double Pressed":
			required_qty = bb_qty * farea * 2

			
		required_uom = "sqm"
		conversion_factor = get_conversion_factor(d_laminate, required_uom).get("conversion_factor")
		
		if not conversion_factor:
			frappe.throw(_("Item {0} has no conversion factor for {1}").format(d_laminate,required_uom))
		
		conversion_factor = flt(1/conversion_factor)
		
		
		stock_uom = laminate_info[0].stock_uom
		# calculate stock required_qty using dimensions of item
		qty = flt(required_qty) / flt(conversion_factor)
		
		detail = side + " " + laminate_sides
		newitem = {"side":detail,"item_code":d_laminate,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
		return newitem
		

		# if glueitem:
			# glueinfo = frappe.db.sql("""select stock_uom from `tabItem` where name=%s""", glueitem, as_dict = 1)
			# required_qty = required_qty*200
			# required_uom = "g"
			# conversion_factor = get_conversion_factor(glueitem, required_uom).get("conversion_factor") or 1.0
			# stock_uom = glueinfo[0].stock_uom
			# conversion_factor = flt(1/conversion_factor)
			# qty = flt(required_qty)/flt(conversion_factor)
			# newitem = {"side":side,"item_code":glueitem,"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
			# glue.append(newitem)
		# else:
			# frappe.msgprint(_("Glue Item Not Set"))
	else:
		return None
def create_condensed_table(dict):
	summary = ""
	
	joiningtext = """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>
				<th width="20%">Item Code</th>
				<th>Part</th>
				<th>Required Qty</th>
				<th width="20%">Stock Details</th>
				<th width="20%">Stock Qty</th>
				</tr></thead><tbody>"""	
	for i, d in enumerate(dict):
		d["qty"] = round_decimal_sig(flt(d["qty"]),3)
		d["conversion_factor"] = round_decimal_sig(flt(d["conversion_factor"]),3)
		
		joiningtext += """<tr>
					<td>""" + str(d["item_code"]) +"""</td>
					<td>""" + str(d["side"]) +"""</td>
					<td>""" + str(d["required_qty"]) + " " +str(d["required_uom"])+"""</td>
					<td>""" + str(d["conversion_factor"]) + (" " + str(d["required_uom"]) + "/" + str(d["stock_uom"]) if d["conversion_factor"] else "")+"""</td>
					<td>""" + str(d["qty"]) + " " +str(d["stock_uom"])+"""</td>
					</tr>"""
	joiningtext += """</tbody></table>"""
	summary += joiningtext
	return summary
	
	
def create_custom_table(dict):
	summary = ""
	
	joiningtext = """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>
				<th width="20%">Item Code</th>
				<th>Part</th>
				<th>Length (m)</th>
				<th>Width (m)</th>
				<th>Required Qty</th>
				<th width="20%">Stock Details</th>
				<th width="20%">Stock Qty</th>
				</tr></thead><tbody>"""	
	for i, d in enumerate(dict):
		d["qty"] = round_decimal_sig(flt(d["qty"]),3)
		d["conversion_factor"] = round_decimal_sig(flt(d["conversion_factor"]),3)
		joiningtext += """<tr>
					<td>""" + str(d["item_code"]) +"""</td>
					<td>""" + str(d["side"]) +"""</td>
					<td>""" + str(d["length"]) +"""</td>
					<td>""" + str(d["width"]) +"""</td>
					<td>""" + str(d["required_qty"]) + " " +str(d["required_uom"])+"""</td>
					<td>""" + str(d["conversion_factor"]) + (" " + str(d["required_uom"]) + "/" + str(d["stock_uom"]) if d["conversion_factor"] else "")+"""</td>
					<td>""" + str(d["qty"]) + " " +str(d["stock_uom"])+"""</td>
					</tr>"""
	joiningtext += """</tbody></table>"""
	summary += joiningtext
	return summary

@frappe.whitelist()	
def get_default_bom(item_code,project=None):
	bom_no = ""
	if project:
		bom_no = frappe.db.get_value("BOM", filters={"item": item_code, "is_active": 1,"docstatus": 1, "project": project}) or frappe.db.get_value("BOM", filters={"item": item_code, "is_active": 1,"docstatus": 1, "is_default": 1})
	else:
		bom_no = frappe.db.get_value("BOM", {"item": item_code, "is_active": 1, "is_default": 1})
	return bom_no
	
def round_sig(x, sig=2):
	from math import log10, floor
	if x != 0:
		return round(x, -int(floor(log10(abs(x))) - (sig - 1)))
	else:
		return 0  # Can't take the log of 0

def round_decimal_sig(x, sig=2):

	import math
	frac, whole = math.modf(x)
	final_num = whole + round_sig(frac,sig)
	return flt(final_num)
	
def get_boms_in_bottom_up_order(bom_no=None):
	def _get_parent(bom_no):
		return frappe.db.sql_list("""select distinct parent from `tabBOM Item`
			where bom_no = %s and docstatus=1 and parenttype='BOM'""", bom_no)

	count = 0
	bom_list = []
	if bom_no:
		bom_list.append(bom_no)
	else:
		# get all leaf BOMs
		bom_list = frappe.db.sql_list("""select name from `tabBOM` bom where docstatus=1
			and not exists(select bom_no from `tabBOM Item`
				where parent=bom.name and ifnull(bom_no, '')!='')""")

	while(count < len(bom_list)):
		for child_bom in _get_parent(bom_list[count]):
			if child_bom not in bom_list:
				bom_list.append(child_bom)
		count += 1

	return bom_list
