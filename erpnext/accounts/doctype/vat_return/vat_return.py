# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff,money_in_words
from frappe.contacts.doctype.address.address import get_default_address

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
			frappe.throw(_("VAT Return of company {0} already created for this period").format(self.employee))
	
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
		data = self.get_angent_vat_gcc()
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
		filters = {}
		filters['company'] = self.company
		
		filters['to_date'] = self.end_date
		filters['from_date'] = self.start_date
		filters['account'] = 'UAE VAT 5% - SLI'
		
		gl_entries = get_gl_entries(filters)
		amount_data = {}
		vat_states = ['Abu Dhabi','Dubai','Sharjah','Ajman','Umm Al Quwain','Ras Al Khaimah','Fujairah']
		
		vat_types = ['reverse_charge_data','zero_rated_data','other_gcc_data','exempt_data','import_customs_data','amendments_data']
		totals_data = {'amount':0,'vat_amount':0,'adjustment':0}
		
		for type in vat_types:
			amount_data[type] = {'amount':0,'vat_amount':0,'adjustment':0}
			
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
		
		for entry in gl_entries:
			
			if entry.voucher_type == "Sales Invoice":
				details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
				if len(details)>0:
					billing_address_name = get_default_address('Customer',details[0].customer)
					if billing_address_name:
						billing_address = frappe.get_doc('Address', billing_address_name)
						if billing_address:
							for state in vat_states:
								if state == billing_address.state:
									amount_data[state]['amount'] = amount_data[state]['amount'] + details[0].grand_total
									amount_data[state]['vat_amount'] = amount_data[state]['vat_amount'] + entry.credit
					
		
		data = []
		letter = 97
		
		for state in vat_states:
			data.append(("1"+chr(letter),"Standard rated supplies in " + str(state),amount_data[state]['amount'],amount_data[state]['vat_amount'],amount_data[state]['adjustment']))
			letter = letter + 1
			
		
		section = 2
		for type in vat_types:
			totals_data["vat_amount"] = amount_data[type]["vat_amount"] + totals_data["vat_amount"]
			totals_data["amount"] = amount_data[type]["amount"] + totals_data["amount"]
			totals_data["adjustment"] = amount_data[type]["adjustment"] + totals_data["adjustment"]
			
			section_txt = ''
			
			if type == "reverse_charge_data":
				section_txt = "Supplies subject to the reverse charge provisions"
				
				filters['account'] = 'UAE VAT 5% - SLI'
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							amount_data[type]['amount'] = amount_data[state]['amount'] + details[0].grand_total
							amount_data[type]['vat_amount'] = amount_data[state]['vat_amount'] + entry.credit
							
										
				
			elif type == "zero_rated_data":
				section_txt = "Zero rated supplies"
				
				filters['account'] = 'UAE VAT 5% - SLI'
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							amount_data[type]['amount'] = amount_data[state]['amount'] + details[0].grand_total
							amount_data[type]['vat_amount'] = amount_data[state]['vat_amount'] + entry.credit
							
				
			elif type == "other_gcc_data":
				section_txt = "Supplies of goods and services to registered customers in other GCC implementing states"
			
				filters['account'] = 'UAE VAT 5% - SLI'
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							amount_data[type]['amount'] = amount_data[state]['amount'] + details[0].grand_total
							amount_data[type]['vat_amount'] = amount_data[state]['vat_amount'] + entry.credit
							
			elif type == "exempt_data":
				section_txt = "Exempt supplies"
				
				filters['account'] = 'UAE VAT 5% - SLI'
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							amount_data[type]['amount'] = amount_data[state]['amount'] + details[0].grand_total
							amount_data[type]['vat_amount'] = amount_data[state]['vat_amount'] + entry.credit
							
				
			elif type == "import_customs_data":
				section_txt = "Import VAT accounted through UAE customs"
				
				filters['account'] = 'UAE VAT 5% - SLI'
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							amount_data[type]['amount'] = amount_data[state]['amount'] + details[0].grand_total
							amount_data[type]['vat_amount'] = amount_data[state]['vat_amount'] + entry.credit
							
				
			elif type == "amendments_data":
				section_txt = "Amendments or corrections to Output figures"
				
				filters['account'] = 'UAE VAT 5% - SLI'
				gl_entries = get_gl_entries(filters)
				for entry in gl_entries:
					if entry.voucher_type == "Sales Invoice":
						details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
						if len(details)>0:
							amount_data[type]['amount'] = amount_data[state]['amount'] + details[0].grand_total
							amount_data[type]['vat_amount'] = amount_data[state]['vat_amount'] + entry.credit
							
			
			
			data.append((str(section),str(section_txt),amount_data[type]["amount"],amount_data[type]["vat_amount"],amount_data[type]["adjustment"]))	

			
			section = section + 1
		
		
		data.append((str(section),"Totals",totals_data["amount"],totals_data["vat_amount"],totals_data["adjustment"]))
		
		
		return data,totals_data

	def get_purchase_data(self):
	
		filters = {}
		filters['company'] = self.company
		
		filters['to_date'] = self.end_date
		filters['from_date'] = self.start_date
		filters['account'] = 'UAE VAT 5% - SLI'
		amount_data = {'vat_amount':0,'amount':0,'adjustment':0}

		gl_entries = get_gl_entries(filters)

		for entry in gl_entries:
			if entry.voucher_type == "Purchase Invoice":
				details = frappe.db.sql("""select name,posting_date,currency,supplier,grand_total, base_total_taxes_and_charges,supplier_address from `tabPurchase Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
				if len(details)>0:
					amount_data['amount'] = flt(amount_data['amount']) + flt(details[0].grand_total)
					amount_data['vat_amount'] = flt(amount_data['vat_amount']) + flt(entry.debit)
	
		filters['account'] = 'UAE VAT 5%_reverse - SLI'							
			
		data = []
		data.append(("9","Standard rated expenses",amount_data['amount'],amount_data['vat_amount'],amount_data['adjustment']))
		
		gl_entries = get_gl_entries(filters)
		
		reverse_data = {'vat_amount':0,'amount':0,'adjustment':0}

		for entry in gl_entries:
			if entry.voucher_type == "Purchase Invoice":
				details = frappe.db.sql("""select name,posting_date,currency,supplier,grand_total, base_total_taxes_and_charges,supplier_address from `tabPurchase Invoice` where name = %s and company = %s""", (entry.voucher_no,self.company),as_dict = 1)
				if len(details)>0:
					reverse_data['amount'] = flt(reverse_data['amount']) + flt(details[0].grand_total)
					reverse_data['vat_amount'] = flt(reverse_data['vat_amount']) + flt(entry.debit)
	
		
		

		
		data.append(("10","Supplies subject to the reverse charge provisions",reverse_data["amount"],reverse_data["vat_amount"],reverse_data["adjustment"]))
		
		totals_data = {'vat_amount':0,'amount':0,'adjustment':0}
		
		totals_data["amount"] = amount_data["amount"] + reverse_data["amount"] 
		totals_data["vat_amount"] = amount_data["vat_amount"] + reverse_data["vat_amount"]
		totals_data["adjustment"] = amount_data["adjustment"] + reverse_data["adjustment"]
		
		data.append(("11","Totals",totals_data["amount"],totals_data["vat_amount"],totals_data["adjustment"]))
		
		return data,totals_data
		
	def get_net_vat_due(self,sales_totals,purchase_totals):
		
		net_vat = flt(sales_totals["vat_amount"]) - flt(purchase_totals["vat_amount"])
		data = []
		data.append(("12","Total value of due tax for the period",sales_totals["vat_amount"]))
		data.append(("13","Total value of recoverable tax for the period",purchase_totals["vat_amount"]))
		data.append(("14","Net VAT due(or reclaimed) for the period",net_vat))
		
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
			data.append(("","Imported goods transferred to the " + str(state),amount_data["state"]["amount"],amount_data["state"]["vat_amount"],amount_data["state"]["adjustment"]))
		
		
		
		return data
		
	def get_angent_vat_gcc(self):
	
		amount_data = {}
		vat_states = ['Kingdom of Bahrain','State of Kuwait','Sultanate of Oman','State of Qatar','Kingdom of Saudi Arabia']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
	
		data = []
		for state in vat_states:
			data.append(("","Imported goods transferred to the " + str(state),amount_data["state"]["amount"],amount_data["state"]["vat_amount"],amount_data["state"]["adjustment"]))
		
		
		return data
	
	def get_transport_own_goods_gcc(self):
	
		amount_data = {}
		vat_states = ['Kingdom of Bahrain','State of Kuwait','Sultanate of Oman','State of Qatar','Kingdom of Saudi Arabia']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
	
		data = []
		for state in vat_states:
			data.append(("","Goods transported to the " + str(state),amount_data["state"]["amount"],amount_data["state"]["vat_amount"],amount_data["state"]["adjustment"]))	
		
		return data
		
	def get_recoverable_vat_gcc(self):
	
		amount_data = {}
		vat_states = ['Kingdom of Bahrain','State of Kuwait','Sultanate of Oman','State of Qatar','Kingdom of Saudi Arabia']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
	
		data = []
		for state in vat_states:
			data.append(("","Recoverable VAT paid in the " + str(state),amount_data["state"]["amount"],amount_data["state"]["vat_amount"],amount_data["state"]["adjustment"]))
		
		
		return data
		
	def get_tax_refunds_for_tourists(self):
	
		amount_data = {}
		vat_states = ['Abu Dhabi','Dubai','Sharjah','Ajman','Umm Al Quwain','Ras Al Khaimah','Fujairah']
		
		for state in vat_states:
			amount_data[state] = {'amount':0,'vat_amount':0,'adjustment':0}
			
		data = []
		
		for state in vat_states:
			data.append(("","Tax Refunds for Tourists Scheme paid in " + str(state),amount_data["state"]["amount"],amount_data["state"]["vat_amount"],amount_data["state"]["adjustment"]))
	
		
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
		
		

def create_condensed_table(header,columns,dict):
	
	joiningtext = ""
	if header:
		joiningtext += """<h2>"""+header+"""</h2>"""
	
	if len(columns) == 0 and len(dict) == 0:
		return joiningtext
	
	joiningtext += """<table class="table table-bordered table-condensed">"""
	joiningtext += """<thead>
			<tr style>"""
	
	for table_column in columns:
		joiningtext += """<th>"""+ str(table_column)+"""</th>"""
	
	joiningtext += """</tr></thead><tbody>"""	
	
	for d in dict:
		joiningtext += """<tr>"""
		
		
		if len(columns) > 0:
			for i, column in enumerate(columns):
				gotdata = ""
				try:
					gotdata = str(d[i])
				except IndexError:
					gotdata = ""
			
				joiningtext += """<td>""" + str(gotdata) +"""</td>"""
		else:
			for data in d:
				try:
					joiningtext += """<td>""" + str(data) +"""</td>"""
				except:
					joiningtext += """<td>""" + data +"""</td>"""
		joiningtext += """</tr>"""
	joiningtext += """</tbody></table>"""
	return joiningtext

def validate_filters(filters, account_details):
	if not filters.get('company'):
		frappe.throw(_('{0} is mandatory').format(_('Company')))

	if filters.get("account") and not account_details.get(filters.account):
		frappe.throw(_("Account {0} does not exists").format(filters.account))

	if filters.get("account") and filters.get("group_by_account") \
			and account_details[filters.account].is_group == 0:
		frappe.throw(_("Can not filter based on Account, if grouped by Account"))

	if filters.get("voucher_no") and filters.get("group_by_voucher"):
		frappe.throw(_("Can not filter based on Voucher No, if grouped by Voucher"))

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))
		
		
def get_gl_entries(filters):
	select_fields = """, sum(debit_in_account_currency) as debit_in_account_currency,
		sum(credit_in_account_currency) as credit_in_account_currency""" \
		if filters.get("show_in_account_currency") else ""

	group_by_condition = "group by voucher_type, voucher_no, account, cost_center" \
		if filters.get("group_by_voucher") else "group by name"

	gl_entries = frappe.db.sql("""
		select
			posting_date, account, party_type, party,
			sum(debit) as debit, sum(credit) as credit,
			voucher_type, voucher_no, cost_center, project,
			against_voucher_type, against_voucher,
			remarks, against, is_opening {select_fields}
		from `tabGL Entry`
		where company=%(company)s {conditions}
		{group_by_condition}
		order by posting_date, account"""\
		.format(select_fields=select_fields, conditions=get_conditions(filters),
			group_by_condition=group_by_condition), filters, as_dict=1)

	return gl_entries
	
def get_conditions(filters):
	conditions = []
	if filters.get("account"):
		lft, rgt = frappe.db.get_value("Account", filters["account"], ["lft", "rgt"])
		conditions.append("""account in (select name from tabAccount
			where lft>=%s and rgt<=%s and docstatus<2)""" % (lft, rgt))

	if filters.get("voucher_no"):
		conditions.append("voucher_no=%(voucher_no)s")

	if filters.get("party_type"):
		conditions.append("party_type=%(party_type)s")

	if filters.get("party"):
		conditions.append("party=%(party)s")

	if not (filters.get("account") or filters.get("party") or filters.get("group_by_account")):
		conditions.append("posting_date >=%(from_date)s")

	if filters.get("project"):
		conditions.append("project=%(project)s")

	from frappe.desk.reportview import build_match_conditions
	match_conditions = build_match_conditions("GL Entry")
	if match_conditions: conditions.append(match_conditions)

	return "and {}".format(" and ".join(conditions)) if conditions else ""

	
def get_result_as_list(data, filters):
	result = []
	for d in data:
		row = [d.get("posting_date"), d.get("account"), d.get("debit"), d.get("credit")]

		if filters.get("show_in_account_currency"):
			row += [d.get("debit_in_account_currency"), d.get("credit_in_account_currency")]

		row += [d.get("voucher_type"), d.get("voucher_no"), d.get("against"),
			d.get("party_type"), d.get("party"), d.get("project"), d.get("cost_center"), d.get("against_voucher_type"), d.get("against_voucher"), d.get("remarks")
		]

		result.append(row)

	return result