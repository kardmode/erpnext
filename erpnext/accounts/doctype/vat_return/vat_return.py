# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff,money_in_words

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
	
	
	def get_sales_data(self):
	
		details = frappe.db.sql("""select name,posting_date,currency,customer,grand_total, base_total_taxes_and_charges,customer_address from `tabSales Invoice` where company = %s and docstatus = 1 and posting_date between %s and %s""", (self.company,self.start_date, self.end_date),as_dict = 1)
		total_amount = 0

		for d in details:
			total_amount = total_amount + d.base_total_taxes_and_charges
		
		

	def get_purchase_data(self):
		
		details = frappe.db.sql("""select name,posting_date,currency,supplier,grand_total,base_total_taxes_and_charges,supplier_address from `tabPurchase Order` where company = %s and docstatus = 1 and posting_date between %s and %s""", (self.company,self.start_date, self.end_date),as_dict = 1)
		total_amount = 0
		
		for d in details:
			total_amount = total_amount + d.base_total_taxes_and_charges
		
	