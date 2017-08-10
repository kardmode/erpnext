# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, cstr, date_diff, flt, formatdate, getdate
from frappe.model.document import Document
class OverlapError(frappe.ValidationError): pass

class WorkingHours(Document):
	def validate(self):
		self.validate_dates()

	def validate_dates(self):
		if self.from_date and self.to_date and (getdate(self.to_date) < getdate(self.from_date)):
			frappe.throw(_("End date cannot be before start date"))
		self.validate_back_dated_application()
		
	def validate_back_dated_application(self):
		if not self.name:
			# hack! if name is null, it could cause problems with !=
			self.name = "New Working Hours"

		for d in frappe.db.sql("""
			select name, from_date, to_date
			from `tabWorking Hours`
			where to_date >= %(from_date)s and from_date <= %(to_date)s
			and department != %(department)s and name != %(name)s""", {
				"from_date": self.from_date,
				"to_date": self.to_date,
				"department": self.department,
				"name": self.name
			}, as_dict = 1):
			
			if d:
				self.throw_overlap_error(d)
	def throw_overlap_error(self, d):
		msg = _("Already have entry between {0} and {1}").format(formatdate(d['from_date']), formatdate(d['to_date'])) \
			+ """ <br><b><a href="#Form/Working Hours/{0}">{0}</a></b>""".format(d["name"])
		frappe.throw(msg, OverlapError)
