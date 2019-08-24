# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class ProjectBreakdown(Document):
	def validate(self):
		pass
			
		
	def get_file_name(self):
		return "{0}.{1}".format(self.name.replace(" ", "-").replace("/", "-"), "xlsx")
	
	def get_report_content(self):
	
		columns = []
		data = []
	
		spreadsheet_data = self.get_spreadsheet_data(columns, data)
		
		from frappe.utils.xlsxutils import make_xlsx

		xlsx_file = make_xlsx(spreadsheet_data, "Project Report")
		return xlsx_file.getvalue()
		
	@staticmethod
	def get_spreadsheet_data(columns, data):
		out = [[_(df.label) for df in columns], ]
		for row in data:
			new_row = []
			out.append(new_row)
			for df in columns:
				new_row.append(frappe.format(row[df.fieldname], df, row))

		return out

@frappe.whitelist()
def download(name):
	'''Download report locally'''
	project_breakdown = frappe.get_doc('Project Breakdown', name)
	project_breakdown.check_permission()
	data = project_breakdown.get_report_content()

	if not data:
		frappe.msgprint(_('No Data'))
		return	

	frappe.local.response.filecontent = data
	frappe.local.response.type = "download"
	frappe.local.response.filename = project_breakdown.get_file_name()
	
@frappe.whitelist()			
def get_details(project):
	sub_projects = frappe.db.sql("""select name from `tabSub Project` where project = %s and docstatus < 2 order by title""", project,as_dict=1)
	new_subprojects = []
	for sub_project in sub_projects:
		locations = get_sub_project_details(project)		
		sub_project["locations"] = locations
		new_subprojects.append(sub_project)

	return new_subprojects

@frappe.whitelist()			
def get_details2(project):
	sub_projects = frappe.db.sql("""select name from `tabProject` where parent_project = %s and docstatus < 2 order by title""", project,as_dict=1)

	new_subprojects = []
	for sub_project in sub_projects:
		locations = get_sub_project_details(sub_project.name)		
		sub_project["locations"] = locations
		new_subprojects.append(sub_project)

	return new_subprojects
	
def get_details2(project):
	sub_projects = frappe.db.sql("""select name from `tabProject` where parent_project = %s and docstatus < 2 order by title""", project,as_dict=1)
	new_subprojects = []
	for sub_project in sub_projects:
		locations = get_sub_project_details(sub_project.name)		
		sub_project["locations"] = locations
		new_subprojects.append(sub_project)

	return new_subprojects
		
@frappe.whitelist()			
def get_sub_project_details(sub_project):
	
	locations = frappe.db.sql("""select label,location from `tabJob Location` where parent = %s order by idx""", sub_project,as_dict=1)
	
	return locations
			
