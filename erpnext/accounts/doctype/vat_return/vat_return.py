# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff,money_in_words,fmt_money
from frappe.contacts.doctype.address.address import get_default_address,get_company_address
from erpnext.accounts.report.utils import convert_to_presentation_currency, get_currency

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
	get_dimension_with_children,
)
class VATReturn(Document):
	def validate(self):
		self.validate_dates()
		self.check_existing()
		
	def validate_dates(self):
		if date_diff(self.end_date, self.start_date) < 0:
			frappe.throw(_("To date cannot be before From date"))
			
	def check_existing(self):
		ret_exist = frappe.db.sql("""select name from `tabVAT Return`
			where start_date = %s and docstatus != 2
			and company = %s and name != %s""",
			(self.start_date,self.company, self.name))
		if ret_exist:
			frappe.throw(_("VAT Return of company {0} already created for this period").format(ret_exist))
	
	@frappe.whitelist()
	def create_vat_return(self):
		
		summary = ""
		table_list = []
		
		header = "Main"
		data = self.get_main_data()
		table_list.append({'header':header,'columns':[],'data':data})
		
		# VAT Company Info
		header = "Taxable Person details"
		data = self.get_taxable_person_data()
		table_list.append({'header':header,'columns':[],'data':data})
		
		# VAT Period Info
		header = "VAT Return Period"
		data = self.get_vat_return_period_data()
		table_list.append({'header':header,'columns':[],'data':data})
		
		# VAT on Sales and all other Outputs Amount
		header = "VAT on Sales and all other Outputs Amount"
		columns = ["","","Amount","VAT Amount","Adjustment"]
		data,sales_totals = self.get_sales_data()
		table_list.append({'header':header,'columns':columns,'data':data})
		
		# VAT on Expenses and all other Inputs
		header = "VAT on Expenses and all other Inputs"
		columns = ["","","Amount","VAT Amount","Adjustment"]
		data,purchase_totals = self.get_purchase_data()
		table_list.append({'header':header,'columns':columns,'data':data})
		
		# Net VAT due
		header = "Net VAT due"
		data = self.get_net_vat_due(sales_totals,purchase_totals)
		table_list.append({'header':header,'columns':[],'data':data})
		
		# Additional Reporting Requirements
		header = "Additional Reporting Requirements"
		table_list.append({'header':header,'columns':[],'data':[]})
		
		# Profit Margin Scheme
		header = "Profit Margin Scheme"
		data = self.get_profit_margin_scheme()
		table_list.append({'header':header,'columns':[],'data':data})
		
		# Goods transferred to GCC implementing states
		header = "Goods transferred to GCC implementing states"
		columns = ["","","Amount","VAT Amount","Adjustment"]
		data = self.get_transferred_to_gcc()
		table_list.append({'header':header,'columns':columns,'data':data})
		
		# VAT paid on personal imports via Agents
		header = "VAT paid on personal imports via Agents"
		columns = ["","","Amount","VAT Amount","Adjustment"]
		data = self.get_agent_vat_gcc()
		table_list.append({'header':header,'columns':columns,'data':data})
		
		# Transportation of own goods to other GCC states
		header = "Transportation of own goods to other GCC states"
		columns = ["","","Amount","VAT Amount","Adjustment"]
		data = self.get_transport_own_goods_gcc()
		table_list.append({'header':header,'columns':columns,'data':data})
		
		# Recoverable VAT paid in other GCC implementing states
		header = "Recoverable VAT paid in other GCC implementing states"
		columns = ["","","Amount","VAT Amount","Adjustment"]
		data = self.get_recoverable_vat_gcc()
		table_list.append({'header':header,'columns':columns,'data':data})
		
		# Tax Refunds for Tourists Scheme provided
		header = "Tax Refunds for Tourists Scheme provided"
		columns = ["","","Amount","VAT Amount","Adjustment"]
		data = self.get_tax_refunds_for_tourists()
		table_list.append({'header':header,'columns':columns,'data':data})
		
		# Declaration
		header = "Declaration"
		data = self.get_declaration()
		table_list.append({'header':header,'columns':[],'data':data})
		
		
		
		for d in table_list:
			summary = summary + create_condensed_table(d['header'],d['columns'],d['data'])
			summary = summary + "<br>"
		self.vat_summary = summary
		return summary
	
	def get_main_data(self):
		data = []
		data.append(("","Form Type",""))
		data.append(("","Document Locator",""))
		data.append(("","Tax Form Filing Type",""))
		data.append(("","Submission Date",""))
		
		return data
		
	def get_taxable_person_data(self):
		data = []
		data.append(("","TRN",self.tax_id))
		data.append(("","Taxable Person Name (English)",self.company))
		data.append(("","Taxable Person Name (Arabic)",self.company_name_in_arabic))
		data.append(("","Taxable Person Address",""))
		data.append(("","Tax Agency Name",""))
		data.append(("","TAN",""))
		data.append(("","Tax Agent Name",""))
		data.append(("","TAAN",""))
		
		return data
		
	def get_vat_return_period_data(self):
		data = []
		
		vat_return_period = str(self.start_date) + ' to ' + str(self.end_date)
		
		data.append(("","VAT Return Period",vat_return_period))
		data.append(("","Tax Year",""))
		data.append(("","VAT Return Period Reference Number",""))
		return data
		
	
	def get_sales_data(self):
		filters = frappe._dict({})
		filters['company'] = self.company		
		filters['to_date'] = self.end_date
		filters['from_date'] = self.start_date

		amount_data = {}
		standard_amount_data = {}
		totals_data = {'amount':0,'vat_amount':0,'adjustment':0}
		
		account_list = []
		account_doc = frappe.get_doc("UAE VAT Settings", self.company)
		if account_doc:
			for d in account_doc.uae_vat_accounts:
				account_list.append({'mrp_vat_type':d.mrp_vat_type,'account':d.account})
		
		vat_states = ['Abu Dhabi','Dubai','Sharjah','Ajman','Umm Al Quwain','Ras Al Khaimah','Fujairah']
		for state in vat_states:
			standard_amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
						
		
		data = []
		section = 1
		sales_data = []

		for i, d in enumerate(account_list,1):
			section = i
			vat_type = d['mrp_vat_type']
			account = d['account']
			
			if not vat_type or not account:
				continue
				
			amount_data[vat_type] = {'amount':0,'vat_amount':0,'adjustment':0}
			section_txt = vat_type
			
			
			filters['account'] = account
			gl_entries = get_gl_entries(filters)
			if vat_type == "Standard Rated":
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,title,project,outstanding_amount,posting_date,customer,base_total, base_grand_total,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							doc_info = details[0]
							doc_state=""
							
							# billing_address_name = get_default_address('Customer',doc_info.customer)
							# if billing_address_name:
								# billing_address = frappe.get_doc('Address', billing_address_name)
								# if billing_address:
									# doc_state = billing_address.city
							
							billing_address_name = get_company_address(self.company)
							if billing_address_name:
								billing_address = frappe.get_doc('Address', billing_address_name.company_address)
								if billing_address:
									doc_state = billing_address.emirate
							
							if doc_state and doc_state in vat_states:
								standard_amount_data[doc_state]['amount'] = standard_amount_data[doc_state]['amount'] + doc_info.base_grand_total - entry.credit
								standard_amount_data[doc_state]['vat_amount'] = standard_amount_data[doc_state]['vat_amount'] + entry.credit
							
								link = frappe.utils.get_link_to_form("Sales Invoice", doc_info.name)
								sales_data.append((link,doc_info.title,doc_info.posting_date,vat_type,doc_info.base_grand_total,entry.credit))
							
							
							
				for letter, state in enumerate(vat_states, 97):
					totals_data["vat_amount"] = standard_amount_data[state]["vat_amount"] + totals_data["vat_amount"]
					totals_data["amount"] = standard_amount_data[state]["amount"] + totals_data["amount"]
					totals_data["adjustment"] = standard_amount_data[state]["adjustment"] + totals_data["adjustment"]
					data.append((str(section)+chr(letter),str(section_txt) + ' ' + str(state),standard_amount_data[state]['amount'],standard_amount_data[state]['vat_amount'],standard_amount_data[state]['adjustment']))
			
			else:
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,posting_date,customer,base_total, base_grand_total,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							doc_info = details[0]
							amount_data[vat_type]['amount'] = amount_data[vat_type]['amount'] + doc_info.base_grand_total - entry.credit
							amount_data[vat_type]['vat_amount'] = amount_data[vat_type]['vat_amount'] + entry.credit
							
							link = frappe.utils.get_link_to_form("Sales Invoice", doc_info.name)
							sales_data.append((link,doc_info.title,doc_info.posting_date,vat_type,doc_info.base_grand_total,entry.credit))
							
							
				totals_data["vat_amount"] = amount_data[vat_type]["vat_amount"] + totals_data["vat_amount"]
				totals_data["amount"] = amount_data[vat_type]["amount"] + totals_data["amount"]
				totals_data["adjustment"] = amount_data[vat_type]["adjustment"] + totals_data["adjustment"]
				data.append((str(section),str(section_txt),amount_data[vat_type]["amount"],amount_data[vat_type]["vat_amount"],amount_data[vat_type]["adjustment"]))	
		
		sales_data.append(("Totals","","","",totals_data["amount"] + totals_data["vat_amount"],totals_data["vat_amount"]))
		sales_columns = ["ID","Title","Date","VAT Type","Grand Total","VAT Amount"]
		self.sales_summary = create_condensed_table("",sales_columns,sales_data,True)

		
		data.append((str(section),"Totals",totals_data["amount"],totals_data["vat_amount"],totals_data["adjustment"]))
		return data,totals_data

	def get_purchase_data(self):
	
		filters = frappe._dict({})
		filters['company'] = self.company
		filters['to_date'] = self.end_date
		filters['from_date'] = self.start_date
		amount_data = {'vat_amount':0,'amount':0,'adjustment':0}
		reverse_data = {'vat_amount':0,'amount':0,'adjustment':0}

		account_list = []
		account_doc = frappe.get_doc("UAE VAT Settings", self.company)
		if account_doc:
			for d in account_doc.uae_vat_accounts:
				account_list.append({'mrp_vat_type':d.mrp_vat_type,'account':d.account})
		
		purchases_data = []
	
		for d in account_list:
			vat_type = d['mrp_vat_type']
			account = d['account']
			
			if not vat_type or not account:
				continue
				
			filters['account'] = account
				
			if vat_type == "Standard Rated":
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Purchase Invoice":
						details = frappe.db.sql("""select name,title,posting_date,base_total,base_grand_total, base_total_taxes_and_charges from `tabPurchase Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							doc_info = details[0]
							amount_data['amount'] = flt(amount_data['amount']) + flt(doc_info.base_grand_total) - flt(entry.debit)
							amount_data['vat_amount'] = flt(amount_data['vat_amount']) + flt(entry.debit)
							
							link = frappe.utils.get_link_to_form("Purchase Invoice", doc_info.name)
							purchases_data.append((link,doc_info.title,doc_info.posting_date,vat_type,doc_info.base_grand_total,entry.debit))

			
			elif vat_type == "Reverse Charge":
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Purchase Invoice":
						details = frappe.db.sql("""select name,title,posting_date,base_total,base_grand_total, base_total_taxes_and_charges from `tabPurchase Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							doc_info = details[0]
							reverse_data['amount'] = flt(reverse_data['amount']) + flt(doc_info.base_grand_total) - flt(entry.debit)
							reverse_data['vat_amount'] = flt(reverse_data['vat_amount']) + flt(entry.debit)
							
							link = frappe.utils.get_link_to_form("Purchase Invoice", doc_info.name)
							purchases_data.append((link,doc_info.title,doc_info.posting_date,vat_type,doc_info.base_grand_total,entry.debit))

		
		
		data = []
		data.append(("9","Standard rated expenses",amount_data['amount'],amount_data['vat_amount'],amount_data['adjustment']))
		data.append(("10","Supplies subject to the reverse charge provisions",reverse_data["amount"],reverse_data["vat_amount"],reverse_data["adjustment"]))
		totals_data = {'vat_amount':0,'amount':0,'adjustment':0}
		totals_data["amount"] = amount_data["amount"] + reverse_data["amount"] 
		totals_data["vat_amount"] = amount_data["vat_amount"] + reverse_data["vat_amount"]
		totals_data["adjustment"] = amount_data["adjustment"] + reverse_data["adjustment"]
		data.append(("11","Totals",totals_data["amount"],totals_data["vat_amount"],totals_data["adjustment"]))
		
		purchases_data.append(("Totals","","","",totals_data["amount"] + totals_data["vat_amount"],totals_data["vat_amount"]))
		purchases_columns = ["ID","Title","Date","VAT Type","Grand Total","VAT Amount"]
		self.purchases_summary = create_condensed_table("",purchases_columns,purchases_data,True)
		
		
		return data,totals_data
		
	def get_net_vat_due(self,sales_totals,purchase_totals):
		
		net_vat = flt(sales_totals["vat_amount"]) - flt(purchase_totals["vat_amount"])
		data = []
		data.append(("12","Total value of due tax for the period",sales_totals["vat_amount"]))
		data.append(("13","Total value of recoverable tax for the period",purchase_totals["vat_amount"]))
		data.append(("14","Net VAT due(or reclaimed) for the period",net_vat))
		self.calculated_due = net_vat
		if cint(self.request_for_refund):
			request_for_refund = "Y"		 
		else:
			request_for_refund = "N"		 
		data.append(("15","If a VAT refund is due, do you wish to request that the refund is paid to you?",str(request_for_refund)))
		
		return data
		
	def get_profit_margin_scheme(self):
		
		if cint(self.use_profit_margin_scheme):
			use_profit_margin_scheme = "Y"		 
		else:
			use_profit_margin_scheme = "N"	
		data = []
		data.append(("","Are you using the profit margin scheme?",use_profit_margin_scheme))
		
		return data
		
		
		
	def get_transferred_to_gcc(self):
	
		amount_data = {}
		vat_states = ['Kingdom of Bahrain','State of Kuwait','Sultanate of Oman','State of Qatar','Kingdom of Saudi Arabia']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
	
		data = []
		for state in vat_states:
			data.append(("","Imported goods transferred to the " + str(state),amount_data[state]["amount"],amount_data[state]["vat_amount"],amount_data[state]["adjustment"]))
		
		
		
		return data
		
	def get_agent_vat_gcc(self):
	
		amount_data = {}
		vat_states = ['Kingdom of Bahrain','State of Kuwait','Sultanate of Oman','State of Qatar','Kingdom of Saudi Arabia']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
	
		data = []
		for state in vat_states:
			data.append(("","Imported goods transferred to the " + str(state),amount_data[state]["amount"],amount_data[state]["vat_amount"],amount_data[state]["adjustment"]))
		
		
		return data
	
	def get_transport_own_goods_gcc(self):
	
		amount_data = {}
		vat_states = ['Kingdom of Bahrain','State of Kuwait','Sultanate of Oman','State of Qatar','Kingdom of Saudi Arabia']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
	
		data = []
		for state in vat_states:
			data.append(("","Goods transported to the " + str(state),amount_data[state]["amount"],amount_data[state]["vat_amount"],amount_data[state]["adjustment"]))	
		
		return data
		
	def get_recoverable_vat_gcc(self):
	
		amount_data = {}
		vat_states = ['Kingdom of Bahrain','State of Kuwait','Sultanate of Oman','State of Qatar','Kingdom of Saudi Arabia']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
	
		data = []
		for state in vat_states:
			data.append(("","Recoverable VAT paid in the " + str(state),amount_data[state]["amount"],amount_data[state]["vat_amount"],amount_data[state]["adjustment"]))
		
		
		return data
		
	def get_tax_refunds_for_tourists(self):
	
		amount_data = {}
		vat_states = ['Abu Dhabi','Dubai','Sharjah','Ajman','Umm Al Quwain','Ras Al Khaimah','Fujairah']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
		data = []
		
		for state in vat_states:
			data.append(("","Tax Refunds for Tourists Scheme paid in " + str(state),amount_data[state]["amount"],amount_data[state]["vat_amount"],amount_data[state]["adjustment"]))
	
		
		return data
		
	def get_declaration(self):
	
		data = []
		data.append(("","I declare that all information provided is true, accurate and complete to the best of my knowledge and belief",""))
		data.append(("","Online User name (English)",""))
		data.append(("","Online User name (Arabic)",""))
		data.append(("","Declarant name (English)",""))
		data.append(("","Declarant name (Arabic)",""))
		data.append(("","Emirates Identity Card number",""))
		data.append(("","",""))
		data.append(("","Passport number (if no Emirates ID available)",""))
		data.append(("","",""))
		
		return data
		
		

def create_condensed_table(header,columns,data,add_sr = False):
	
	joiningtext = ""
	if header:
		joiningtext += """<h2>"""+header+"""</h2>"""
	
	if len(columns) == 0 and len(data) == 0:
		return joiningtext
	
	joiningtext += """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>"""
	
	if add_sr:
		joiningtext += """<th>Sr</th>"""
		
	for table_column in columns:
		joiningtext += """<th>"""+ str(table_column)+"""</th>"""
	
	joiningtext += """</tr></thead><tbody>"""	
	
	for count, d in enumerate(data,1):
		joiningtext += """<tr>"""
		if add_sr:
			joiningtext += """<td>"""+str(count)+"""</td>"""		
		if len(columns) > 0:
			for i, column in enumerate(columns):
				gotdata = ""
				try:
					gotdata = str(d[i])
				except IndexError:
					gotdata = ""

				if is_number_tryexcept(gotdata) and not i ==0:
					joiningtext += """<td>""" + str(fmt_money(flt(gotdata))) +"""</td>"""
				else:
					joiningtext += """<td>""" + str(gotdata) +"""</td>"""
					
		else:
			for entry in d:
				try:
					joiningtext += """<td>""" + str(entry) +"""</td>"""
				except:
					joiningtext += """<td>""" + entry +"""</td>"""
					
		joiningtext += """</tr>"""
	joiningtext += """</tbody></table>"""
	return joiningtext
	
	
def is_number_tryexcept(s):
    """ Returns True if string is a number. """
    try:
        float(s)
        return True
    except ValueError:
        return False

def validate_filters(filters, account_details):
	if not filters.get("company"):
		frappe.throw(_("{0} is mandatory").format(_("Company")))

	if not filters.get("from_date") and not filters.get("to_date"):
		frappe.throw(
			_("{0} and {1} are mandatory").format(frappe.bold(_("From Date")), frappe.bold(_("To Date")))
		)

	if filters.get("account"):
		filters.account = frappe.parse_json(filters.get("account"))
		for account in filters.account:
			if not account_details.get(account):
				frappe.throw(_("Account {0} does not exists").format(account))

	if filters.get("account") and filters.get("group_by") == "Group by Account":
		filters.account = frappe.parse_json(filters.get("account"))
		for account in filters.account:
			if account_details[account].is_group == 0:
				frappe.throw(_("Can not filter based on Child Account, if grouped by Account"))

	if filters.get("voucher_no") and filters.get("group_by") in ["Group by Voucher"]:
		frappe.throw(_("Can not filter based on Voucher No, if grouped by Voucher"))

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))

	if filters.get("project"):
		filters.project = frappe.parse_json(filters.get("project"))

	if filters.get("cost_center"):
		filters.cost_center = frappe.parse_json(filters.get("cost_center"))
		
		
def get_gl_entries(filters, accounting_dimensions = None):
	currency_map = get_currency(filters)
	select_fields = """, debit, credit, debit_in_account_currency,
		credit_in_account_currency """

	order_by_statement = "order by posting_date, account, creation"

	if filters.get("include_dimensions"):
		order_by_statement = "order by posting_date, creation"

	if filters.get("group_by") == "Group by Voucher":
		order_by_statement = "order by posting_date, voucher_type, voucher_no"
	if filters.get("group_by") == "Group by Account":
		order_by_statement = "order by account, posting_date, creation"

	if filters.get("include_default_book_entries"):
		filters["company_fb"] = frappe.get_cached_value(
			"Company", filters.get("company"), "default_finance_book"
		)

	dimension_fields = ""
	if accounting_dimensions:
		dimension_fields = ", ".join(accounting_dimensions) + ","

	gl_entries = frappe.db.sql(
		"""
		select
			name as gl_entry, posting_date, account, party_type, party,
			voucher_type, voucher_no, {dimension_fields}
			cost_center, project,
			against_voucher_type, against_voucher, account_currency,
			remarks, against, is_opening, creation {select_fields}
		from `tabGL Entry`
		where company=%(company)s {conditions}
		{order_by_statement}
	""".format(
			dimension_fields=dimension_fields,
			select_fields=select_fields,
			conditions=get_conditions(filters),
			order_by_statement=order_by_statement,
		),
		filters,
		as_dict=1,
	)

	if filters.get("presentation_currency"):
		return convert_to_presentation_currency(gl_entries, currency_map, filters.get("company"))
	else:
		return gl_entries

	
def get_conditions(filters):
	conditions = []
	if filters.get("account"):
		filters.account = get_accounts_with_children(filters.get("account"))
		conditions.append("account in %(account)s")

	if filters.get("cost_center"):
		filters.cost_center = get_cost_centers_with_children(filters.get("cost_center"))
		conditions.append("cost_center in %(cost_center)s")

	if filters.get("voucher_no"):
		conditions.append("voucher_no=%(voucher_no)s")

	if filters.get("group_by") == "Group by Party" and not filters.get("party_type"):
		conditions.append("party_type in ('Customer', 'Supplier')")

	if filters.get("party_type"):
		conditions.append("party_type=%(party_type)s")

	if filters.get("party"):
		conditions.append("party in %(party)s")

	conditions.append("(posting_date >=%(from_date)s)")

	conditions.append("(posting_date <%(to_date)s)")

	if filters.get("project"):
		conditions.append("project in %(project)s")

	if filters.get("include_default_book_entries"):
		if filters.get("finance_book"):
			if filters.get("company_fb") and cstr(filters.get("finance_book")) != cstr(
				filters.get("company_fb")
			):
				frappe.throw(
					_("To use a different finance book, please uncheck 'Include Default Book Entries'")
				)
			else:
				conditions.append("(finance_book in (%(finance_book)s, '') OR finance_book IS NULL)")
		else:
			conditions.append("(finance_book in (%(company_fb)s, '') OR finance_book IS NULL)")
	else:
		if filters.get("finance_book"):
			conditions.append("(finance_book in (%(finance_book)s, '') OR finance_book IS NULL)")
		else:
			conditions.append("(finance_book in ('') OR finance_book IS NULL)")

	if not filters.get("show_cancelled_entries"):
		conditions.append("is_cancelled = 0")

	from frappe.desk.reportview import build_match_conditions

	match_conditions = build_match_conditions("GL Entry")

	if match_conditions:
		conditions.append(match_conditions)

	if filters.get("include_dimensions"):
		accounting_dimensions = get_accounting_dimensions(as_list=False)

		if accounting_dimensions:
			for dimension in accounting_dimensions:
				if not dimension.disabled:
					if filters.get(dimension.fieldname):
						if frappe.get_cached_value("DocType", dimension.document_type, "is_tree"):
							filters[dimension.fieldname] = get_dimension_with_children(
								dimension.document_type, filters.get(dimension.fieldname)
							)
							conditions.append("{0} in %({0})s".format(dimension.fieldname))
						else:
							conditions.append("{0} in %({0})s".format(dimension.fieldname))

	return "and {}".format(" and ".join(conditions)) if conditions else ""

def get_accounts_with_children(accounts):
	if not isinstance(accounts, list):
		accounts = [d.strip() for d in accounts.strip().split(",") if d]

	all_accounts = []
	for d in accounts:
		account = frappe.get_cached_doc("Account", d)
		if account:
			children = frappe.get_all(
				"Account", filters={"lft": [">=", account.lft], "rgt": ["<=", account.rgt]}
			)
			all_accounts += [c.name for c in children]
		else:
			frappe.throw(_("Account: {0} does not exist").format(d))

	return list(set(all_accounts))
