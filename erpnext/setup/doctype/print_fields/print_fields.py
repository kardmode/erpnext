# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from frappe.utils.jinja import validate_template

class PrintFields(Document):
	def validate(self):
		validate_template(self.print_field)

@frappe.whitelist()
def get_print_fields(template_name, doc):
	if isinstance(doc, basestring):
		doc = json.loads(doc)

	print_fields = frappe.get_doc("Print Fields", template_name)
	return frappe.render_template(print_fields.print_field, doc)