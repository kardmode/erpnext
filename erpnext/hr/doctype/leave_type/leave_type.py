# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.model.document import Document

class LeaveType(Document):
	def validate(self):
		if self.is_lwp ==1:
			self.is_paid_in_advance = 0
			self.is_present_during_period = 0