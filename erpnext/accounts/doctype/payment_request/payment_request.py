# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _,msgprint,throw
from frappe.model.document import Document
from frappe.utils import flt, nowdate, get_url,money_in_words,getdate,fmt_money,formatdate
from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry, get_company_defaults
from frappe.integrations.utils import get_payment_gateway_controller
from frappe.model.naming import make_autoname
from frappe.utils.background_jobs import enqueue

class PaymentRequest(Document):
	# def autoname(self):
		# import datetime
		# year = (getdate(self.posting_date)).year
		# month = (getdate(self.posting_date)).month
		# date_string = str(year)
		# naming_series = self.naming_series
		# # if self.company:
			# # abbr = 	frappe.db.get_value("Company", self.company, "abbr")
			# # if abbr:
				# # naming_series = str(abbr) + "-" + naming_series 
			
		# self.name = make_autoname(naming_series + date_string + '.#####')
			
	def validate(self):
		# self.validate_reference_document()
		# self.validate_payment_request()
		# self.validate_currency()
		
		self.request_in_words = money_in_words(self.advance_required, self.currency)
		self.in_words = money_in_words(self.outstanding_amount, self.currency)


	def validate_reference_document(self):
		if not self.reference_doctype or not self.reference_name:
			frappe.throw(_("To create a Payment Request reference document is required"))

	def validate_payment_request(self):
		if self.outstanding_amount <= 0:
			frappe.throw(_("Payment Request already exists {0}".format(self.reference_name)))

		# if frappe.db.get_value("Payment Request", {"reference_name": self.reference_name,
			# "name": ("!=", self.name), "status": ("not in", ["Initiated", "Paid"]), "docstatus": 1}, "name"):
			# frappe.throw(_("Payment Request already exists {0}".format(self.reference_name)))

	def validate_currency(self):
		ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
		if self.payment_account and ref_doc.currency != frappe.db.get_value("Account", self.payment_account, "account_currency"):
			frappe.throw(_("Transaction currency must be same as Payment Gateway currency"))

	def on_submit(self):
		send_mail = not self.mute_email

		ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)

		if (hasattr(ref_doc, "order_type") and getattr(ref_doc, "order_type") == "Shopping Cart") \
			or self.flags.mute_email:
			send_mail = False

		if send_mail:
			self.set_payment_request_url()
			self.send_email()
			self.make_communication_entry()

	def on_cancel(self):
		self.check_if_payment_entry_exists()
		self.set_as_cancelled()

	def make_invoice(self):
		ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
		if (hasattr(ref_doc, "order_type") and getattr(ref_doc, "order_type") == "Shopping Cart"):
			from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
			si = make_sales_invoice(self.reference_name, ignore_permissions=True)
			si = si.insert(ignore_permissions=True)
			si.submit()

	def set_payment_request_url(self):
		if self.payment_account:
			self.payment_url = self.get_payment_url()

		if self.payment_url:
			self.db_set('payment_url', self.payment_url)

		if self.payment_url or not self.payment_gateway_account:
			self.db_set('status', 'Initiated')

	def get_payment_url(self):
		if self.reference_doctype != "Fees":
			data = frappe.db.get_value(self.reference_doctype, self.reference_name, ["company", "customer_name"], as_dict=1)
		else:
			data = frappe.db.get_value(self.reference_doctype, self.reference_name, ["student_name"], as_dict=1)
			data.update({"company": frappe.defaults.get_defaults().company})

		controller = get_payment_gateway_controller(self.payment_gateway)
		controller.validate_transaction_currency(self.currency)

		return controller.get_payment_url(**{
			"amount": flt(self.grand_total, self.precision("grand_total")),
			"title": data.company.encode("utf-8"),
			"description": self.subject.encode("utf-8"),
			"reference_doctype": "Payment Request",
			"reference_docname": self.name,
			"payer_email": self.email_to or frappe.session.user,
			"payer_name": data.customer_name,
			"order_id": self.name,
			"currency": self.currency
		})

	def set_as_paid(self):
		if frappe.session.user == "Guest":
			frappe.set_user("Administrator")

		payment_entry = self.create_payment_entry()
		self.make_invoice()

		return payment_entry

	def create_payment_entry(self, submit=True):
		"""create entry"""
		frappe.flags.ignore_account_permission = True

		ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)

		if self.reference_doctype == "Sales Invoice":
			party_account = ref_doc.debit_to
		elif self.reference_doctype == "Purchase Invoice":
			party_account = ref_doc.credit_to
		else:
			party_account = get_party_account("Customer", ref_doc.get("customer"), ref_doc.company)

		party_account_currency = ref_doc.get("party_account_currency") or get_account_currency(party_account)

		bank_amount = self.grand_total
		if party_account_currency == ref_doc.company_currency and party_account_currency != self.currency:
			party_amount = ref_doc.base_grand_total
		else:
			party_amount = self.grand_total

		payment_entry = get_payment_entry(self.reference_doctype, self.reference_name,
			party_amount=party_amount, bank_account=self.payment_account, bank_amount=bank_amount)

		payment_entry.update({
			"reference_no": self.name,
			"reference_date": nowdate(),
			"remarks": "Payment Entry against {0} {1} via Payment Request {2}".format(self.reference_doctype,
				self.reference_name, self.name)
		})

		if payment_entry.difference_amount:
			company_details = get_company_defaults(ref_doc.company)

			payment_entry.append("deductions", {
				"account": company_details.exchange_gain_loss_account,
				"cost_center": company_details.cost_center,
				"amount": payment_entry.difference_amount
			})

		if submit:
			payment_entry.insert(ignore_permissions=True)
			payment_entry.submit()

		return payment_entry

	def send_email(self):
		"""send email with payment link"""
		email_args = {
			"recipients": self.email_to,
			"sender": None,
			"subject": self.subject,
			"message": self.get_message(),
			"now": True,
			"attachments": [frappe.attach_print(self.reference_doctype, self.reference_name,
				file_name=self.reference_name, print_format=self.print_format)]}
		enqueue(method=frappe.sendmail, queue='short', timeout=300, async=True, **email_args)

	def get_message(self):
		"""return message with payment gateway link"""

		context = {
			"doc": frappe.get_doc(self.reference_doctype, self.reference_name),
			"payment_url": self.payment_url
		}

		if self.message:
			return frappe.render_template(self.message, context)

	def set_failed(self):
		pass

	def set_as_cancelled(self):
		self.db_set("status", "Cancelled")

	def check_if_payment_entry_exists(self):
		if self.status == "Paid":
			payment_entry = frappe.db.sql_list("""select parent from `tabPayment Entry Reference`
				where reference_name=%s""", self.reference_name)
			if payment_entry:
				frappe.throw(_("Payment Entry already exists"), title=_('Error'))

	def make_communication_entry(self):
		"""Make communication entry"""
		comm = frappe.get_doc({
			"doctype":"Communication",
			"subject": self.subject,
			"content": self.get_message(),
			"sent_or_received": "Sent",
			"reference_doctype": self.reference_doctype,
			"reference_name": self.reference_name
		})
		comm.insert(ignore_permissions=True)

	def get_payment_success_url(self):
		return self.payment_success_url

	def on_payment_authorized(self, status=None):
		if not status:
			return

		shopping_cart_settings = frappe.get_doc("Shopping Cart Settings")

		if status in ["Authorized", "Completed"]:
			redirect_to = None
			self.run_method("set_as_paid")

			# if shopping cart enabled and in session
			if (shopping_cart_settings.enabled and hasattr(frappe.local, "session")
				and frappe.local.session.user != "Guest"):

				success_url = shopping_cart_settings.payment_success_url
				if success_url:
					redirect_to = ({
						"Orders": "orders",
						"Invoices": "invoices",
						"My Account": "me"
					}).get(success_url, "me")
				else:
					redirect_to = get_url("/orders/{0}".format(self.reference_name))

			return redirect_to
	
	def get_invoice_info(self,args):
		args = frappe._dict(args)		
		newd = frappe.db.sql("""select title,posting_date,currency,customer,grand_total as total_amount, outstanding_amount,debit_to,project from `tabSales Invoice` where name = %s limit 1""", args.docname,as_dict = 1)
		return newd
		
	def get_doc_info(self,args):
		args = frappe._dict(args)

		self.currency = "AED"
		project = args.docname
		self.subject = project
		
		invoices = get_invoices(project)
		for d in sorted(invoices):
			newd = self.append('invoices')
			newd.sales_invoice = d.name
			newd.posting_date = d.posting_date
			newd.outstanding_amount = d.outstanding_amount
			newd.total_amount = d.grand_total
			newd.project = project
			newd.title = d.title
		
		
		self.calculate_totals()
		
		
	def calculate_totals(self):	
		grand_total = 0
		outstanding_amount = 0
		total_advance = 0
		
		for d in self.get('invoices'):
			grand_total = grand_total + flt(d.total_amount)
			outstanding_amount = outstanding_amount + flt(d.outstanding_amount)
			
		
		
		
		total_advance = flt(grand_total)-flt(outstanding_amount)
		
		self.currency ="AED"
		self.grand_total = grand_total
		
		
		self.outstanding_amount = outstanding_amount
		self.total_advance = total_advance
		
		self.in_words = money_in_words(self.outstanding_amount, self.currency)
		self.request_in_words = money_in_words(self.advance_required, self.currency)

@frappe.whitelist(allow_guest=True)
def make_payment_request(**args):
	"""Make payment request"""

	args = frappe._dict(args)
	ref_doc = frappe.get_doc(args.dt, args.dn)

	gateway_account = get_gateway_details(args) or frappe._dict()

	grand_total = get_amount(ref_doc, args.doctype)
		
	outstanding_amount,payments_summary = get_outstanding_amount(ref_doc, args.doctype)
	total_advance = flt(grand_total)-flt(outstanding_amount)


	existing_payment_request = frappe.db.get_value("Payment Request",
		{"reference_doctype": args.dt, "reference_name": args.dn, "docstatus": ["!=", 2]})

	if existing_payment_request:
		pr = frappe.get_doc("Payment Request", existing_payment_request)

	else:
		pr = frappe.new_doc("Payment Request")
		
		in_words = money_in_words(outstanding_amount, ref_doc.currency)

		
		pr.update({
			"payment_gateway_account": gateway_account.get("name"),
			"payment_gateway": gateway_account.get("payment_gateway"),
			"payment_account": gateway_account.get("payment_account"),
			"currency": ref_doc.currency,
			"grand_total": grand_total,
			"email_to": args.recipient_id or "",
			"subject": ref_doc.project,
			"message": gateway_account.get("message") or get_dummy_message(ref_doc),
			"reference_doctype": args.dt,
			"reference_name": args.dn,
			"project":ref_doc.project,
			"in_words":in_words,
			"outstanding_amount":outstanding_amount,
			"total_advance":total_advance,
			"customer":ref_doc.customer,
			"customer_address":ref_doc.customer_address,
			"contact_person":ref_doc.contact_person,
			"address_display":ref_doc.address_display,
			"contact_display":ref_doc.contact_display,
		})

		if args.order_type == "Shopping Cart" or args.mute_email:
			pr.flags.mute_email = True

		if args.submit_doc:
			pr.insert(ignore_permissions=True)
			pr.submit()

	if args.order_type == "Shopping Cart":
		frappe.db.commit()
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = pr.get_payment_url()

	if args.return_doc:
		return pr

	return pr.as_dict()

def get_amount(ref_doc, dt):
	"""get amount based on doctype"""
	grand_total = 0
	if dt == "Sales Order":
		if ref_doc.party_account_currency == ref_doc.currency:
			grand_total = flt(ref_doc.grand_total)
		else:
			grand_total = flt(ref_doc.grand_total) / ref_doc.conversion_rate

	elif dt == "Sales Invoice":
		if ref_doc.party_account_currency == ref_doc.currency:
			grand_total = flt(ref_doc.grand_total)
		else:
			grand_total = flt(ref_doc.grand_total) / ref_doc.conversion_rate
	elif dt == "Project":
		doc_list = get_documents(ref_doc.name,"Sales Invoice")
		
		for d in doc_list:
			grand_total = grand_total + flt(d.grand_total)
	
	
	if dt == "Fees":
		grand_total = ref_doc.outstanding_amount


	
	return grand_total
	
		
def get_outstanding_amount(ref_doc, dt):
	"""get amount based on doctype"""
	outstanding_amount = 0
	
	payments_summary = """<table class="table table-bordered table-condensed">"""
	payments_summary += """<thead><tr style>
				<th>Sr</th>
				<th width="20%">Ref.</th>
				<th>Transaction Ref.</th>
				<th>Date</th>
				<th>Amount</th>
				</tr></thead><tbody>"""
	
	if dt == "Sales Order":
		outstanding_amount = flt(ref_doc.grand_total) - flt(ref_doc.advance_paid)
		if ref_doc.party_account_currency == ref_doc.currency:
			outstanding_amount = flt(outstanding_amount)
		else:
			outstanding_amount = flt(outstanding_amount) / ref_doc.conversion_rate
		
		payments_summary += get_advances(ref_doc)
	elif dt == "Sales Invoice":
		if ref_doc.party_account_currency == ref_doc.currency:
			outstanding_amount = flt(ref_doc.outstanding_amount)
		else:
			outstanding_amount = flt(ref_doc.outstanding_amount) / ref_doc.conversion_rate
		
		payments_summary += get_advances(ref_doc)
	elif dt == "Project":
		doctype = "Sales Invoice"
		doc_list = get_documents(ref_doc.name,doctype)
		
		
		for d in doc_list:
			outstanding_amount = outstanding_amount + flt(d.outstanding_amount)
			d["doctype"] = doctype
			payments_summary += get_advances(d)
		
	if outstanding_amount <= 0 :
		frappe.msgprint(_("No Outstanding Balance"))
		
	payments_summary += """</tbody></table>"""
	return outstanding_amount,payments_summary



def get_gateway_details(args):
	"""return gateway and payment account of default payment gateway"""
	if args.get("payment_gateway"):
		return get_payment_gateway_account(args.get("payment_gateway"))

	if args.order_type == "Shopping Cart":
		payment_gateway_account = frappe.get_doc("Shopping Cart Settings").payment_gateway_account
		return get_payment_gateway_account(payment_gateway_account)

	gateway_account = get_payment_gateway_account({"is_default": 1})

	return gateway_account

def get_payment_gateway_account(args):
	return frappe.db.get_value("Payment Gateway Account", args,
		["name", "payment_gateway", "payment_account", "message"],
			as_dict=1)

@frappe.whitelist()
def get_print_format_list(ref_doctype):
	print_format_list = ["Standard"]

	print_format_list.extend([p.name for p in frappe.get_all("Print Format",
		filters={"doc_type": ref_doctype})])

	return {
		"print_format": print_format_list
	}

@frappe.whitelist(allow_guest=True)
def resend_payment_email(docname):
	return frappe.get_doc("Payment Request", docname).send_email()

@frappe.whitelist()
def make_payment_entry(docname):
	doc = frappe.get_doc("Payment Request", docname)
	return doc.create_payment_entry(submit=False).as_dict()

def make_status_as_paid(doc, method):
	for ref in doc.references:
		payment_request_name = frappe.db.get_value("Payment Request",
			{"reference_doctype": ref.reference_doctype, "reference_name": ref.reference_name,
			"docstatus": 1})

		if payment_request_name:
			doc = frappe.get_doc("Payment Request", payment_request_name)
			if doc.status != "Paid":
				doc.db_set('status', 'Paid')
				frappe.db.commit()

def get_dummy_message(doc):
	return frappe.render_template("""{% if doc.contact_person -%}
<p>Dear {{ doc.contact_display }},</p>
{%- else %}<p>To Whom It May Concern,</p>{% endif %}

<p>{{ _("Requesting payment against {0} {1} for amount {2}").format(doc.doctype,
	doc.name, doc.get_formatted("grand_total")) }}</p>
<p>{{ _("If you have any questions, please get back to us.") }}</p>

<p>{{ _("Thank you for your business.") }}</p>
""", dict(doc=doc, payment_url = '{{ payment_url }}'))



def get_documents(project,doctype):
	ss_list = []
	if doctype == "Sales Order":
		ss_list = frappe.db.sql("""select name,title,posting_date,currency,customer,grand_total , advance_paid, debit_to from `tabSales Order` where project = %s and docstatus = 1""", project,as_dict = 1)

	elif doctype == "Sales Invoice":
		ss_list = frappe.db.sql("""select name,title,posting_date,currency,customer,grand_total, outstanding_amount,debit_to from `tabSales Invoice` where project = %s and docstatus = 1""", project,as_dict = 1)

	return ss_list
	
def get_invoices(project):
	"""Returns list of advances against Account, Party, Reference"""
	res = get_documents(project,"Sales Invoice")
	
	return res

	
def get_advances(ref_doc):
	"""Returns list of advances against Account, Party, Reference"""
	order_list = [ref_doc.name]
	res = get_advance_entries(order_list,ref_doc.doctype,ref_doc,include_unallocated=False)
	
		
	joiningtext = ""
	for i, d in enumerate(res):
		amount = fmt_money(d.amount, 2, d.paid_from_account_currency)
		joiningtext += """<tr>
					<td>""" + str(i+1) +"""</td>
					<td>""" + str(ref_doc.name) +"""</td>
					<td>""" + str(d.reference_no) +"""</td>
					<td>""" + str(formatdate(d.reference_date)) +"""</td>
					<td>""" + str(d.paid_from_account_currency) + " " + amount +"""</td>
					</tr>"""
	
	return joiningtext

def get_advance_entries(order_list,order_doctype,ref_doc,include_unallocated=True):
	party_account = ref_doc.debit_to
	party_type = "Customer"
	party = ref_doc.customer
	amount_field = "credit_in_account_currency"

	# from erpnext.controllers.accounts_controller import get_advance_journal_entries

	# journal_entries = get_advance_journal_entries(party_type, party, party_account,
		# amount_field, order_doctype, order_list, include_unallocated)

	payment_entries = get_advance_payment_entries(party_type, party, party_account,
		order_doctype, order_list, include_unallocated)

	res = payment_entries

	return res

def get_advance_payment_entries(party_type, party, party_account,
		order_doctype, order_list=None, include_unallocated=True, against_all_orders=False):
	party_account_field = "paid_from" if party_type == "Customer" else "paid_to"
	payment_type = "Receive" if party_type == "Customer" else "Pay"
	payment_entries_against_order, unallocated_payment_entries = [], []

	if order_list or against_all_orders:
		if order_list:
			reference_condition = " and t2.reference_name in ({0})"\
				.format(', '.join(['%s'] * len(order_list)))
		else:
			reference_condition = ""
			order_list = []

		payment_entries_against_order = frappe.db.sql("""
			select
				"Payment Entry" as reference_type, t1.name as reference_name,
				t1.remarks, t2.allocated_amount as amount, t2.name as reference_row,
				t2.reference_name as against_order, t1.posting_date,t1.paid_from_account_currency, t1.reference_no,t1.reference_date
			from `tabPayment Entry` t1, `tabPayment Entry Reference` t2
			where
				t1.name = t2.parent and t1.{0} = %s and t1.payment_type = %s
				and t1.party_type = %s and t1.party = %s and t1.docstatus = 1
				and t2.reference_doctype = %s {1}
		""".format(party_account_field, reference_condition),
		[party_account, payment_type, party_type, party, order_doctype] + order_list, as_dict=1)

	if include_unallocated:
		unallocated_payment_entries = frappe.db.sql("""
				select "Payment Entry" as reference_type, name as reference_name,
				remarks, unallocated_amount as amount
				from `tabPayment Entry`
				where
					{0} = %s and party_type = %s and party = %s and payment_type = %s
					and docstatus = 1 and unallocated_amount > 0
			""".format(party_account_field), (party_account, party_type, party, payment_type), as_dict=1)

	return list(payment_entries_against_order) + list(unallocated_payment_entries)
