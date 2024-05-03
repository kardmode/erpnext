# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form
from frappe.utils import cint, cstr, flt, today, ceil
from erpnext.stock.doctype.item.item import get_item_details
from erpnext.stock.get_item_details import get_conversion_factor, get_price_list_rate


class ProductBundle(Document):
	# def autoname(self):
		# self.name = 'PB-' + self.new_item_code + ('-%.3i' % idx)

	def validate(self):
		self.validate_main_item()
		self.validate_child_items()
		self.validate_duplicate_packing_item()
		from erpnext.utilities.transaction_base import validate_uom_is_integer

		validate_uom_is_integer(self, "uom", "qty")

	def on_trash(self):
		linked_doctypes = [
			"Delivery Note",
			"Sales Invoice",
			"POS Invoice",
			"Purchase Receipt",
			"Purchase Invoice",
			"Stock Entry",
			"Stock Reconciliation",
			"Sales Order",
			"Purchase Order",
			"Material Request",
		]

		invoice_links = []
		for doctype in linked_doctypes:
			item_doctype = doctype + " Item"

			if doctype == "Stock Entry":
				item_doctype = doctype + " Detail"

			invoices = frappe.db.get_all(
				item_doctype, {"item_code": self.new_item_code, "docstatus": 1}, ["parent"]
			)

			for invoice in invoices:
				invoice_links.append(get_link_to_form(doctype, invoice["parent"]))

		if len(invoice_links):
			frappe.throw(
				"This Product Bundle is linked with {}. You will have to cancel these documents in order to delete this Product Bundle".format(
					", ".join(invoice_links)
				),
				title=_("Not Allowed"),
			)

	def validate_main_item(self):
		"""Validates, main Item is not a stock item"""
		if frappe.db.get_value("Item", self.new_item_code, "is_stock_item"):
			frappe.throw(_("Parent Item {0} must not be a Stock Item").format(self.new_item_code))
			
		if self.project:
			if frappe.db.sql("""select name from `tabProduct Bundle`
				where new_item_code = %s and name <> %s and project = %s""", (self.new_item_code,self.name,self.project)):
				frappe.throw(_("There is already a product bundle for this item and project").format(self.new_item_code,self.name,self.project))
			

		if frappe.db.get_value("Item", self.new_item_code, "is_fixed_asset"):
			frappe.throw(_("Parent Item {0} must not be a Fixed Asset").format(self.new_item_code))

	def validate_child_items(self):
		total_qty = 0
		total = 0
		for item in self.items:
			item.amount = flt(item.rate) * flt(item.qty)
			total += item.amount
			total_qty += item.qty

			if frappe.db.exists("Product Bundle", {"name": item.item_code, "disabled": 0}):
				frappe.throw(
					_(
						"Row #{0}: Child Item should not be a Product Bundle. Please remove Item {1} and Save"
					).format(item.idx, frappe.bold(item.item_code))
				)
		self.total_qty = total_qty
		self.total = total

	def validate_duplicate_packing_item(self):
		items = []
		for d in self.items:
			if d.item_code not in items:
				items.append(d.item_code)
			else:
				frappe.throw(_("The item {0} added multiple times")
					.format(frappe.bold(d.item_code)), title=_("Duplicate Item Error"))
					
	def get_item_det(self, item_code):
		item = get_item_details(item_code)

		if not item:
			frappe.throw(_("Item: {0} does not exist in the system").format(item_code))

		return item
		
	@frappe.whitelist()
	def get_bom_material_detail(self, args=None):
		"""Get raw material details like uom, desc and rate"""
		if not args:
			args = frappe.form_dict.get("args")

		if isinstance(args, str):
			import json

			args = json.loads(args)

		item = self.get_item_det(args["item_code"])

		args["bom_no"] = args["bom_no"] or item and cstr(item["default_bom"]) or ""
		args["transfer_for_manufacture"] = (
			cstr(args.get("include_item_in_manufacturing", ""))
			or item
			and item.include_item_in_manufacturing
			or 0
		)

		args.update(item)
		
		conversion_factor = get_conversion_factor(args['item_code'], args.get('uom') or args.get('stock_uom')).get("conversion_factor") or 1.0
		args['conversion_factor'] = conversion_factor
		

		rate = self.get_rm_rate(args)
		stock_rate = rate / conversion_factor

		from erpnext.stock.doctype.stock_entry.stock_entry import get_best_warehouse

		best_warehouse,enough_stock = get_best_warehouse(args["item_code"],args.get("stock_qty") or args.get("qty") or 1,company = self.company)

		ret_item = {
			"item_name": item and args["item_name"] or "",
			"description": item and args["description"] or "",
			"image": item and args["image"] or "",
			"stock_uom": item and args["stock_uom"] or "",
			"uom": item and args.get('uom') or args.get('stock_uom') or '',
			"conversion_factor": args['conversion_factor'],
			"bom_no": args["bom_no"],
			"rate": rate,
			"qty": args.get("qty") or args.get("stock_qty") or 1,
			"stock_qty": args.get("stock_qty") or args.get("qty") or 1,
			"base_rate": flt(rate) * (1),
			"include_item_in_manufacturing": cint(args.get("transfer_for_manufacture")),
			"sourced_by_supplier": args.get("sourced_by_supplier", 0),
			'stock_rate' : stock_rate,
			'base_stock_rate' : flt(stock_rate) * (1),
			'source_warehouse':best_warehouse,
		}

		if args.get("do_not_explode"):
			ret_item["bom_no"] = ""

		return ret_item
		
	def get_rm_rate(self, arg):
		"""Get raw material rate as per selected method, if bom exists takes bom cost"""
		rate = get_bom_item_rate(arg, self)
		return flt(rate) * flt(1) / (1)



@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_new_item_code(doctype, txt, searchfield, start, page_len, filters):
	product_bundles = frappe.db.get_list("Product Bundle", {"disabled": 0}, pluck="name")

	item = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(item)
		.select(item.item_code, item.item_name)
		.where((item.is_stock_item == 0) & (item.is_fixed_asset == 0) & (item[searchfield].like(f"%{txt}%")))
		.limit(page_len)
		.offset(start)
	)

	if product_bundles:
		query = query.where(item.name.notin(product_bundles))

	return query.run()
	
def has_product_bundle(item_code,project=None, item_row=None):
	if item_row and item_row.get("product_bundle"):
		return frappe.db.sql("""select name from `tabProduct Bundle`
			where name=%s and docstatus != 2""", item_row.product_bundle)
	elif project:	
		with_project = frappe.db.sql("""select name from `tabProduct Bundle` where new_item_code=%s and project=%s and docstatus != 2""", (item_code,project))
		if with_project:
			return with_project
		
	return frappe.db.sql("""select name from `tabProduct Bundle` where new_item_code=%s and project IS NULL and docstatus != 2""", item_code)

def get_product_bundle_details(name):
	return frappe.db.get_value("Product Bundle",name, ["use_total_to_cost", "total"], as_dict=1)
	
	
def get_bom_item_rate(args, bom_doc):
	rate = (
			flt(args.get("last_purchase_rate"))
			or flt(frappe.db.get_value("Item", args["item_code"], "last_purchase_rate"))
		) * (args.get("conversion_factor") or 1)

	return flt(rate)