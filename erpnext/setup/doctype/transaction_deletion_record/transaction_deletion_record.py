# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from collections import OrderedDict

import frappe
from frappe import _, qb
from frappe.query_builder import DocType
from frappe.desk.notifications import clear_notifications
from frappe.model.document import Document
from frappe.utils import cint, comma_and, create_batch, get_link_to_form
from frappe.model.naming import parse_naming_series		
from frappe.utils.background_jobs import create_job_id, is_job_enqueued


class TransactionDeletionRecord(Document):
	def __init__(self, *args, **kwargs):
		super(TransactionDeletionRecord, self).__init__(*args, **kwargs)
		self.batch_size = 5000
		# Tasks are listed by their execution order
		self.task_to_internal_method_map = OrderedDict(
			{
				"Delete Bins": "delete_bins",
				"Delete Leads and Addresses": "delete_lead_addresses",
				"Reset Company Values": "reset_company_values",
				"Clear Notifications": "delete_notifications",
				"Initialize Summary Table": "initialize_doctypes_to_be_deleted_table",
				"Delete Transactions": "delete_company_transactions",
			}
		)

	def validate(self):
		frappe.only_for("System Manager")
		self.validate_doctypes_to_be_ignored()

	def validate_doctypes_to_be_ignored(self):
		doctypes_to_be_ignored_list = get_doctypes_to_be_ignored()
		for doctype in self.doctypes_to_be_ignored:
			if doctype.doctype_name not in doctypes_to_be_ignored_list:
				pass
				# frappe.throw(
					# _(
						# "DocTypes should not be added manually to the 'Excluded DocTypes' table. You are only allowed to remove entries from it."
					# ),
					# title=_("Not Allowed"),
				# )

	def generate_job_name_for_task(self, task=None):
		method = self.task_to_internal_method_map[task]
		return f"{self.name}_{method}"

	def generate_job_name_for_next_tasks(self, task=None):
		job_names = []
		current_task_idx = list(self.task_to_internal_method_map).index(task)
		for idx, task in enumerate(self.task_to_internal_method_map.keys(), 0):
			# generate job_name for next tasks
			if idx > current_task_idx:
				job_names.append(self.generate_job_name_for_task(task))
		return job_names

	def generate_job_name_for_all_tasks(self):
		job_names = []
		for task in self.task_to_internal_method_map.keys():
			job_names.append(self.generate_job_name_for_task(task))
		return job_names

	def before_submit(self):
		if queued_docs := frappe.db.get_all(
			"Transaction Deletion Record",
			filters={"company": self.company, "status": ("in", ["Running", "Queued"]), "docstatus": 1},
			pluck="name",
		):
			frappe.throw(
				_(
					"Cannot enqueue multi docs for one company. {0} is already queued/running for company: {1}"
				).format(
					comma_and([get_link_to_form("Transaction Deletion Record", x) for x in queued_docs]),
					frappe.bold(self.company),
				)
			)

		if not self.doctypes_to_be_ignored:
			self.populate_doctypes_to_be_ignored_table()

		self.delete_bins()
		self.delete_lead_addresses()
		self.reset_company_values()
		clear_notifications()
		self.delete_company_transactions()
		self.mrp_recalculate_bin_qty()
	
	@frappe.whitelist()
	def mrp_run(self):
		self.delete_bins()
		self.delete_lead_addresses()
		self.reset_company_values()
		clear_notifications()
		self.delete_company_transactions()
		self.mrp_recalculate_bin_qty()
			
	
	@frappe.whitelist()		
	def second_step(self):
		self.delete_lead_addresses()
		self.reset_company_values()
		clear_notifications()

	def reset_task_flags(self):
		self.clear_notifications = 0
		self.delete_bin_data = 0
		self.delete_leads_and_addresses = 0
		self.delete_transactions = 0
		self.initialize_doctypes_table = 0
		self.reset_company_default_values = 0

	def before_save(self):
		self.status = ""
		self.doctypes.clear()
		self.reset_task_flags()

	def on_submit(self):
		self.db_set("status", "Queued")

	def on_cancel(self):
		self.db_set("status", "Cancelled")

	def enqueue_task(self, task: str | None = None):
		if task and task in self.task_to_internal_method_map:
			# make sure that none of next tasks are already running
			job_names = self.generate_job_name_for_next_tasks(task=task)
			self.validate_running_task_for_doc(job_names=job_names)

			# Generate Job Id to uniquely identify each task for this document
			job_id = self.generate_job_name_for_task(task)

			if self.process_in_single_transaction:
				self.execute_task(task_to_execute=task)
			else:
				frappe.enqueue(
					"frappe.utils.background_jobs.run_doc_method",
					doctype=self.doctype,
					name=self.name,
					doc_method="execute_task",
					job_id=job_id,
					queue="long",
					enqueue_after_commit=True,
					task_to_execute=task,
				)

	def execute_task(self, task_to_execute: str | None = None):
		if task_to_execute:
			method = self.task_to_internal_method_map[task_to_execute]
			if task := getattr(self, method, None):
				try:
					task()
				except Exception as err:
					frappe.db.rollback()
					traceback = frappe.get_traceback(with_context=True)
					if traceback:
						message = "Traceback: <br>" + traceback
						frappe.db.set_value(self.doctype, self.name, "error_log", message)
					frappe.db.set_value(self.doctype, self.name, "status", "Failed")

	def delete_notifications(self):
		self.validate_doc_status()
		if not self.clear_notifications:
			clear_notifications()
			self.db_set("clear_notifications", 1)
		self.enqueue_task(task="Initialize Summary Table")

	@frappe.whitelist()
	def mrp_recalculate_bin_qty(self):
		if not self.custom_mrp_debug_only:
			# self.delete_bins()
			
			items = frappe.get_all(
				"Item", filters={}
			)
			
			from erpnext.stock.stock_balance import repost_stock
			existing_allow_negative_stock = frappe.db.get_value(
				"Stock Settings", None, "allow_negative_stock"
			)
			frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
			
			for r in items:
				new_name = r.name
				
				repost_stock_for_warehouses = frappe.get_all(
					"Stock Ledger Entry",
					"warehouse",
					filters={"item_code": new_name,"company":self.company},
					pluck="warehouse",
					distinct=True,
				)

				for warehouse in repost_stock_for_warehouses:
					repost_stock(new_name, warehouse)

			frappe.db.set_single_value(
				"Stock Settings", "allow_negative_stock", existing_allow_negative_stock
			)
	
	
	def populate_doctypes_to_be_ignored_table(self):
		doctypes_to_be_ignored_list = get_doctypes_to_be_ignored()
		for doctype in doctypes_to_be_ignored_list:
			self.append("doctypes_to_be_ignored", {"doctype_name": doctype})

	@frappe.whitelist()
	def delete_bins(self):
		if not self.custom_mrp_debug_only:
			frappe.db.sql(
				"""delete from `tabBin` where warehouse in
					(select name from tabWarehouse where company=%s)""",
				self.company,
			)
		
			frappe.db.sql(
				"""delete from `tabRepost Item Valuation` where company=%s""",
				self.company,
			)

	def delete_lead_addresses(self):
		if not self.custom_mrp_debug_only:
			"""Delete addresses to which leads are linked"""
	def validate_running_task_for_doc(self, job_names: list = None):
		# at most only one task should be runnning
		running_tasks = []
		for x in job_names:
			if is_job_enqueued(x):
				running_tasks.append(create_job_id(x))

		if running_tasks:
			frappe.throw(
				_("{0} is already running for {1}").format(
					comma_and([get_link_to_form("RQ Job", x) for x in running_tasks]), self.name
				)
			)

	def validate_doc_status(self):
		if self.status != "Running":
			frappe.throw(
				_("{0} is not running. Cannot trigger events for this Document").format(
					get_link_to_form("Transaction Deletion Record", self.name)
				)
			)

	@frappe.whitelist()
	def start_deletion_tasks(self):
		# This method is the entry point for the chain of events that follow
		self.db_set("status", "Running")
		self.enqueue_task(task="Delete Bins")

	def delete_bins(self):
		self.validate_doc_status()
		if not self.delete_bin_data:
			frappe.db.sql(
				"""delete from `tabBin` where warehouse in
					(select name from tabWarehouse where company=%s)""",
				self.company,
			)
			self.db_set("delete_bin_data", 1)
		self.enqueue_task(task="Delete Leads and Addresses")

	def delete_lead_addresses(self):
		"""Delete addresses to which leads are linked"""
		self.validate_doc_status()
		if not self.delete_leads_and_addresses:
			leads = frappe.get_all("Lead", filters={"company": self.company})
			leads = ["'%s'" % row.get("name") for row in leads]
			addresses = []
			if leads:
				addresses = frappe.db.sql_list(
					"""select parent from `tabDynamic Link` where link_name
					in ({leads})""".format(
						leads=",".join(leads)
					)
				)

				if addresses:
					addresses = ["%s" % frappe.db.escape(addr) for addr in addresses]

					frappe.db.sql(
						"""delete from `tabAddress` where name in ({addresses}) and
						name not in (select distinct dl1.parent from `tabDynamic Link` dl1
						inner join `tabDynamic Link` dl2 on dl1.parent=dl2.parent
						and dl1.link_doctype<>dl2.link_doctype)""".format(
							addresses=",".join(addresses)
						)
					)

					frappe.db.sql(
						"""delete from `tabDynamic Link` where link_doctype='Lead'
						and parenttype='Address' and link_name in ({leads})""".format(
							leads=",".join(leads)
						)
					)

				frappe.db.sql(
					"""update `tabCustomer` set lead_name=NULL where lead_name in ({leads})""".format(
						leads=",".join(leads)
					)
				)

	def reset_company_values(self):
		if not self.custom_mrp_debug_only:
			self.db_set("delete_leads_and_addresses", 1)

		self.validate_doc_status()
		if not self.reset_company_default_values:
			company_obj = frappe.get_doc("Company", self.company)
			company_obj.total_monthly_sales = 0
			company_obj.sales_monthly_history = None
			company_obj.save()
			self.db_set("reset_company_default_values", 1)
		self.enqueue_task(task="Clear Notifications")

	def initialize_doctypes_to_be_deleted_table(self):
		self.validate_doc_status()
		if not self.initialize_doctypes_table:
			doctypes_to_be_ignored_list = self.get_doctypes_to_be_ignored_list()
			docfields = self.get_doctypes_with_company_field(doctypes_to_be_ignored_list)
			tables = self.get_all_child_doctypes()
			for docfield in docfields:
				if docfield["parent"] != self.doctype:
					no_of_docs = self.get_number_of_docs_linked_with_specified_company(
						docfield["parent"], docfield["fieldname"]
					)
					if no_of_docs > 0:
						# Initialize
						self.populate_doctypes_table(tables, docfield["parent"], docfield["fieldname"], 0)
			self.db_set("initialize_doctypes_table", 1)
		self.enqueue_task(task="Delete Transactions")

	@frappe.whitelist()
	def delete_company_transactions(self):
		self.custom_mrp_summary = ''
		self.set('doctypes',[])
		
		if not self.doctypes_to_be_ignored:
			self.populate_doctypes_to_be_ignored_table()
	
		doctypes_to_be_ignored_list = self.get_doctypes_to_be_ignored_list()
		docfields = self.get_doctypes_with_company_field(doctypes_to_be_ignored_list)

		# tables = self.get_all_child_doctypes()
		for docfield in docfields:
			if docfield["parent"] != self.doctype:
				# no_of_docs = self.get_number_of_docs_linked_with_specified_company(
					# docfield["parent"], docfield["fieldname"]
				# )

				self.custom_mrp_summary += '<b>' + str(docfield["parent"]) + '</b>' + '<br>'
				
				parent_docs = self.get_docs_to_be_deleted(docfield["parent"], docfield["fieldname"])
				
				self.delete_version_log(docfield["parent"], docfield["fieldname"], parent_docs)
				self.delete_connections(docfield["parent"], docfield["fieldname"], parent_docs)
					
				# self.populate_doctypes_table(tables, docfield["parent"], no_of_docs)
				
				self.delete_child_tables(docfield["parent"], docfield["fieldname"], parent_docs)
				self.delete_docs_linked_with_specified_company(docfield["parent"], docfield["fieldname"], parent_docs)
		# self.validate_doc_status()
		# if not self.delete_transactions:
			# doctypes_to_be_ignored_list = self.get_doctypes_to_be_ignored_list()
			# docfields = self.get_doctypes_with_company_field(doctypes_to_be_ignored_list)

			# tables = self.get_all_child_doctypes()
			# for docfield in self.doctypes:
				# if docfield.doctype_name != self.doctype and not docfield.done:
					# no_of_docs = self.get_number_of_docs_linked_with_specified_company(
						# docfield.doctype_name, docfield.docfield_name
					# )
					# if no_of_docs > 0:
						# reference_docs = frappe.get_all(
							# docfield.doctype_name, filters={docfield.docfield_name: self.company}, limit=self.batch_size
						# )
						# reference_doc_names = [r.name for r in reference_docs]

						# self.delete_version_log(docfield.doctype_name, reference_doc_names)
						# self.delete_communications(docfield.doctype_name, reference_doc_names)
						# self.delete_comments(docfield.doctype_name, reference_doc_names)
						# self.unlink_attachments(docfield.doctype_name, reference_doc_names)
						# self.delete_child_tables(docfield.doctype_name, reference_doc_names)
						# self.delete_docs_linked_with_specified_company(docfield.doctype_name, reference_doc_names)
						# processed = int(docfield.no_of_docs) + len(reference_doc_names)
						# frappe.db.set_value(docfield.doctype, docfield.name, "no_of_docs", processed)
					# else:
						# # reset naming series
						# naming_series = frappe.db.get_value("DocType", docfield.doctype_name, "autoname")
						# if naming_series:
							# if "#" in naming_series:
								# self.update_naming_series(naming_series, docfield.doctype_name)
						# frappe.db.set_value(docfield.doctype, docfield.name, "done", 1)

			# pending_doctypes = frappe.db.get_all(
				# "Transaction Deletion Record Details",
				# filters={"parent": self.name, "done": 0},
				# pluck="doctype_name",
			# )
			# if pending_doctypes:
				# # as method is enqueued after commit, calling itself will not make validate_doc_status to throw
				# # recursively call this task to delete all transactions
				# self.enqueue_task(task="Delete Transactions")
			# else:
				# self.db_set("status", "Completed")
				# self.db_set("delete_transactions", 1)
				# self.db_set("error_log", None)

					
	def get_docs_to_be_deleted(self, doctype, company_fieldname):
		parent_docs_to_be_deleted = []
		limit = 100
		if frappe.get_meta(doctype).has_field("posting_date"):
			parent_docs_to_be_deleted = frappe.get_all(
				doctype, {company_fieldname: self.company, "posting_date": ["<", self.custom_mrp_delete_before_date]}
				, pluck="name"
			)
		
		elif frappe.get_meta(doctype).has_field("transaction_date"):
			parent_docs_to_be_deleted = frappe.get_all(
				doctype, {company_fieldname: self.company, "transaction_date": ["<", self.custom_mrp_delete_before_date]}
				, pluck="name"
			)
		else:
			parent_docs_to_be_deleted = frappe.get_all(
				doctype, {company_fieldname: self.company}
				, pluck="name"
			)
		
		return parent_docs_to_be_deleted
	
	def get_doctypes_to_be_ignored_list(self):
		singles = frappe.get_all("DocType", filters={"issingle": 1}, pluck="name")
		doctypes_to_be_ignored_list = singles
		for doctype in self.doctypes_to_be_ignored:
			doctypes_to_be_ignored_list.append(doctype.doctype_name)

		return doctypes_to_be_ignored_list

	def get_doctypes_with_company_field(self, doctypes_to_be_ignored_list):
		docfields = frappe.get_all(
			"DocField",
			filters={
				"fieldtype": "Link",
				"options": "Company",
				"parent": ["not in", doctypes_to_be_ignored_list],
			},
			fields=["parent", "fieldname"],
		)

		return docfields

	def get_all_child_doctypes(self):
		return frappe.get_all("DocType", filters={"istable": 1}, pluck="name")

	def get_number_of_docs_linked_with_specified_company(self, doctype, company_fieldname):
		return frappe.db.count(doctype, {company_fieldname: self.company})

	def populate_doctypes_table(self, tables, doctype, fieldname, no_of_docs):
		self.flags.ignore_validate_update_after_submit = True
		if doctype not in tables:
			self.append("doctypes", {"doctype_name": doctype, "no_of_docs": no_of_docs})
	
	
	@frappe.whitelist()
	def mrp_delete_connections(self):
		if not self.custom_mrp_debug_only:
			communications = qb.DocType("Communication")
			qb.from_(communications).delete().where(
					(communications.creation < self.custom_mrp_delete_before_date)
				).run()
				
			comments = qb.DocType("Comment")
			qb.from_(comments).delete().where(
					(comments.creation < self.custom_mrp_delete_before_date)
				).run()
				
	@frappe.whitelist()
	def mrp_delete_comments(self):
		if not self.custom_mrp_debug_only:
			comments = qb.DocType("Comment")
			qb.from_(comments).delete().where(
					(comments.comment_type == "Deleted")
				).run()		
			

	def delete_connections(self, doctype, company_fieldname, parent_docs_to_be_deleted):
		if self.custom_mrp_debug_only:
			pass
		else:
			self.delete_communications(doctype, parent_docs_to_be_deleted)
			self.delete_comments(doctype, parent_docs_to_be_deleted)
			self.unlink_attachments(doctype, parent_docs_to_be_deleted)


	def delete_child_tables(self, doctype, company_fieldname, parent_docs_to_be_deleted):
		if parent_docs_to_be_deleted:
			if self.custom_mrp_debug_only:
				pass
			else:
				child_tables = frappe.get_all(
					"DocField", filters={"fieldtype": "Table", "parent": doctype}, pluck="options"
				)
				
				for batch in create_batch(parent_docs_to_be_deleted, self.batch_size):
					for table in child_tables:
						frappe.db.delete(table, {"parent": ["in", batch]})

	def delete_docs_linked_with_specified_company(self, doctype, company_fieldname, parent_docs_to_be_deleted):	
		if self.custom_mrp_debug_only:
			pass
		else:
			for batch in create_batch(parent_docs_to_be_deleted, self.batch_size):
				frappe.db.delete(doctype, {"name": ["in", batch]})
		
			# if frappe.get_meta(doctype).has_field("posting_date"):
				# frappe.db.delete(doctype, {company_fieldname: self.company, "posting_date": ["<", self.custom_mrp_delete_before_date]})
			# elif frappe.get_meta(doctype).has_field("transaction_date"):
				# frappe.db.delete(doctype, {company_fieldname: self.company, "transaction_date": ["<", self.custom_mrp_delete_before_date]})
			# else:
				# frappe.db.delete(doctype, {company_fieldname: self.company})

	@frappe.whitelist()
	def update_naming_series_custom(self):
		if not self.doctypes_to_be_ignored:
			self.populate_doctypes_to_be_ignored_table()
	
		doctypes_to_be_ignored_list = self.get_doctypes_to_be_ignored_list()
		docfields = self.get_doctypes_with_company_field(doctypes_to_be_ignored_list)

		# tables = self.get_all_child_doctypes()
		for docfield in docfields:
			if docfield["parent"] != self.doctype:
				parent_docs_to_be_deleted = self.get_docs_to_be_deleted(docfield["parent"], docfield["fieldname"])
				doctype = docfield["parent"]
				company_fieldname = docfield["fieldname"]
				for d in parent_docs_to_be_deleted:
					doc = frappe.get_doc(doctype, d)
					
					if doc.meta.autoname:
						if doc.meta.autoname.startswith("naming_series:") and getattr(doc, "naming_series", None):
							revert_series_if_last(doc.naming_series, doc.name, doc, doctype=doctype, custom_mrp_debug_only = self.custom_mrp_debug_only)

						elif doc.meta.autoname.split(":", 1)[0] not in ("Prompt", "field", "hash", "autoincrement"):
							revert_series_if_last(doc.meta.autoname, doc.name, doc, doctype=doctype, custom_mrp_debug_only = self.custom_mrp_debug_only)


	def update_naming_series(self, naming_series, doctype_name):
		if "." in naming_series:
			prefix, hashes = naming_series.rsplit(".", 1)
		else:
			prefix, hashes = naming_series.rsplit("{", 1)
		last = frappe.db.sql(
			"""select max(name) from `tab{0}`
						where name like %s""".format(
				doctype_name
			),
			prefix + "%",
		)
		if last and last[0][0]:
			last = cint(last[0][0].replace(prefix, ""))
		else:
			last = 0

		frappe.db.sql("""update `tabSeries` set current = %s where name=%s""", (last, prefix))

	def delete_version_log(self, doctype, company_fieldname, parent_docs_to_be_deleted):
		if self.custom_mrp_debug_only:
			pass
		else:
			if parent_docs_to_be_deleted:
				versions = qb.DocType("Version")
				for batch in create_batch(parent_docs_to_be_deleted, self.batch_size):
					qb.from_(versions).delete().where(
						(versions.ref_doctype == doctype) & (versions.docname.isin(batch))
					).run()


	def delete_communications(self, doctype, parent_docs_to_be_deleted):
		if self.custom_mrp_debug_only:
			pass
		else:
			if parent_docs_to_be_deleted:
				communications = qb.DocType("Communication")
				for batch in create_batch(parent_docs_to_be_deleted, self.batch_size):
					qb.from_(communications).delete().where(
						(communications.reference_doctype == doctype) & (communications.reference_name.isin(batch))
					).run()
	
	
		# communications = frappe.get_all(
			# "Communication",
			# filters={"reference_doctype": doctype, "reference_name": ["in", parent_docs_to_be_deleted]},
			# pluck="name"
		# )

		# for batch in create_batch(communications, self.batch_size):
			# frappe.delete_doc("Communication", batch, ignore_permissions=True)

	def delete_comments(self, doctype, parent_docs_to_be_deleted):
		if self.custom_mrp_debug_only:
			pass
		else:
			if parent_docs_to_be_deleted:
				comments = qb.DocType("Comment")
				for batch in create_batch(parent_docs_to_be_deleted, self.batch_size):
					qb.from_(comments).delete().where(
						(comments.reference_doctype == doctype) & (comments.reference_name.isin(batch))
					).run()
	
	
		# comments = frappe.get_all(
			# "Comment",
			# filters={"reference_doctype": doctype, "reference_name": ["in", parent_docs_to_be_deleted]},
			# pluck="name"
		# )

		# for batch in create_batch(comments, self.batch_size):
			# frappe.delete_doc("Comment", batch, ignore_permissions=True)

	def unlink_attachments(self, doctype, parent_docs_to_be_deleted):
		files = frappe.get_all(
			"File",
			filters={"attached_to_doctype": doctype, "attached_to_name": ["in", parent_docs_to_be_deleted]},
		)
		file_names = [c.name for c in files]

		if not file_names:
			return

		file = qb.DocType("File")

		for batch in create_batch(file_names, self.batch_size):
			qb.update(file).set(file.attached_to_doctype, None).set(file.attached_to_name, None).where(
				file.name.isin(batch)
			).run()


@frappe.whitelist()
def get_doctypes_to_be_ignored():
	doctypes_to_be_ignored = [
		"Account",
		"Cost Center",
		"Warehouse",
		"Budget",
		"Party Account",
		"Employee",
		"Sales Taxes and Charges Template",
		"Purchase Taxes and Charges Template",
		"POS Profile",
		"BOM",
		"Company",
		"Bank Account",
		"Item Tax Template",
		"Mode of Payment",
		"Mode of Payment Account",
		"Item Default",
		"Customer",
		"Supplier",
	]

	doctypes_to_be_ignored.extend(frappe.get_hooks("company_data_to_be_ignored") or [])

	return doctypes_to_be_ignored
	
	
def recalculate_bin_qty(new_name, company):
	from erpnext.stock.stock_balance import repost_stock

	existing_allow_negative_stock = frappe.db.get_value(
		"Stock Settings", None, "allow_negative_stock"
	)
	frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)

	repost_stock_for_warehouses = frappe.get_all(
		"Stock Ledger Entry",
		"warehouse",
		filters={"item_code": new_name,"company":company},
		pluck="warehouse",
		distinct=True,
	)

	# Delete all existing bins to avoid duplicate bins for the same item and warehouse
	# Do step 1 instead - delete all bins for company
	# frappe.db.delete("Bin", {"item_code": new_name})

	for warehouse in repost_stock_for_warehouses:
		repost_stock(new_name, warehouse)

	frappe.db.set_single_value(
		"Stock Settings", "allow_negative_stock", existing_allow_negative_stock
	)
	
@frappe.whitelist()
def reopen_pos(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.supplier,
		t1.transaction_date,
		t1.status,
		t1.title
	FROM
		`tabPurchase Order` t1
	WHERE
		YEAR(t1.transaction_date) = %s AND
		t1.docstatus = 1 AND
		t1.status = "Closed"
	ORDER BY
		t1.transaction_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Purchase Order", po_detail.name)
				po.update_status("Submitted")				
				prs_created.append(_("PO {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.transaction_date,po_detail.title))
			else:
				prs_created.append(_("PO {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.transaction_date,po_detail.title))

		except Exception as error:
			error_list.append(error)
	
	frappe.db.commit()

	return prs_created
	
@frappe.whitelist()
def cancel_sis(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.status,
		t1.title
	FROM
		`tabSales Invoice` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Sales Invoice", po_detail.name)
				po.cancel()
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)
	
	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def cancel_jes(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.title
	FROM
		`tabJournal Entry` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Journal Entry", po_detail.name)
				po.cancel()
				prs_created.append(_("PR {0} {1} {2}.").format(po_detail.name, po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PR {0} {1} {2}.").format(po_detail.name, po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)
	
	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def cancel_ses(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.title
	FROM
		`tabStock Entry` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Stock Entry", po_detail.name)
				po.cancel()
				prs_created.append(_("SE {0} {1} {2}.").format(po_detail.name,po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("SE {0} {1} {2}.").format(po_detail.name,po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)
	
	frappe.db.commit()
		
	return prs_created

@frappe.whitelist()
def cancel_dns(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.status,
		t1.title
	FROM
		`tabDelivery Note` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Delivery Note", po_detail.name)
				po.cancel()
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)
	
	frappe.db.commit()
		
	
	return prs_created
	
@frappe.whitelist()
def delete_prs(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.status,
		t1.title
	FROM
		`tabPurchase Receipt` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 2
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Purchase Receipt", po_detail.name)
				
				po.delete()
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)

	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def cancel_imps(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.title
	FROM
		`tabMRP Import Entry` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("MRP Import Entry", po_detail.name)
				po.cancel()
				prs_created.append(_("PR {0} {1} {2}.").format(po_detail.name, po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PR {0} {1} {2}.").format(po_detail.name, po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)

	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def cancel_pros(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.reference_title as title
	FROM
		`tabMRP Production Order` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("MRP Production Order", po_detail.name)
				po.cancel()
				prs_created.append(_("PR {0} {1} {2}.").format(po_detail.name, po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PR {0} {1} {2}.").format(po_detail.name, po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)

	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def cancel_repos(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date
	FROM
		`tabRepost Item Valuation` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Repost Item Valuation", po_detail.name)
				po.cancel()
				po.delete()
				prs_created.append(_("PR {0} {1}.").format(po_detail.name,po_detail.posting_date))
			else:
				prs_created.append(_("PR {0} {1}.").format(po_detail.name,po_detail.posting_date))

		except Exception as error:
			error_list.append(error)

	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def cancel_strs(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date
	FROM
		`tabStock Reconciliation` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Stock Reconciliation", po_detail.name)
				po.cancel()
				prs_created.append(_("PR {0} {1}.").format(po_detail.name,po_detail.posting_date))
			else:
				prs_created.append(_("PR {0} {1}.").format(po_detail.name,po_detail.posting_date))

		except Exception as error:
			error_list.append(error)

	frappe.db.commit()
	
	return prs_created

@frappe.whitelist()
def cancel_prs(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.status,
		t1.title
	FROM
		`tabPurchase Receipt` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Purchase Receipt", po_detail.name)
				po.cancel()
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PR {0} {1} {2} {3}.").format(po_detail.name, po_detail.status, po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)

	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def cancel_pes(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.title
	FROM
		`tabPayment Entry` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Payment Entry", po_detail.name)
				po.cancel()
				prs_created.append(_("PE {0} {1} {2}.").format(po_detail.name,po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PE {0} {1} {2}.").format(po_detail.name,po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)
	
	frappe.db.commit()

	
	return prs_created
	
@frappe.whitelist()
def cancel_pis(year = None,limit=500,submit=False):
	if not year:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.posting_date,
		t1.title
	FROM
		`tabPurchase Invoice` t1
	WHERE
		YEAR(t1.posting_date) = %s AND
		t1.docstatus = 1
	ORDER BY
		t1.posting_date ASC
	LIMIT
		%s""", (year,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Purchase Invoice", po_detail.name)
				po.cancel()
				prs_created.append(_("PI {0} {1} {2}.").format(po_detail.name,po_detail.posting_date,po_detail.title))
			else:
				prs_created.append(_("PI {0} {1} {2}.").format(po_detail.name,po_detail.posting_date,po_detail.title))

		except Exception as error:
			error_list.append(error)
	
	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def delete_warehouses(parent_warehouse = None,limit=500,submit=False, force=False):
	if not parent_warehouse:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.disabled
	FROM
		`tabWarehouse` t1
	WHERE
		t1.parent_warehouse = %s AND
		t1.disabled = 1
	LIMIT
		%s""", (parent_warehouse,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Warehouse", po_detail.name)
				po.delete(force=force)
				prs_created.append(_("Warehouse {0} {1}.").format(po_detail.name,po_detail.disabled))
			else:
				prs_created.append(_("Warehouse {0} {1}.").format(po_detail.name,po_detail.disabled))

		except Exception as error:
			error_list.append(error)
	

	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def enable_warehouses(parent_warehouse = None,limit=500,submit=False):
	if not parent_warehouse:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.disabled
	FROM
		`tabWarehouse` t1
	WHERE
		t1.parent_warehouse = %s AND
		t1.disabled = 1
	LIMIT
		%s""", (parent_warehouse,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Warehouse", po_detail.name)
				po.disabled = 0
				po.save()
				prs_created.append(_("Warehouse {0} {1}.").format(po_detail.name,po_detail.disabled))
			else:
				prs_created.append(_("Warehouse {0} {1}.").format(po_detail.name,po_detail.disabled))

		except Exception as error:
			error_list.append(error)
	

	frappe.db.commit()
	
	return prs_created
	
@frappe.whitelist()
def disable_warehouses(parent_warehouse = None,limit=500,submit=False):
	if not parent_warehouse:
		return None
		
	purchase_order_details = frappe.db.sql("""SELECT
		t1.name,
		t1.disabled
	FROM
		`tabWarehouse` t1
	WHERE
		t1.parent_warehouse = %s AND
		t1.disabled = 0
	LIMIT
		%s""", (parent_warehouse,cint(limit)), as_dict=True)
			
	prs_created = []
	error_list = []
	submit = cint(submit)
	
	for po_detail in purchase_order_details:
		try:
			if submit:
				po = frappe.get_doc("Warehouse", po_detail.name)
				po.disabled = 1
				po.save()
				prs_created.append(_("Warehouse {0} {1}.").format(po_detail.name,po_detail.disabled))
			else:
				prs_created.append(_("Warehouse {0} {1}.").format(po_detail.name,po_detail.disabled))

		except Exception as error:
			error_list.append(error)
	

	frappe.db.commit()
	
	return prs_created
	
	
def revert_series_if_last(key, name=None, doc=None, doctype=None, custom_mrp_debug_only = None):
	if key.startswith("format:"):
		first_colon_index = key.find(":")
		autoname_value = key[first_colon_index + 1 :]
		key = get_prefix_format_autoname(autoname_value)
	
	if ".#" in key:
		prefix, hashes = key.rsplit(".", 1)

		if "#" not in hashes:
			# get the hash part from the key
			hash = re.search("#+", key)
			if not hash:
				return
			name = name.replace(hashes, "")
			prefix = prefix.replace(hash.group(), "")
	else:
		prefix = key
	
	# ignore check for . so we can add default prefixes
	
	dash_count = name.count("-")
	if dash_count > 0:
		new_prefix = parse_naming_series(prefix.split('.'),doc=doc, doctype=doctype)
		name_count = name.count(new_prefix)
		if name_count > 0:
			prefix = new_prefix
	
	count = cint(name.replace(prefix, ""))	
	series = qb.DocType("Series")
	current = (
		frappe.qb.from_(series).where(series.name == prefix).for_update().select("current")
	).run()
	
	msg = str(name) + ' ' + str(prefix)
	frappe.errprint(msg)

	if current and current[0][0] == count:
		if custom_mrp_debug_only:
			pass
		else:
			frappe.db.sql("UPDATE `tabSeries` SET `current` = `current` - 1 WHERE `name`=%s", prefix)


@frappe.whitelist()
def is_deletion_doc_running(company: str | None = None, err_msg: str | None = None):
	if company:
		if running_deletion_jobs := frappe.db.get_all(
			"Transaction Deletion Record",
			filters={"docstatus": 1, "company": company, "status": "Running"},
		):
			if not err_msg:
				err_msg = ""
			frappe.throw(
				title=_("Deletion in Progress!"),
				msg=_("Transaction Deletion Document: {0} is running for this Company. {1}").format(
					get_link_to_form("Transaction Deletion Record", running_deletion_jobs[0].name), err_msg
				),
			)


def check_for_running_deletion_job(doc, method=None):
	# Check if DocType has 'company' field
	df = qb.DocType("DocField")
	if (
		not_allowed := qb.from_(df)
		.select(df.parent)
		.where((df.fieldname == "company") & (df.parent == doc.doctype))
		.run()
	):
		is_deletion_doc_running(
			doc.company, _("Cannot make any transactions until the deletion job is completed")
		)
