# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe import _
from frappe.utils import cint, cstr, flt, ceil
from erpnext.setup.utils import get_exchange_rate
from erpnext import get_company_currency, get_default_company


class ItemPriceDuplicateItem(frappe.ValidationError): pass


from frappe.model.document import Document


class ItemPrice(Document):

	def validate(self):
		self.validate_item()
		self.validate_dates()
		self.update_price_list_details()
		self.update_item_details()
		self.check_duplicates()

	def validate_item(self):
		if not frappe.db.exists("Item", self.item_code):
			frappe.throw(_("Item {0} not found").format(self.item_code))

	def validate_dates(self):
		if self.valid_from and self.valid_upto:
			if self.valid_from > self.valid_upto:
				frappe.throw(_("Valid From Date must be lesser than Valid Upto Date."))

	def update_price_list_details(self):
		if self.price_list:
			price_list_details = frappe.db.get_value("Price List",
				{"name": self.price_list, "enabled": 1},
				["buying", "selling", "currency"])

			if not price_list_details:
				link = frappe.utils.get_link_to_form('Price List', self.price_list)
				frappe.throw("The price list {0} does not exists or disabled".
					format(link))

			self.buying, self.selling, self.currency = price_list_details

	def update_item_details(self):
		if self.item_code:
			self.item_name, self.item_description,self.stock_uom = frappe.db.get_value("Item",
				self.item_code, ["item_name", "description","stock_uom"])
			if not self.uom:
				self.uom = self.stock_uom

	def check_duplicates(self):
		conditions = "where item_code=%(item_code)s and price_list=%(price_list)s and name != %(name)s"
		condition_data_dict = dict(item_code=self.item_code, price_list=self.price_list, name=self.name)

		for field in ['uom', 'valid_from',
			'valid_upto', 'packing_unit', 'customer', 'supplier']:
			if self.get(field):
				conditions += " and {0} = %({1})s".format(field, field)
				condition_data_dict[field] = self.get(field)

		price_list_rate = frappe.db.sql("""
			SELECT price_list_rate
			FROM `tabItem Price`
			  {conditions} """.format(conditions=conditions), condition_data_dict)

		if price_list_rate :
			frappe.throw(_("Item Price appears multiple times based on Price List, Supplier/Customer, Currency, Item, UOM, Qty and Dates."), ItemPriceDuplicateItem)

	def before_save(self):
		if self.selling:
			self.reference = self.customer
		if self.buying:
			self.reference = self.supplier
		
		if self.selling and not self.buying:
			# if only selling then remove supplier
			self.supplier = None
		if self.buying and not self.selling:
			# if only buying then remove customer
			self.customer = None

@frappe.whitelist()
def add_to_another_pl(item_price_docname, new_price_list):
	new_price_list_currency = frappe.db.get_value("Price List",
			{"name": new_price_list, "enabled": 1},
			["currency"])
		
	if not new_price_list_currency:
		link = frappe.utils.get_link_to_form('Price List', new_price_list)
		frappe.throw("The price list {0} does not exists or disabled".
			format(link))
	
	item_price_doc = frappe.get_doc("Item Price", item_price_docname)
	original_price_list = item_price_doc.price_list
	original_item_price = item_price_doc.price_list_rate
	original_price_list_currency = item_price_doc.currency
	
	if not original_price_list_currency == new_price_list_currency:
		conversion_rate = get_exchange_rate(original_price_list_currency,new_price_list_currency, args="for_buying")
		new_price_list_rate = flt(original_item_price) * (conversion_rate or 1)
	
	copy_doc = frappe.copy_doc(item_price_doc)
	copy_doc.update({"price_list": new_price_list})
	copy_doc.update({"price_list_rate": new_price_list_rate})
	try:
		copy_doc.insert()
		return copy_doc.name
	except frappe.DuplicateEntryError:
		pass
		
@frappe.whitelist()
def copy_all_to_another_pl(original_price_list, new_price_list):
	new_price_list_currency = frappe.db.get_value("Price List",
			{"name": new_price_list, "enabled": 1},
			["currency"])
		
	if not new_price_list_currency:
		link = frappe.utils.get_link_to_form('Price List', new_price_list)
		frappe.throw("The price list {0} does not exists or disabled".
			format(link))
	
	item_price_names = frappe.get_all("Item Price",
		fields = ["name"],
		filters = {'price_list': original_price_list}
	)

	for d in item_price_names:
		add_to_another_pl(d.name, new_price_list)
	
	
	return