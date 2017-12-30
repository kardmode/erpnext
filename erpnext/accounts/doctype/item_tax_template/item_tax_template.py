# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document

class ItemTaxTemplate(Document):
	pass

@frappe.whitelist()
def get_template_details(template_name=None,item_code=None):
	accounts = []
	if not template_name and not item_code:
		accounts = []
	elif item_code and not template_name:
		accounts = frappe.db.sql("""
			select t1.tax_type as account_head, t1.tax_rate as rate
			from `tabItem Tax` t1, `tabItem` t2
			where t2.name=%s and t1.parent = t2.name order by t1.idx""",item_code, as_dict=1)

	elif template_name:
		accounts = frappe.db.sql("""
			select t1.account_head, t1.rate
			from `tabItem Tax Template Accounts` t1, `tabItem Tax Template` t2
			where t2.name=%s and t1.parent = t2.name order by t1.idx""",template_name, as_dict=1)
		
	
	out = json.dumps(dict(([d.account_head, d.rate] for d in accounts)))
	return out
