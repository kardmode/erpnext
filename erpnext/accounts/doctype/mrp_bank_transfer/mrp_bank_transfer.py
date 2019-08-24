# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class MRPBankTransfer(Document):
	def validate(self):
		self.validate_dates()
		self.set_total_in_words()
		
	def validate_dates(self):
		pass
		
	def set_total_in_words(self):
		from frappe.utils import money_in_words

		if self.meta.get_field("base_in_words"):
			base_amount = abs(self.base_grand_total)
			self.base_in_words = money_in_words(base_amount, self.company_currency)

		if self.meta.get_field("in_words"):
			if self.transfer_amount:
				amount = abs(self.transfer_amount)
			else:
				amount = 0
			self.in_words = money_in_words(amount, self.currency_of_transfer)
