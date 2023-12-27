# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


from datetime import date

import frappe
from frappe import _, bold
from frappe.core.doctype.role.role import get_users
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, formatdate, get_datetime, getdate

from typing import Any, Dict, List, Optional, TypedDict
from frappe.query_builder import Order
from frappe.query_builder.functions import Coalesce, CombineDatetime
from frappe.utils.nestedset import get_descendants_of

from erpnext.accounts.utils import get_fiscal_year
from erpnext.controllers.item_variant import ItemTemplateCannotHaveStock
from erpnext.stock.doctype.inventory_dimension.inventory_dimension import get_inventory_dimensions
from erpnext.stock.stock_ledger import get_previous_sle


class StockFreezeError(frappe.ValidationError):
	pass


class BackDatedStockTransaction(frappe.ValidationError):
	pass


exclude_from_linked_with = True


class StockLedgerEntry(Document):
	def autoname(self):
		"""
		Temporarily name doc for fast insertion
		name will be changed using autoname options (in a scheduled job)
		"""
		self.name = frappe.generate_hash(txt="", length=10)
		if self.meta.autoname == "hash":
			self.to_rename = 0

	def validate(self):
		self.flags.ignore_submit_comment = True
		from erpnext.stock.utils import validate_disabled_warehouse, validate_warehouse_company

		self.validate_mandatory()
		self.validate_item()
		self.validate_batch()
		validate_disabled_warehouse(self.warehouse)
		validate_warehouse_company(self.warehouse, self.company)
		self.scrub_posting_time()
		self.validate_and_set_fiscal_year()
		self.block_transactions_against_group_warehouse()
		self.validate_with_last_transaction_posting_time()
		self.validate_inventory_dimension_negative_stock()

	def validate_inventory_dimension_negative_stock(self):
		extra_cond = ""
		kwargs = {}

		dimensions = self._get_inventory_dimensions()
		if not dimensions:
			return

		for dimension, values in dimensions.items():
			kwargs[dimension] = values.get("value")
			extra_cond += f" and {dimension} = %({dimension})s"

		kwargs.update(
			{
				"item_code": self.item_code,
				"warehouse": self.warehouse,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"company": self.company,
			}
		)

		sle = get_previous_sle(kwargs, extra_cond=extra_cond)
		if sle:
			flt_precision = cint(frappe.db.get_default("float_precision")) or 2
			diff = sle.qty_after_transaction + flt(self.actual_qty)
			diff = flt(diff, flt_precision)
			if diff < 0 and abs(diff) > 0.0001:
				self.throw_validation_error(diff, dimensions)
				
		
		dimension_balance = mrp_get_stock_balance_with_dimension(kwargs)
		if dimension_balance:
			flt_precision = cint(frappe.db.get_default("float_precision")) or 2
			diff = dimension_balance.bal_qty + flt(self.actual_qty)
			diff = flt(diff, flt_precision)
			if diff < 0 and abs(diff) > 0.0001:
				self.throw_validation_error_mrp(diff, dimension_balance.bal_qty, dimensions)
		elif self.actual_qty < 0:
			self.throw_validation_error_mrp(flt(self.actual_qty),0, dimensions)
	
	def throw_validation_error(self, diff, dimensions):
		dimension_msg = _(", with the inventory {0}: {1}").format(
			"dimensions" if len(dimensions) > 1 else "dimension",
			", ".join(f"{bold(d.doctype)} ({d.value})" for k, d in dimensions.items()),
		)

		msg = _(
			"{0} units of {1} are required in {2}{3}, on {4} {5} for {6} to complete the transaction."
		).format(
			abs(diff),
			frappe.get_desk_link("Item", self.item_code),
			frappe.get_desk_link("Warehouse", self.warehouse),
			dimension_msg,
			self.posting_date,
			self.posting_time,
			frappe.get_desk_link(self.voucher_type, self.voucher_no),
		)

		frappe.throw(msg, title=_("Inventory Dimension Negative Stock"))
	
	def throw_validation_error_mrp(self, diff, balance, dimensions):
		dimension_msg = _(", with the inventory {0}: {1}").format(
			"dimensions" if len(dimensions) > 1 else "dimension",
			", ".join(f"{bold(d.doctype)} ({d.value})" for k, d in dimensions.items()),
		)

		msg = _(
			"{0} units of {1} are required in {2}{3}, on {4} {5} for {6} to complete the transaction. Current Balance Is {7}"
		).format(
			abs(diff),
			frappe.get_desk_link("Item", self.item_code),
			frappe.get_desk_link("Warehouse", self.warehouse),
			dimension_msg,
			self.posting_date,
			self.posting_time,
			frappe.get_desk_link(self.voucher_type, self.voucher_no),
			balance
		)

		frappe.throw(msg, title=_("Inventory Dimension Negative Stock"))

	def _get_inventory_dimensions(self):
		inv_dimensions = get_inventory_dimensions()
		inv_dimension_dict = {}
		for dimension in inv_dimensions:
			if not dimension.get("validate_negative_stock") or not self.get(dimension.fieldname):
				continue

			dimension["value"] = self.get(dimension.fieldname)
			inv_dimension_dict.setdefault(dimension.fieldname, dimension)

		return inv_dimension_dict

	def on_submit(self):
		self.check_stock_frozen_date()
		self.calculate_batch_qty()

		if not self.get("via_landed_cost_voucher"):
			from erpnext.stock.doctype.serial_no.serial_no import process_serial_no

			process_serial_no(self)

	def calculate_batch_qty(self):
		if self.batch_no:
			batch_qty = (
				frappe.db.get_value(
					"Stock Ledger Entry",
					{"docstatus": 1, "batch_no": self.batch_no, "is_cancelled": 0},
					"sum(actual_qty)",
				)
				or 0
			)
			frappe.db.set_value("Batch", self.batch_no, "batch_qty", batch_qty)

	def validate_mandatory(self):
		mandatory = ["warehouse", "posting_date", "voucher_type", "voucher_no", "company"]
		for k in mandatory:
			if not self.get(k):
				frappe.throw(_("{0} is required").format(self.meta.get_label(k)))

		if self.voucher_type != "Stock Reconciliation" and not self.actual_qty:
			frappe.throw(_("Actual Qty is mandatory"))

	def validate_item(self):
		item_det = frappe.db.sql(
			"""select name, item_name, has_batch_no, docstatus,
			is_stock_item, has_variants, stock_uom, create_new_batch
			from tabItem where name=%s""",
			self.item_code,
			as_dict=True,
		)

		if not item_det:
			frappe.throw(_("Item {0} not found").format(self.item_code))

		item_det = item_det[0]

		if item_det.is_stock_item != 1:
			frappe.throw(_("Item {0} must be a stock Item").format(self.item_code))

		# check if batch number is valid
		if item_det.has_batch_no == 1:
			batch_item = (
				self.item_code
				if self.item_code == item_det.item_name
				else self.item_code + ":" + item_det.item_name
			)
			if not self.batch_no:
				frappe.throw(_("Batch number is mandatory for Item {0}").format(batch_item))
			elif not frappe.db.get_value("Batch", {"item": self.item_code, "name": self.batch_no}):
				frappe.throw(
					_("{0} is not a valid Batch Number for Item {1}").format(self.batch_no, batch_item)
				)

		elif item_det.has_batch_no == 0 and self.batch_no and self.is_cancelled == 0:
			frappe.throw(_("The Item {0} cannot have Batch").format(self.item_code))

		if item_det.has_variants:
			frappe.throw(
				_("Stock cannot exist for Item {0} since has variants").format(self.item_code),
				ItemTemplateCannotHaveStock,
			)

		self.stock_uom = item_det.stock_uom

	def check_stock_frozen_date(self):
		stock_settings = frappe.get_cached_doc("Stock Settings")

		if stock_settings.stock_frozen_upto:
			if (
				getdate(self.posting_date) <= getdate(stock_settings.stock_frozen_upto)
				and stock_settings.stock_auth_role not in frappe.get_roles()
			):
				frappe.throw(
					_("Stock transactions before {0} are frozen").format(
						formatdate(stock_settings.stock_frozen_upto)
					),
					StockFreezeError,
				)

		stock_frozen_upto_days = cint(stock_settings.stock_frozen_upto_days)
		if stock_frozen_upto_days:
			older_than_x_days_ago = (
				add_days(getdate(self.posting_date), stock_frozen_upto_days) <= date.today()
			)
			if older_than_x_days_ago and stock_settings.stock_auth_role not in frappe.get_roles():
				frappe.throw(
					_("Not allowed to update stock transactions older than {0}").format(stock_frozen_upto_days),
					StockFreezeError,
				)

	def scrub_posting_time(self):
		if not self.posting_time or self.posting_time == "00:0":
			self.posting_time = "00:00"

	def validate_batch(self):
		if self.batch_no and self.voucher_type != "Stock Entry":
			if (self.voucher_type in ["Purchase Receipt", "Purchase Invoice"] and self.actual_qty < 0) or (
				self.voucher_type in ["Delivery Note", "Sales Invoice"] and self.actual_qty > 0
			):
				return

			expiry_date = frappe.db.get_value("Batch", self.batch_no, "expiry_date")
			if expiry_date:
				if getdate(self.posting_date) > getdate(expiry_date):
					frappe.throw(_("Batch {0} of Item {1} has expired.").format(self.batch_no, self.item_code))

	def validate_and_set_fiscal_year(self):
		if not self.fiscal_year:
			self.fiscal_year = get_fiscal_year(self.posting_date, company=self.company)[0]
		else:
			from erpnext.accounts.utils import validate_fiscal_year

			validate_fiscal_year(
				self.posting_date, self.fiscal_year, self.company, self.meta.get_label("posting_date"), self
			)

	def block_transactions_against_group_warehouse(self):
		from erpnext.stock.utils import is_group_warehouse

		is_group_warehouse(self.warehouse)

	def validate_with_last_transaction_posting_time(self):
		authorized_role = frappe.db.get_single_value(
			"Stock Settings", "role_allowed_to_create_edit_back_dated_transactions"
		)
		if authorized_role:
			authorized_users = get_users(authorized_role)
			if authorized_users and frappe.session.user not in authorized_users:
				last_transaction_time = frappe.db.sql(
					"""
					select MAX(timestamp(posting_date, posting_time)) as posting_time
					from `tabStock Ledger Entry`
					where docstatus = 1 and is_cancelled = 0 and item_code = %s
					and warehouse = %s""",
					(self.item_code, self.warehouse),
				)[0][0]

				cur_doc_posting_datetime = "%s %s" % (
					self.posting_date,
					self.get("posting_time") or "00:00:00",
				)

				if last_transaction_time and get_datetime(cur_doc_posting_datetime) < get_datetime(
					last_transaction_time
				):
					msg = _("Last Stock Transaction for item {0} under warehouse {1} was on {2}.").format(
						frappe.bold(self.item_code), frappe.bold(self.warehouse), frappe.bold(last_transaction_time)
					)

					msg += "<br><br>" + _(
						"You are not authorized to make/edit Stock Transactions for Item {0} under warehouse {1} before this time."
					).format(frappe.bold(self.item_code), frappe.bold(self.warehouse))

					msg += "<br><br>" + _("Please contact any of the following users to {} this transaction.")
					msg += "<br>" + "<br>".join(authorized_users)
					frappe.throw(msg, BackDatedStockTransaction, title=_("Backdated Stock Entry"))

	def on_cancel(self):
		msg = _("Individual Stock Ledger Entry cannot be cancelled.")
		msg += "<br>" + _("Please cancel related transaction.")
		frappe.throw(msg)


def on_doctype_update():
	frappe.db.add_index(
		"Stock Ledger Entry", fields=["posting_date", "posting_time"], index_name="posting_sort_index"
	)
	frappe.db.add_index("Stock Ledger Entry", ["voucher_no", "voucher_type"])
	frappe.db.add_index("Stock Ledger Entry", ["batch_no", "item_code", "warehouse"])
	frappe.db.add_index("Stock Ledger Entry", ["warehouse", "item_code"], "item_warehouse")


def mrp_get_stock_balance_with_dimension(args):
	to_date = getdate(args.get("posting_date"))
	from_date = to_date
	args["to_date"] = to_date
	args["from_date"] = from_date
	company = args.get("company")
	args["float_precision"] = cint(frappe.db.get_default("float_precision")) or 3
	args["inventory_dimensions"] = get_inventory_dimension_fields()
	

	start_from = None
	args["start_from"] = start_from
	
	data = None
	
	from erpnext import get_company_currency
	args["company_currency"] = get_company_currency(company)
	
			
	sle_entries: List[SLEntry] = []
	
	opening_data = frappe._dict({})
	closing_balance = get_closing_balance(args)
	if closing_balance:
		start_from = add_days(closing_balance[0].to_date, 1)
		args["start_from"] = start_from

		res = frappe.get_doc("Closing Stock Balance", closing_balance[0].name).get_prepared_data()

		for entry in res.data:
			entry = frappe._dict(entry)

			group_by_key = get_group_by_key(args, entry)
			if group_by_key not in opening_data:
				opening_data.setdefault(group_by_key, entry)
			
	args["opening_data"] = opening_data
	
	sle_entries = prepare_stock_ledger_entries(args)
	
	if sle_entries:
		item_warehouse_map = get_item_warehouse_map(args, sle_entries)
		data = prepare_new_data(item_warehouse_map)
	
	if data and len(data)>0:
		return data[0]
	else:
		return None
	
def get_inventory_dimension_fields():
	return [dimension.fieldname for dimension in get_inventory_dimensions()]
		
def get_closing_balance(args) -> List[Dict[str, Any]]:
	from_date = args.get("from_date")
	company = args.get("company")
	
	
	table = frappe.qb.DocType("Closing Stock Balance")

	query = (
		frappe.qb.from_(table)
		.select(table.name, table.to_date)
		.where(
			(table.docstatus == 1)
			& (table.company == company)
			& ((table.to_date <= from_date))
		)
		.orderby(table.to_date, order=Order.desc)
		.limit(1)
	)

	for fieldname in ["warehouse", "item_code", "item_group", "warehouse_type"]:
		if args.get(fieldname):
			query = query.where(table[fieldname] == args.get(fieldname))

	return query.run(as_dict=True)
	
def get_group_by_key(args,row) -> tuple:
	group_by_key = [row.company, row.item_code, row.warehouse]
	inventory_dimensions = args.get("inventory_dimensions")
	for fieldname in inventory_dimensions:
		if args.get(fieldname):
			group_by_key.append(row.get(fieldname))

	return tuple(group_by_key)
		
def prepare_stock_ledger_entries(args):
	sle = frappe.qb.DocType("Stock Ledger Entry")
	item_table = frappe.qb.DocType("Item")

	query = (
		frappe.qb.from_(sle)
		.inner_join(item_table)
		.on(sle.item_code == item_table.name)
		.select(
			sle.item_code,
			sle.warehouse,
			sle.posting_date,
			sle.actual_qty,
			sle.valuation_rate,
			sle.company,
			sle.voucher_type,
			sle.qty_after_transaction,
			sle.stock_value_difference,
			sle.item_code.as_("name"),
			sle.voucher_no,
			sle.stock_value,
			sle.batch_no,
			sle.serial_no,
			item_table.item_group,
			item_table.stock_uom,
			item_table.item_name,
		)
		.where((sle.docstatus < 2) & (sle.is_cancelled == 0))
		.orderby(CombineDatetime(sle.posting_date, sle.posting_time))
		.orderby(sle.creation)
		.orderby(sle.actual_qty)
	)

	query = apply_inventory_dimensions_filters(args, query, sle)
	query = apply_warehouse_filters(args, query, sle)
	query = apply_items_filters(args, query, item_table)
	query = apply_date_filters(args, query, sle)
	query = query.where(sle.company == args.get("company"))

	return query.run(as_dict=True)
	
def apply_inventory_dimensions_filters(args, query, sle) -> str:
	inventory_dimension_fields = get_inventory_dimension_fields()
	if inventory_dimension_fields:
		for fieldname in inventory_dimension_fields:
			query = query.select(fieldname)
			if args.get(fieldname):
				query = query.where(sle[fieldname] == args.get(fieldname))

	return query

def apply_warehouse_filters(args, query, sle) -> str:
	warehouse_table = frappe.qb.DocType("Warehouse")
	from erpnext.stock.doctype.warehouse.warehouse import apply_warehouse_filter

	if args.get("warehouse"):
		query = apply_warehouse_filter(query, sle, args)
	elif warehouse_type := args.get("warehouse_type"):
		query = (
			query.join(warehouse_table)
			.on(warehouse_table.name == sle.warehouse)
			.where(warehouse_table.warehouse_type == warehouse_type)
		)

	return query

def apply_items_filters(args, query, item_table) -> str:
	if item_group := args.get("item_group"):
		children = get_descendants_of("Item Group", item_group, ignore_permissions=True)
		query = query.where(item_table.item_group.isin(children + [item_group]))

	for field in ["item_code", "brand"]:
		if not args.get(field):
			continue
		elif field == "item_code":
			query = query.where(item_table.name == args.get(field))
		else:
			query = query.where(item_table[field] == args.get(field))

	return query

def apply_date_filters(args, query, sle) -> str:
	if not args.get("ignore_closing_balance") and args.get("start_from"):
		query = query.where(sle.posting_date >= args.get("start_from"))

	if args.get("to_date"):
		query = query.where(sle.posting_date <= args.get("to_date"))

	return query

def prepare_new_data(item_warehouse_map):
	data = []

	variant_values = {}
	for key, report_data in item_warehouse_map.items():
		if variant_data := variant_values.get(report_data.item_code):
			report_data.update(variant_data)

		data.append(report_data)
		
	return data
	
def get_item_warehouse_map(args, sle_entries):
	item_warehouse_map = {}
	args["opening_vouchers"] = get_opening_vouchers(args)
	inventory_dimensions = args.get("inventory_dimensions")
	float_precision = args.get("float_precision")
	opening_data = args["opening_data"]

	for entry in sle_entries:
		group_by_key = get_group_by_key(args, entry)
		if group_by_key not in item_warehouse_map:
			initialize_data(args,item_warehouse_map, group_by_key, entry)

		prepare_item_warehouse_map(args,item_warehouse_map, entry, group_by_key)

		if opening_data.get(group_by_key):
			del opening_data[group_by_key]

	for group_by_key, entry in opening_data.items():
		if group_by_key not in item_warehouse_map:
			initialize_data(args,item_warehouse_map, group_by_key, entry)

	item_warehouse_map = filter_items_with_no_transactions(
		item_warehouse_map, float_precision, inventory_dimensions
	)

	return item_warehouse_map
	
def prepare_item_warehouse_map(args, item_warehouse_map, entry, group_by_key):
	inventory_dimensions = args.get("inventory_dimensions")
	from_date = args.get("from_date")
	float_precision = args.get("float_precision")
	opening_vouchers = args.get("opening_vouchers")
	to_date = args.get("to_date")

	qty_dict = item_warehouse_map[group_by_key]
	for field in inventory_dimensions:
		qty_dict[field] = entry.get(field)

	if entry.voucher_type == "Stock Reconciliation" and (not entry.batch_no or entry.serial_no):
		qty_diff = flt(entry.qty_after_transaction) - flt(qty_dict.bal_qty)
	else:
		qty_diff = flt(entry.actual_qty)

	value_diff = flt(entry.stock_value_difference)

	if entry.posting_date < from_date or entry.voucher_no in opening_vouchers.get(
		entry.voucher_type, []
	):
		qty_dict.opening_qty += qty_diff
		qty_dict.opening_val += value_diff

	elif entry.posting_date >= from_date and entry.posting_date <= to_date:

		if flt(qty_diff, float_precision) >= 0:
			qty_dict.in_qty += qty_diff
			qty_dict.in_val += value_diff
		else:
			qty_dict.out_qty += abs(qty_diff)
			qty_dict.out_val += abs(value_diff)

	qty_dict.val_rate = entry.valuation_rate
	qty_dict.bal_qty += qty_diff
	qty_dict.bal_val += value_diff
	
def initialize_data(args, item_warehouse_map, group_by_key, entry):
	opening_data = args["opening_data"].get(group_by_key, {})

	item_warehouse_map[group_by_key] = frappe._dict(
		{
			"item_code": entry.item_code,
			"warehouse": entry.warehouse,
			"item_group": entry.item_group,
			"company": entry.company,
			"currency": args["company_currency"],
			"stock_uom": entry.stock_uom,
			"item_name": entry.item_name,
			"opening_qty": opening_data.get("bal_qty") or 0.0,
			"opening_val": opening_data.get("bal_val") or 0.0,
			"opening_fifo_queue": opening_data.get("fifo_queue") or [],
			"in_qty": 0.0,
			"in_val": 0.0,
			"out_qty": 0.0,
			"out_val": 0.0,
			"bal_qty": opening_data.get("bal_qty") or 0.0,
			"bal_val": opening_data.get("bal_val") or 0.0,
			"val_rate": 0.0,
		}
	)
	
def filter_items_with_no_transactions(
	iwb_map, float_precision: float, inventory_dimensions: list = None
):
	pop_keys = []
	for group_by_key in iwb_map:
		qty_dict = iwb_map[group_by_key]

		no_transactions = True
		for key, val in qty_dict.items():
			if inventory_dimensions and key in inventory_dimensions:
				continue

			if key in [
				"item_code",
				"warehouse",
				"item_name",
				"item_group",
				"project",
				"stock_uom",
				"company",
				"opening_fifo_queue",
			]:
				continue

			val = flt(val, float_precision)
			qty_dict[key] = val
			if key != "val_rate" and val:
				no_transactions = False

		if no_transactions:
			pop_keys.append(group_by_key)

	for key in pop_keys:
		iwb_map.pop(key)

	return iwb_map
	
def get_opening_vouchers(args):
	to_date = args.get("to_date")
	
	opening_vouchers = {"Stock Entry": [], "Stock Reconciliation": []}

	se = frappe.qb.DocType("Stock Entry")
	sr = frappe.qb.DocType("Stock Reconciliation")

	vouchers_data = (
		frappe.qb.from_(
			(
				frappe.qb.from_(se)
				.select(se.name, Coalesce("Stock Entry").as_("voucher_type"))
				.where((se.docstatus == 1) & (se.posting_date <= to_date) & (se.is_opening == "Yes"))
			)
			+ (
				frappe.qb.from_(sr)
				.select(sr.name, Coalesce("Stock Reconciliation").as_("voucher_type"))
				.where(
					(sr.docstatus == 1) & (sr.posting_date <= to_date) & (sr.purpose == "Opening Stock")
				)
			)
		).select("voucher_type", "name")
	).run(as_dict=True)

	if vouchers_data:
		for d in vouchers_data:
			opening_vouchers[d.voucher_type].append(d.name)

	return opening_vouchers