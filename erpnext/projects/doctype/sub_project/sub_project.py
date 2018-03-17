# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import throw, _
from frappe.utils import cint, validate_email_add
from frappe.model.document import Document


class SubProject(Document):
	def on_update(self):
		self.update_nsm_model()
	def on_trash(self):
		# delete bin
		
		if self.check_if_child_exists():
			throw(_("Child sub projects exists for this sub project."))
		


		self.update_nsm_model()
	
	def update_nsm_model(self):
		frappe.utils.nestedset.update_nsm(self)

	def check_if_child_exists(self):
		return frappe.db.sql("""select name from `tabSub Project`
			where parent_sub_project = %s limit 1""", self.name)
	def convert_to_group_or_ledger(self):
		if self.is_group:
			self.convert_to_ledger()
		else:
			self.convert_to_group()

	def convert_to_ledger(self):
		if self.check_if_child_exists():
			frappe.throw(_("Sub Projects with child nodes cannot be converted to ledger"))
		else:
			self.is_group = 0
			self.save()
			return 1

	def convert_to_group(self):
		self.is_group = 1
		self.save()
		return 1

	
@frappe.whitelist()
def get_children(doctype, parent=None, company=None,project=None, is_root=False):

	if is_root:
		parent = ""
		
	sub_projects = frappe.db.sql("""select name as value,
		is_group as expandable
		from `tabSub Project`
		where docstatus < 2
		and ifnull(`parent_sub_project`,'') = %s
		and (`company` = %s or company is null or company = '')
		and (`project` = %s or project is null or project = '')
		order by name""", (parent, company,project), as_dict=1)

	
	return sub_projects

@frappe.whitelist()
def add_node():
	from frappe.desk.treeview import make_tree_args
	args = make_tree_args(**frappe.form_dict)
	
	if cint(args.is_root) or args.is_root == 'true':
		args.parent_sub_project = None
		args.parent = None
		
	frappe.get_doc(args).insert()

@frappe.whitelist()
def convert_to_group_or_ledger():
	args = frappe.form_dict
	return frappe.get_doc("Sub Project`", args.docname).convert_to_group_or_ledger()