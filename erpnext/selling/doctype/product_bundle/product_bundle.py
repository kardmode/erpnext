# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe import _

from frappe.model.document import Document

class ProductBundle(Document):
	# def autoname(self):
		# self.name = self.new_item_code

	def validate(self):
		self.validate_main_item()
		self.validate_child_items()
		from erpnext.utilities.transaction_base import validate_uom_is_integer
		validate_uom_is_integer(self, "uom", "qty")

	def validate_main_item(self):
		"""Validates, main Item is not a stock item"""
		if frappe.db.get_value("Item", self.new_item_code, "is_stock_item"):
			frappe.throw(_("Parent Item {0} must not be a Stock Item").format(self.new_item_code))
			
		if self.is_default:
			if frappe.db.sql("""select name from `tabProduct Bundle`
				where new_item_code = %s and name <> %s and is_default = 1""", (self.new_item_code,self.name)):
				frappe.throw(_("There is already a default product bundle for this item.").format(self.new_item_code,self.name))
		elif not self.project:
			frappe.throw(_("Project is required if not a default bundle.").format(self.new_item_code))
		
		if self.project:
			if frappe.db.sql("""select name from `tabProduct Bundle`
				where new_item_code = %s and name <> %s and project = %s""", (self.new_item_code,self.name,self.project)):
				frappe.throw(_("There is already a product bundle for this item and project").format(self.new_item_code,self.name,self.project))
			
	def validate_child_items(self):
		total_qty = 0
		total = 0
		for item in self.items:
			item.amount = item.rate * item.qty
			total += item.amount
			total_qty += item.qty
			if frappe.db.exists("Product Bundle", item.item_code):
				frappe.throw(_("Child Item should not be a Product Bundle. Please remove item `{0}` and save").format(item.item_code))
		
		self.total_qty = total_qty
		self.total = total
		
def get_new_item_code(doctype, txt, searchfield, start, page_len, filters):
	from erpnext.controllers.queries import get_match_cond

	# return frappe.db.sql("""select name, item_name, description from tabItem
		# where is_stock_item=0 and name not in (select name from `tabProduct Bundle`)
		# and %s like %s %s limit %s, %s""" % (searchfield, "%s",
		# get_match_cond(doctype),"%s", "%s"),
		# ("%%%s%%" % txt, start, page_len))
		
	return frappe.db.sql("""select name, item_name, description from tabItem
		where is_stock_item=0
		and %s like %s %s limit %s, %s""" % (searchfield, "%s",
		get_match_cond(doctype),"%s", "%s"),
		("%%%s%%" % txt, start, page_len))

def has_product_bundle(item_code,project=None):
	
	if project:
	
		with_project = frappe.db.sql("""select name from `tabProduct Bundle` 
			where new_item_code=%s and project=%s and docstatus != 2""", (item_code,project))
		if with_project:
			return with_project
		
		return frappe.db.sql("""select name from `tabProduct Bundle`
			where new_item_code=%s and is_default = 1 and docstatus != 2""", item_code)
	else:
		return frappe.db.sql("""select name from `tabProduct Bundle`
			where new_item_code=%s and is_default = 1 and docstatus != 2""", item_code)

def get_product_bundle_details(name):
	return frappe.db.get_value("Product Bundle",name, ["use_total_to_cost", "total"], as_dict=1)
