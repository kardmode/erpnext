# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.model.naming import make_autoname
from frappe.utils import flt
from frappe import _
from frappe.utils import getdate


from erpnext.controllers.selling_controller import SellingController

form_grid_templates = {
	"items": "templates/form_grid/item_grid.html"
}

class Quotation(SellingController):
	def autoname(self):
		import datetime
		year = (getdate(self.transaction_date)).year
		self.name = make_autoname('QTN-'+ str(year) + '.#####')
	def validate(self):
		super(Quotation, self).validate()
		self.set_status()
		self.update_opportunity()
		self.validate_order_type()
		self.validate_uom_is_integer("stock_uom", "qty")
		self.validate_quotation_to()
		if self.items:
			self.with_items = 1

	def has_sales_order(self):
		return frappe.db.get_value("Sales Order Item", {"prevdoc_docname": self.name, "docstatus": 1})

	def validate_order_type(self):
		super(Quotation, self).validate_order_type()

	def validate_quotation_to(self):
		if self.customer:
			self.quotation_to = "Customer"
			self.lead = None
		elif self.lead:
			self.quotation_to = "Lead"

	def update_lead(self):
		if self.lead:
			frappe.get_doc("Lead", self.lead).set_status(update=True)

	def update_opportunity(self):
		for opportunity in list(set([d.prevdoc_docname for d in self.get("items")])):
			if opportunity:
				frappe.get_doc("Opportunity", opportunity).set_status(update=True)

	def declare_order_lost(self, arg):
		if not self.has_sales_order():
			frappe.db.set(self, 'status', 'Lost')
			frappe.db.set(self, 'order_lost_reason', arg)
			self.update_opportunity()
			self.update_lead()
		else:
			frappe.throw(_("Cannot set as Lost as Sales Order is made."))

	def check_item_table(self):
		if not self.get('items'):
			frappe.throw(_("Please enter item details"))

	def on_submit(self):
		self.check_item_table()

		# Check for Approving Authority
		frappe.get_doc('Authorization Control').validate_approving_authority(self.doctype, self.company, self.base_grand_total, self)

		#update enquiry status
		self.update_opportunity()
		self.update_lead()

	def on_cancel(self):
		#update enquiry status
		self.set_status(update=True)
		self.update_opportunity()
		self.update_lead()

	def print_other_charges(self,docname):
		print_lst = []
		for d in self.get('taxes'):
			lst1 = []
			lst1.append(d.description)
			lst1.append(d.total)
			print_lst.append(lst1)
		return print_lst


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	return _make_sales_order(source_name, target_doc)

def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
	customer = _make_customer(source_name, ignore_permissions)

	def set_missing_values(source, target):
		if customer:
			target.customer = customer.name
			target.customer_name = customer.customer_name
		target.ignore_pricing_rule = 1
		target.flags.ignore_permissions = ignore_permissions
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
		if source.project:
			target.project = source.project
		

	def update_item(obj, target, source_parent):
		target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)	

	doclist = get_mapped_doc("Quotation", source_name, {
			"Quotation": {
				"doctype": "Sales Order",
				"validation": {
					"docstatus": ["=", 1]
				}
			},
			"Quotation Item": {
				"doctype": "Sales Order Item",
				"field_map": {
					"parent": "prevdoc_docname"
				},
				"postprocess": update_item
			},
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"add_if_empty": True
			},
			"Sales Team": {
				"doctype": "Sales Team",
				"add_if_empty": True
			}
		}, target_doc, set_missing_values, ignore_permissions=ignore_permissions)

	# postprocess: fetch shipping address, set missing values
	
	return doclist

def _make_customer(source_name, ignore_permissions=False):
	quotation = frappe.db.get_value("Quotation", source_name, ["lead", "order_type", "customer"])
	if quotation and quotation[0] and not quotation[2]:
		lead_name = quotation[0]
		customer_name = frappe.db.get_value("Customer", {"lead_name": lead_name},
			["name", "customer_name"], as_dict=True)
		if not customer_name:
			from erpnext.crm.doctype.lead.lead import _make_customer
			customer_doclist = _make_customer(lead_name, ignore_permissions=ignore_permissions)
			customer = frappe.get_doc(customer_doclist)
			customer.flags.ignore_permissions = ignore_permissions
			if quotation[1] == "Shopping Cart":
				customer.customer_group = frappe.db.get_value("Shopping Cart Settings", None,
					"default_customer_group")

			try:
				customer.insert()
				return customer
			except frappe.NameError:
				if frappe.defaults.get_global_default('cust_master_name') == "Customer Name":
					customer.run_method("autoname")
					customer.name += "-" + lead_name
					customer.insert()
					return customer
				else:
					raise
			except frappe.MandatoryError:
				frappe.local.message_log = []
				frappe.throw(_("Please create Customer from Lead {0}").format(lead_name))
		else:
			return customer_name
		

			
@frappe.whitelist()
def upload():
	if not frappe.has_permission("Quotation", "create"):
		raise frappe.PermissionError

	from frappe.utils.csvutils import read_csv_content_from_uploaded_file
	from frappe.modules import scrub

	rows = read_csv_content_from_uploaded_file()
	rows = filter(lambda x: x and any(x), rows)
	if not rows:
		msg = [_("Please select a csv file")]
		return {"messages": msg, "error": msg}
	columns = [scrub(f) for f in rows[0]]
	columns[0] = "item_code"
	ret = []
	error = False
	messages = []
	start_row = 1
	for i, row in enumerate(rows[start_row:]):
		
		row_idx = i + start_row
		d = frappe._dict(zip(columns, row))
		itemdict = frappe.db.sql("""select name,item_group, is_sales_item from `tabItem` where name = %s and docstatus < 2""",d.item_code, as_dict=1)
		
		if itemdict:
			item = itemdict[0]
			newitem = {}
			newitem["item_code"] = item.name
			newitem["qty"] = d.quantity
			newitem["item_group"] = item.item_group
			if d.page_break:
				newitem["page_break"] = True
			else:
				newitem["page_break"] = False
			
			if item.is_sales_item:
			
				if str(item.item_group).lower() in {"header1","header2","header3","header4"}:
					newitem["qty"] = "0"
					ret.append(newitem)
					if d.page_break:
						messages.append('Header Row (#%d) %s with Page Break' % (row_idx,row[0]))	
					else:
						messages.append('Header Row (#%d) %s' % (row_idx,row[0]))	
				elif str(item.item_group).lower() == "raw material":
					messages.append('Ignored Row (#%d) %s : Item is a raw material' % (row_idx,row[0]))		
				elif str(item.item_group).lower() == "assemblypart":
					messages.append('Ignored Row (#%d) %s : Item is an assembly part' % (row_idx,row[0]))		
				else:
					ret.append(newitem)
					if d.page_break:
						messages.append('Row (#%d) %s : Item added with Page Break' % (row_idx,row[0]))	
					else:
						messages.append('Row (#%d) %s : Item added' % (row_idx,row[0]))	
			else:
				error = True
				messages.append('Error for row (#%d) %s : Item is not a sales item' % (row_idx,row[0]))		
		else:
			error = True
			messages.append('Error for row (#%d) %s : Invalid Item Code' % (row_idx,row[0]))		
		

	return {"items":ret,"messages": messages, "error": error}


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	def set_missing_values(source, target):
		quotation = frappe.get_doc(target)

		company_currency = frappe.db.get_value("Company", quotation.company, "default_currency")
		# party_account_currency = get_party_account_currency("Customer", quotation.customer,
			# quotation.company) if quotation.customer else company_currency

		# quotation.currency = party_account_currency or company_currency

		# if company_currency == quotation.currency:
			# exchange_rate = 1
		# else:
			# exchange_rate = get_exchange_rate(quotation.currency, company_currency,
				# quotation.transaction_date)

		# quotation.conversion_rate = exchange_rate

		quotation.run_method("set_missing_values")
		quotation.run_method("calculate_taxes_and_totals")
		


	doclist = get_mapped_doc("Product Collection", source_name, {
		"Product Collection": {
			"doctype": "Quotation",
		},
		"Product Collection Item": {
			"doctype": "Quotation Item",
			"field_map": {
					"parent": "prevdoc_docname"
				}
		}
	}, target_doc, set_missing_values)

	return doclist

@frappe.whitelist()
def get_product_bundle_items(item_code):
	new_dict = frappe.db.sql("""select t1.item_code, t1.qty, t1.uom, t1.description
		from `tabProduct Collection Item` t1, `tabProduct Collection` t2
		where t2.new_item_code=%s and t1.parent = t2.name order by t1.idx""", item_code, as_dict=1)
	frappe.errprint(new_dict)
	return new_dict
		
# @frappe.whitelist()
# def build_item_summary(items = None):

	
	# if not (items):
		# frappe.throw(_("No items provided"))
	
	# import json
	# bomitems = json.loads(items)
	
	# custom = []
	# # glue = []
	# summary = ""
	# for i, d in enumerate(bomitems):

		# d['qty'] = flt(d['qty'])*flt(qtyOriginal)
		# qty = flt(d['qty'])
		
		# item = frappe.db.sql("""select stock_uom from `tabItem` where name=%s""", d['item_code'], as_dict = 1)

		# conversion_factor = 1.0
		# stock_uom = item[0].stock_uom
		# required_uom = item[0].stock_uom
		# from math import ceil

		# if d['side'] in ["hardware","custom",""]:

			# required_qty = d['qty']
			# qty = d['qty']
			# newitem = {"side":d['side'],"item_code":d['item_code'],"length":length,"width":width,"required_qty":required_qty,"qty":qty,"conversion_factor":conversion_factor,"stock_uom":stock_uom,"required_uom":required_uom}
			# custom.append(newitem)
		
			
	# for dicts in (custom):
		# if len(dicts)> 0 :
			

			# joiningtext = """<table class="table table-bordered table-condensed">
						# <tr>
						# <th>Sr</th>
						# <th width="20%">Item Code</th>
						# <th>Part</th>
						# <th>Length (m)</th>
						# <th>Width (m)</th>
						# <th>Required Qty</th>
						# <th width="20%">Stock Details</th>
						# <th width="20%">Stock Qty</th>
						# </tr>"""
			# for i, d in enumerate(dicts):
				# d["qty"] = round(flt(d["qty"]),5)
				# d["conversion_factor"] = round(flt(d["conversion_factor"]),5)
				# joiningtext += """<tr>
							# <td>""" + str(i+1) +"""</td>
							# <td>""" + str(d["item_code"]) +"""</td>
							# <td>""" + str(d["side"]) +"""</td>
							# <td>""" + str(d["length"]) +"""</td>
							# <td>""" + str(d["width"]) +"""</td>
							# <td>""" + str(d["required_qty"]) + " " +str(d["required_uom"])+"""</td>
							# <td>""" + str(d["conversion_factor"]) + (" " + str(d["required_uom"]) + "/" + str(d["stock_uom"]) if d["conversion_factor"] else "")+"""</td>
							# <td>""" + str(d["qty"]) + " " +str(d["stock_uom"])+"""</td>
							# </tr>"""
			# joiningtext += """</table><br>"""
			# summary = summary + joiningtext
	

	# return custom,summary
