# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
import frappe.defaults
from erpnext.controllers.selling_controller import SellingController
from erpnext.stock.doctype.batch.batch import set_batch_nos
from erpnext.stock.doctype.serial_no.serial_no import get_delivery_note_serial_no
from frappe import _
from frappe.contacts.doctype.address.address import get_company_address
from frappe.desk.notifications import clear_doctype_notifications
from frappe.model.mapper import get_mapped_doc
from frappe.model.utils import get_fetch_values
from frappe.utils import flt, cint, getdate,comma_and

form_grid_templates = {
	"items": "templates/form_grid/item_grid.html"
}

class DeliveryNote(SellingController):
	def __init__(self, *args, **kwargs):
		super(DeliveryNote, self).__init__(*args, **kwargs)
		self.status_updater = [{
			'source_dt': 'Delivery Note Item',
			'target_dt': 'Sales Order Item',
			'join_field': 'so_detail',
			'target_field': 'delivered_qty',
			'target_parent_dt': 'Sales Order',
			'target_parent_field': 'per_delivered',
			'target_ref_field': 'qty',
			'source_field': 'qty',
			'percent_join_field': 'against_sales_order',
			'status_field': 'delivery_status',
			'keyword': 'Delivered',
			'second_source_dt': 'Sales Invoice Item',
			'second_source_field': 'qty',
			'second_join_field': 'so_detail',
			'overflow_type': 'delivery',
			'second_source_extra_cond': """ and exists(select name from `tabSales Invoice`
				where name=`tabSales Invoice Item`.parent and update_stock = 1)"""
		},
		{
			'source_dt': 'Delivery Note Item',
			'target_dt': 'Sales Invoice Item',
			'join_field': 'si_detail',
			'target_field': 'delivered_qty',
			'target_parent_dt': 'Sales Invoice',
			'target_ref_field': 'qty',
			'source_field': 'qty',
			'percent_join_field': 'against_sales_invoice',
			'overflow_type': 'delivery',
			'no_tolerance': 1
		}]
		if cint(self.is_return):
			self.status_updater.append({
				'source_dt': 'Delivery Note Item',
				'target_dt': 'Sales Order Item',
				'join_field': 'so_detail',
				'target_field': 'returned_qty',
				'target_parent_dt': 'Sales Order',
				'source_field': '-1 * qty',
				'second_source_dt': 'Sales Invoice Item',
				'second_source_field': '-1 * qty',
				'second_join_field': 'so_detail',
				'extra_cond': """ and exists (select name from `tabDelivery Note`
					where name=`tabDelivery Note Item`.parent and is_return=1)""",
				'second_source_extra_cond': """ and exists (select name from `tabSales Invoice`
					where name=`tabSales Invoice Item`.parent and is_return=1 and update_stock=1)"""
			})

	def before_print(self):
		def toggle_print_hide(meta, fieldname):
			df = meta.get_field(fieldname)
			if self.get("print_without_amount"):
				df.set("__print_hide", 1)
			else:
				df.delete_key("__print_hide")

		item_meta = frappe.get_meta("Delivery Note Item")
		print_hide_fields = {
			"parent": ["grand_total", "rounded_total", "in_words", "currency", "total", "taxes"],
			"items": ["rate", "amount", "discount_amount", "price_list_rate", "discount_percentage"]
		}

		for key, fieldname in print_hide_fields.items():
			for f in fieldname:
				toggle_print_hide(self.meta if key == "parent" else item_meta, f)

		super(DeliveryNote, self).before_print()

	def set_actual_qty(self):
		for d in self.get('items'):
			if d.item_code and d.warehouse:
				actual_qty = frappe.db.sql("""select actual_qty from `tabBin`
					where item_code = %s and warehouse = %s""", (d.item_code, d.warehouse))
				d.actual_qty = actual_qty and flt(actual_qty[0][0]) or 0
				
	def set_total_qty(self):
		total_qty = 0
		for d in self.get('items'):
			total_qty = total_qty + flt(d.qty)
		self.total_qty = total_qty
		
	def so_required(self):
		"""check in manage account if sales order required or not"""
		if frappe.db.get_value("Selling Settings", None, 'so_required') == 'Yes':
			for d in self.get('items'):
				if not d.against_sales_order:
					frappe.throw(_("Sales Order required for Item {0}").format(d.item_code))

	def validate(self):
		self.validate_posting_time()
		super(DeliveryNote, self).validate()
		self.set_status()
		self.so_required()
		self.validate_proj_cust()
		self.check_close_sales_order("against_sales_order")
		self.validate_for_items()
		self.validate_warehouse()
		self.validate_uom_is_integer("stock_uom", "stock_qty")
		self.validate_uom_is_integer("uom", "qty")
		self.validate_with_previous_doc()

		if self._action != 'submit' and not self.is_return:
			set_batch_nos(self, 'warehouse', True)

		from erpnext.stock.doctype.packed_item.packed_item import make_packing_list
		make_packing_list(self)
		
		self.set_total_qty()

		self.update_current_stock()

		if not self.installation_status: self.installation_status = 'Not Installed'

	def validate_with_previous_doc(self):
		super(DeliveryNote, self).validate_with_previous_doc({
			"Sales Order": {
				"ref_dn_field": "against_sales_order",
				"compare_fields": [["customer", "="], ["company", "="], ["project", "="], ["currency", "="]]
			},
			"Sales Order Item": {
				"ref_dn_field": "so_detail",
				"compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
				"is_child_table": True,
				"allow_duplicate_prev_row_id": True
			},
			"Sales Invoice": {
				"ref_dn_field": "against_sales_invoice",
				"compare_fields": [["customer", "="], ["company", "="], ["project", "="], ["currency", "="]]
			},
			"Sales Invoice Item": {
				"ref_dn_field": "si_detail",
				"compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
				"is_child_table": True,
				"allow_duplicate_prev_row_id": True
			},
		})

		if cint(frappe.db.get_single_value('Selling Settings', 'maintain_same_sales_rate')) \
				and not self.is_return:
			self.validate_rate_with_reference_doc([["Sales Order", "against_sales_order", "so_detail"],
				["Sales Invoice", "against_sales_invoice", "si_detail"]])

	def validate_proj_cust(self):
		"""check for does customer belong to same project as entered.."""
		if self.project and self.customer:
			res = frappe.db.sql("""select name from `tabProject`
				where name = %s and (customer = %s or
					ifnull(customer,'')='')""", (self.project, self.customer))
			if not res:
				frappe.throw(_("Customer {0} does not belong to project {1}").format(self.customer, self.project))

	def validate_for_items(self):
		check_list, chk_dupl_itm = [], []
		if cint(frappe.db.get_single_value("Selling Settings", "allow_multiple_items")):
			return

		for d in self.get('items'):
			e = [d.item_code, d.description, d.warehouse, d.against_sales_order or d.against_sales_invoice, d.batch_no or '']
			f = [d.item_code, d.description, d.against_sales_order or d.against_sales_invoice]

			if frappe.db.get_value("Item", d.item_code, "is_stock_item") == 1:
				if e in check_list:
					frappe.msgprint(_("Note: Item {0} entered multiple times").format(d.item_code))
				else:
					check_list.append(e)
			else:
				if f in chk_dupl_itm:
					frappe.msgprint(_("Note: Item {0} entered multiple times").format(d.item_code))
				else:
					chk_dupl_itm.append(f)

	def validate_warehouse(self):
		super(DeliveryNote, self).validate_warehouse()

		for d in self.get_item_list():
			if frappe.db.get_value("Item", d['item_code'], "is_stock_item") == 1:
				if not d['warehouse']:
					frappe.throw(_("Warehouse required for stock Item {0}").format(d["item_code"]))


	def update_current_stock(self):
		if self.get("_action") and self._action != "update_after_submit":
			for d in self.get('items'):
				d.actual_qty = frappe.db.get_value("Bin", {"item_code": d.item_code,
					"warehouse": d.warehouse}, "actual_qty")

			for d in self.get('packed_items'):
				bin_qty = frappe.db.get_value("Bin", {"item_code": d.item_code,
					"warehouse": d.warehouse}, ["actual_qty", "projected_qty"], as_dict=True)
				if bin_qty:
					d.actual_qty = flt(bin_qty.actual_qty)
					d.projected_qty = flt(bin_qty.projected_qty)

	def on_submit(self):
	
		self.validate_packed_qty()

		# Check for Approving Authority
		frappe.get_doc('Authorization Control').validate_approving_authority(self.doctype, self.company, self.base_grand_total, self)

		# update delivered qty in sales order
		self.update_prevdoc_status()
		self.update_billing_status()

		if not self.is_return:
			self.check_credit_limit()
		elif self.issue_credit_note:
			self.make_return_invoice()
		# Updating stock ledger should always be called after updating prevdoc status,
		# because updating reserved qty in bin depends upon updated delivered qty in SO
		self.update_stock_ledger()
		self.make_gl_entries()

	def on_cancel(self):
		self.check_close_sales_order("against_sales_order")
		self.check_next_docstatus()

		self.update_prevdoc_status()
		self.update_billing_status()

		# Updating stock ledger should always be called after updating prevdoc status,
		# because updating reserved qty in bin depends upon updated delivered qty in SO
		self.update_stock_ledger()

		self.cancel_packing_slips()

		self.make_gl_entries_on_cancel()

	def check_credit_limit(self):
		from erpnext.selling.doctype.customer.customer import check_credit_limit

		extra_amount = 0
		validate_against_credit_limit = False
		bypass_credit_limit_check_at_sales_order = cint(frappe.db.get_value("Customer", self.customer,
			"bypass_credit_limit_check_at_sales_order"))
		if bypass_credit_limit_check_at_sales_order:
			validate_against_credit_limit = True
			extra_amount = self.base_grand_total
		else:
			for d in self.get("items"):
				if not (d.against_sales_order or d.against_sales_invoice):
					validate_against_credit_limit = True
					break

		if validate_against_credit_limit:
			check_credit_limit(self.customer, self.company,
				bypass_credit_limit_check_at_sales_order, extra_amount)

	def validate_packed_qty(self):
		"""
			Validate that if packed qty exists, it should be equal to qty
		"""
		if not any([flt(d.get('packed_qty')) for d in self.get("items")]):
			return
		has_error = False
		for d in self.get("items"):
			if flt(d.get('qty')) != flt(d.get('packed_qty')):
				frappe.msgprint(_("Packed quantity must equal quantity for Item {0} in row {1}").format(d.item_code, d.idx))
				has_error = True
		if has_error:
			raise frappe.ValidationError

	def check_next_docstatus(self):
		submit_rv = frappe.db.sql("""select t1.name
			from `tabSales Invoice` t1,`tabSales Invoice Item` t2
			where t1.name = t2.parent and t2.delivery_note = %s and t1.docstatus = 1""",
			(self.name))
		if submit_rv:
			frappe.throw(_("Sales Invoice {0} has already been submitted").format(submit_rv[0][0]))

		submit_in = frappe.db.sql("""select t1.name
			from `tabInstallation Note` t1, `tabInstallation Note Item` t2
			where t1.name = t2.parent and t2.prevdoc_docname = %s and t1.docstatus = 1""",
			(self.name))
		if submit_in:
			frappe.throw(_("Installation Note {0} has already been submitted").format(submit_in[0][0]))

	def cancel_packing_slips(self):
		"""
			Cancel submitted packing slips related to this delivery note
		"""
		res = frappe.db.sql("""SELECT name FROM `tabPacking Slip` WHERE delivery_note = %s
			AND docstatus = 1""", self.name)

		if res:
			for r in res:
				ps = frappe.get_doc('Packing Slip', r[0])
				ps.cancel()
			frappe.msgprint(_("Packing Slip(s) cancelled"))

	def update_status(self, status):
		self.set_status(update=True, status=status)
		self.notify_update()
		clear_doctype_notifications(self)

	def update_billing_status(self, update_modified=True):
		updated_delivery_notes = [self.name]
		for d in self.get("items"):
			if d.si_detail and not d.so_detail:
				d.db_set('billed_amt', d.amount, update_modified=update_modified)
			elif d.so_detail:
				updated_delivery_notes += update_billed_amount_based_on_so(d.so_detail, update_modified)

		for dn in set(updated_delivery_notes):
			dn_doc = self if (dn == self.name) else frappe.get_doc("Delivery Note", dn)
			dn_doc.update_billing_percentage(update_modified=update_modified)

		self.load_from_db()
		
	def submit_to_manufacture(self):
		self.make_stock_entries("Manufacture")
		
	def make_stock_entry_from_do(self,bom,purpose,sales_order_no=None,qty=None):
		from erpnext.stock.stock_ledger import NegativeStockError
		from erpnext.stock.doctype.stock_entry.stock_entry import IncorrectValuationRateError, \
			DuplicateEntryForProductionOrderError, OperationsNotCompleteError

		try:
			st = frappe.get_doc(self.make_stock_entry(bom, purpose,sales_order_no,qty))
			st.posting_date = frappe.flags.current_date
			for d in st.get("items"):
				d.cost_center = "Main - " + frappe.db.get_value('Company', st.company, 'abbr')
			st.insert()
			frappe.db.commit()
			
			return st.name

		except (NegativeStockError, IncorrectValuationRateError, DuplicateEntryForProductionOrderError,
			OperationsNotCompleteError):
			frappe.db.rollback()
			
	def make_stock_entry(self,bom,purpose,sales_order_no=None,qty=None):

		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = purpose
		stock_entry.sales_order = sales_order_no
		stock_entry.delivery_note_no = self.name

		stock_entry.company = self.company
		stock_entry.from_bom = 1
		stock_entry.bom_no = bom
		stock_entry.use_multi_level_bom = 1
		stock_entry.fg_completed_qty = qty

		if purpose=="Manufacture":
			# stock_entry.from_warehouse = production_order.wip_warehouse
			# stock_entry.to_warehouse = production_order.fg_warehouse
			stock_entry.project = self.project
			
			from erpnext.stock.doctype.stock_entry.stock_entry import get_additional_costs
			additional_costs = get_additional_costs(production_order, fg_qty=stock_entry.fg_completed_qty)
			stock_entry.set("additional_costs", additional_costs)
			
		else:
			# stock_entry.from_warehouse = production_order.source_warehouse
			# stock_entry.to_warehouse = production_order.wip_warehouse
			stock_entry.project = self.project

		
		stock_entry.get_items()
		return stock_entry.as_dict()
		
	def make_stock_entries(self,purpose=None,all=False):
		if purpose:
			conditions = ""
			ste_list = []

			for item in self.get('items'):
				bom = frappe.db.get_value("BOM", filters={"item": item.item_code, "project": self.project}) or frappe.db.get_value("BOM", filters={"item": item.item_code, "is_default": 1})
				if bom:
					if purpose == "Manufacture":
					
						stock_entries = frappe.db.sql("""select name 
						from `tabStock Entry` where delivery_note_no=%s and docstatus=0 and purpose=%s and bom_no = %s""",(self.name,purpose,bom), as_dict=1)
						if not stock_entries:
							ste_name = self.make_stock_entry_from_do(bom, purpose,item.against_sales_order,item.qty)
							if ste_name:
								ste_list.append(ste_name)
							
					else:
						stock_entries = frappe.db.sql("""select name 
						from `tabStock Entry` where delivery_note_no=%s and docstatus=0 and purpose=%s and bom_no = %s""",(self.name,purpose,bom), as_dict=1)
						
						if not stock_entries:
							ste_name = self.make_stock_entry_from_do(bom, purpose,item.against_sales_order,item.qty)
							if ste_name:
								ste_list.append(ste_name)
				
				
				
			if ste_list:
				ste_list = ["""<a href="#Form/Stock Entry/%s" target="_blank">%s</a>""" % \
					(p, p) for p in ste_list]
				msgprint(_("{0} created for {1}").format(comma_and(ste_list),purpose))
			else :
				msgprint(_("No Stock Entries Created for {0}").format(purpose))			
			

	def submit_stock_entries(self,purpose=None,all=False):
		if purpose:
			ste_list = []
			for d in self.get('items'):
				bom = frappe.db.get_value("BOM", filters={"item": item.item_code, "project": self.project}) or frappe.db.get_value("BOM", filters={"item": item.item_code, "is_default": 1})
				if bom:
					if purpose == "Manufacture":
						stock_entries = frappe.db.sql("""select name 
						from `tabStock Entry` where delivery_note_no=%s and docstatus=0 and purpose=%s and bom_no = %s""",(self.name,purpose,bom), as_dict=1)
						
						for ste in stock_entries:
							doc = frappe.get_doc('Stock Entry', ste["name"])
							doc.submit()
							ste_list.append(doc.name)
					else:
						stock_entries = frappe.db.sql("""select name 
						from `tabStock Entry` where delivery_note_no=%s and docstatus=0 and purpose=%s and bom_no = %s""",(self.name,purpose,bom), as_dict=1)
						
						for ste in stock_entries:
							doc = frappe.get_doc('Stock Entry', ste["name"])
							doc.submit()
							ste_list.append(doc.name)

				
					
			if ste_list:
				ste_list = ["""<a href="#Form/Stock Entry/%s" target="_blank">%s</a>""" % \
					(p, p) for p in ste_list]
				msgprint(_("{0} submitted for {1}").format(comma_and(ste_list),purpose))
			else :
				msgprint(_("No Stock Entries Submitted for {0}").format(purpose))
						

	def make_return_invoice(self):
		try:
			return_invoice = make_sales_invoice(self.name)
			return_invoice.is_return = True
			return_invoice.save()
			return_invoice.submit()
			frappe.msgprint(_("Credit Note {0} has been created automatically").format(return_invoice.name))
		except:
			frappe.throw(_("Could not create Credit Note automatically, please uncheck 'Issue Credit Note' and submit again"))

def update_billed_amount_based_on_so(so_detail, update_modified=True):
	# Billed against Sales Order directly
	billed_against_so = frappe.db.sql("""select sum(amount) from `tabSales Invoice Item`
		where so_detail=%s and (dn_detail is null or dn_detail = '') and docstatus=1""", so_detail)
	billed_against_so = billed_against_so and billed_against_so[0][0] or 0

	# Get all Delivery Note Item rows against the Sales Order Item row
	dn_details = frappe.db.sql("""select dn_item.name, dn_item.amount, dn_item.si_detail, dn_item.parent
		from `tabDelivery Note Item` dn_item, `tabDelivery Note` dn
		where dn.name=dn_item.parent and dn_item.so_detail=%s
			and dn.docstatus=1 and dn.is_return = 0
		order by dn.posting_date asc, dn.posting_time asc, dn.name asc""", so_detail, as_dict=1)

	updated_dn = []
	for dnd in dn_details:
		billed_amt_agianst_dn = 0

		# If delivered against Sales Invoice
		if dnd.si_detail:
			billed_amt_agianst_dn = flt(dnd.amount)
			billed_against_so -= billed_amt_agianst_dn
		else:
			# Get billed amount directly against Delivery Note
			billed_amt_agianst_dn = frappe.db.sql("""select sum(amount) from `tabSales Invoice Item`
				where dn_detail=%s and docstatus=1""", dnd.name)
			billed_amt_agianst_dn = billed_amt_agianst_dn and billed_amt_agianst_dn[0][0] or 0

		# Distribute billed amount directly against SO between DNs based on FIFO
		if billed_against_so and billed_amt_agianst_dn < dnd.amount:
			pending_to_bill = flt(dnd.amount) - billed_amt_agianst_dn
			if pending_to_bill <= billed_against_so:
				billed_amt_agianst_dn += pending_to_bill
				billed_against_so -= pending_to_bill
			else:
				billed_amt_agianst_dn += billed_against_so
				billed_against_so = 0

		frappe.db.set_value("Delivery Note Item", dnd.name, "billed_amt", billed_amt_agianst_dn, update_modified=update_modified)

		updated_dn.append(dnd.parent)

	return updated_dn

def get_list_context(context=None):
	from erpnext.controllers.website_list_for_contact import get_list_context
	list_context = get_list_context(context)
	list_context.update({
		'show_sidebar': True,
		'show_search': True,
		'no_breadcrumbs': True,
		'title': _('Shipments'),
	})
	return list_context

def get_invoiced_qty_map(delivery_note):
	"""returns a map: {dn_detail: invoiced_qty}"""
	invoiced_qty_map = {}

	for dn_detail, qty in frappe.db.sql("""select dn_detail, qty from `tabSales Invoice Item`
		where delivery_note=%s and docstatus=1""", delivery_note):
			if not invoiced_qty_map.get(dn_detail):
				invoiced_qty_map[dn_detail] = 0
			invoiced_qty_map[dn_detail] += qty

	return invoiced_qty_map

def get_returned_qty_map(delivery_note):
	"""returns a map: {so_detail: returned_qty}"""
	returned_qty_map = frappe._dict(frappe.db.sql("""select dn_item.item_code, sum(abs(dn_item.qty)) as qty
		from `tabDelivery Note Item` dn_item, `tabDelivery Note` dn
		where dn.name = dn_item.parent
			and dn.docstatus = 1
			and dn.is_return = 1
			and dn.return_against = %s
		group by dn_item.item_code
	""", delivery_note))

	return returned_qty_map

@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
	doc = frappe.get_doc('Delivery Note', source_name)

	to_make_invoice_qty_map = {}
	returned_qty_map = get_returned_qty_map(source_name)
	invoiced_qty_map = get_invoiced_qty_map(source_name)


	def set_missing_values(source, target):
		if source.project:
			target.project = source.project
		if source.room_qty:
			target.room_qty = source.room_qty
		if source.sub_project:
			target.sub_project = source.sub_project
		target.is_pos = 0
		target.ignore_pricing_rule = 1
		target.run_method("set_missing_values")
		target.run_method("set_po_nos")

		if len(target.get("items")) == 0:
			frappe.throw(_("All these items have already been invoiced"))

		target.run_method("calculate_taxes_and_totals")

		# set company address
		target.update(get_company_address(target.company))
		if target.company_address:
			target.update(get_fetch_values("Sales Invoice", 'company_address', target.company_address))

	def update_item(source_doc, target_doc, source_parent):
		target_doc.qty = to_make_invoice_qty_map[source_doc.name]

		if source_doc.serial_no and source_parent.per_billed > 0:
			target_doc.serial_no = get_delivery_note_serial_no(source_doc.item_code,
				target_doc.qty, source_parent.name)

	def get_pending_qty(item_row):
		pending_qty = item_row.qty - invoiced_qty_map.get(item_row.name, 0)

		returned_qty = 0
		if returned_qty_map.get(item_row.item_code, 0) > 0:
			returned_qty = flt(returned_qty_map.get(item_row.item_code, 0))
			returned_qty_map[item_row.item_code] -= pending_qty

		if returned_qty:
			if returned_qty >= pending_qty:
				pending_qty = 0
				returned_qty -= pending_qty
			else:
				pending_qty -= returned_qty
				returned_qty = 0

		to_make_invoice_qty_map[item_row.name] = pending_qty

		return pending_qty

	doc = get_mapped_doc("Delivery Note", source_name, {
		"Delivery Note": {
			"doctype": "Sales Invoice",
			"validation": {
				"docstatus": ["=", 1]
			}
		},
		"Delivery Note Item": {
			"doctype": "Sales Invoice Item",
			"field_map": {
				"name": "dn_detail",
				"parent": "delivery_note",
				"so_detail": "so_detail",
				"against_sales_order": "sales_order",
				"serial_no": "serial_no",
				"cost_center": "cost_center"
			},
			"postprocess": update_item,
			"filter": lambda d: get_pending_qty(d) <= 0 if not doc.get("is_return") else get_pending_qty(d) > 0
		},
		"Sales Taxes and Charges": {
			"doctype": "Sales Taxes and Charges",
			"add_if_empty": True
		},
		"Sales Team": {
			"doctype": "Sales Team",
			"field_map": {
				"incentives": "incentives"
			},
			"add_if_empty": True
		}
	}, target_doc, set_missing_values)

	return doc

@frappe.whitelist()
def make_delivery_trip(source_name, target_doc=None):
	def update_stop_details(source_doc, target_doc, source_parent):
		target_doc.customer = source_parent.customer
		target_doc.address = source_parent.shipping_address_name
		target_doc.customer_address = source_parent.shipping_address
		target_doc.contact = source_parent.contact_person
		target_doc.customer_contact = source_parent.contact_display
		target_doc.grand_total = source_parent.grand_total

		# Append unique Delivery Notes in Delivery Trip
		delivery_notes.append(target_doc.delivery_note)

	delivery_notes = []

	doclist = get_mapped_doc("Delivery Note", source_name, {
		"Delivery Note": {
			"doctype": "Delivery Trip",
			"validation": {
				"docstatus": ["=", 1]
			}
		},
		"Delivery Note Item": {
			"doctype": "Delivery Stop",
			"field_map": {
				"parent": "delivery_note"
			},
			"condition": lambda item: item.parent not in delivery_notes,
			"postprocess": update_stop_details
		}
	}, target_doc)

	return doclist

@frappe.whitelist()
def make_installation_note(source_name, target_doc=None):
	def update_item(obj, target, source_parent):
		target.qty = flt(obj.qty) - flt(obj.installed_qty)
		target.serial_no = obj.serial_no

	doclist = get_mapped_doc("Delivery Note", source_name, 	{
		"Delivery Note": {
			"doctype": "Installation Note",
			"validation": {
				"docstatus": ["=", 1]
			}
		},
		"Delivery Note Item": {
			"doctype": "Installation Note Item",
			"field_map": {
				"name": "prevdoc_detail_docname",
				"parent": "prevdoc_docname",
				"parenttype": "prevdoc_doctype",
			},
			"postprocess": update_item,
			"condition": lambda doc: doc.installed_qty < doc.qty
		}
	}, target_doc)

	return doclist

@frappe.whitelist()
def make_packing_slip(source_name, target_doc=None):
	doclist = get_mapped_doc("Delivery Note", source_name, 	{
		"Delivery Note": {
			"doctype": "Packing Slip",
			"field_map": {
				"name": "delivery_note",
				"letter_head": "letter_head"
			},
			"validation": {
				"docstatus": ["=", 0]
			}
		}
	}, target_doc)

	return doclist


@frappe.whitelist()
def make_sales_return(source_name, target_doc=None):
	from erpnext.controllers.sales_and_purchase_return import make_return_doc
	return make_return_doc("Delivery Note", source_name, target_doc)


@frappe.whitelist()
def update_delivery_note_status(docname, status):
	dn = frappe.get_doc("Delivery Note", docname)
	dn.update_status(status)
	

		
@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None):
	def update_item(obj, target, source_parent):
		# target.qty = flt(obj.qty) - flt(obj.received_qty)
		# target.stock_qty = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.conversion_factor)
		# target.amount = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate)
		# target.base_amount = (flt(obj.qty) - flt(obj.received_qty)) * \
			# flt(obj.rate) * flt(source_parent.conversion_rate)
		target.project = source_parent.project
		
	def update_target_doc(obj, target, source_parent):
		pass
	
	def set_missing_values(source, target):
		target.supplier = source.company
		target.supplier_delivery_note = source.name
		
		target.company = source.customer
		
		
		target.shipping_address = source.shipping_address_name
		target.title = source.title
		
		target.ignore_pricing_rule = 1
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

		

		
		if not target.company == source.company:
			from erpnext.stock.utils import get_default_warehouse

			default_warehouse = get_default_warehouse(company = target.company).get("source_warehouse")

			for d in target.get("items"):
				d.warehouse = default_warehouse 
		
		target.flags.ignore_permissions = True
		target.insert()

	doc = get_mapped_doc("Delivery Note", source_name,	{
		"Delivery Note": {
			"doctype": "Purchase Receipt",
			"field_map": {
				# "per_billed": "per_billed"
			},
			"validation": {
				"docstatus": ["=", 1],
			}
		},
		"Delivery Note Item": {
			"doctype": "Purchase Receipt Item",
			# "field_map": {
				# "name": "delivery_note_item",
				# "parent": "delivery_note"
			# },
			"postprocess": update_item
		},
		"Sales Taxes and Charges": {
			"doctype": "Purchase Taxes and Charges",
			"add_if_empty": True
		}
	}, target_doc, set_missing_values)

	return doc
	
@frappe.whitelist()
def make_transfer_dn(company,customer,source_name,project=None):
	try:
		current_dn = frappe.get_doc("Delivery Note", source_name)

		new_dn = frappe.copy_doc(current_dn, ignore_no_copy=True)
		
		new_dn.company = company
		new_dn.company_trn = frappe.db.get_value("Company",company,"tax_id")
		
		new_dn.customer = customer
		new_dn.project = project
		
		from erpnext.selling.doctype.customer.customer import get_customer_details
		from frappe.contacts.doctype.address.address import get_default_address,get_address_display
		
		customer_details = get_customer_details(customer)
		
		if customer_details:
			new_dn.tax_id = customer_details.tax_id
			new_dn.customer_name_in_arabic = customer_details.customer_name_in_arabic
		
		new_dn.shipping_address_name = get_default_address('Customer', customer)
		new_dn.shipping_address = get_address_display(new_dn.shipping_address_name)
		new_dn.customer_address = get_default_address('Customer', customer)
		new_dn.address_display = get_address_display(new_dn.customer_address)

		if not new_dn.company == current_dn.company:
			from erpnext.stock.utils import get_default_warehouse

			default_warehouse = get_default_warehouse(company = new_dn.company).get("source_warehouse")

			for d in new_dn.get("items"):
				d.warehouse = default_warehouse 
		
		new_dn.insert(ignore_permissions=True)

		return new_dn.name
	
	except:
		return False

	


