# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cstr, flt, cint,nowtime, nowdate, add_days, comma_and, getdate
from frappe import msgprint, _

class MRPJobOrder(Document):
	def validate(self):
		self.validate_dates()
		self.calculate_total_qty()
		
	def validate_dates(self):
	
		if self.posting_date and self.due_date:
			if getdate(self.posting_date)>getdate(self.due_date):
				pass

		else:
			pass

		
	def calculate_total_qty(self):
		total_qty = 0
		if self.get("items"):
			for d in self.items:
				if d.qty and is_number(d.qty):
					total_qty = total_qty + flt(d.qty)
		
		self.total_qty = total_qty
		
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False