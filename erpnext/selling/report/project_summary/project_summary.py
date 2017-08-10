# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, flt, getdate, rounded,money_in_words

from frappe import msgprint, _


def execute(filters=None):
	if not filters: filters = {}
	
	columns = get_columns(filters)
	data = []
	
	if not filters.get("project"):
		return columns, data
	
	format = filters.get("format")
	project = filters.get("project")
	doctype = filters.get("doctype")

	

	project_info = get_project(project)
	if project_info:
		start_date = project_info[0].expected_start_date
	row = ["",project,start_date,"", "" ,"", "","",""]
	data.append(row)
	
	sp_list = get_sub_projects(project)
	
	project_total = 0
	project_total_qty = 0
	for sp in sp_list:
		doc_list = get_documents(project,doctype,sp)

		group_total = 0
		group_qty = 0
		if format in ["Prices","BOQ","Delivery Note"]:
			for d in doc_list:		
				row = ["",d.title,sp.sub_project,"", "" ,"","", d.room_qty,"",""]
				data.append(row)
				
				item_list = get_items(d.name, doctype)
		
				for i,item in enumerate(item_list):
					item_details = get_item_details(item.name)
					from frappe.utils import strip_html_tags
					item.description = strip_html_tags(item.description)
					
					brand = ""
					warranty_period = ""
					manufacturer_part_no = ""
					if manufacturer_part_no:
						brand = str(brand) + " " + str(brand)
										
					row = [str(i+1),item.item_name, item.description,brand,item.item_group,warranty_period,item.uom,item.qty,item.rate,item.amount]
					data.append(row)
					group_qty = group_qty + item.qty
	
				if format in ["BOQ","Delivery Note"]:
					row = ["","Total","","", "" ,"","", group_qty,"",d.grand_total]
				else:
					row = ["","Total","","", "" ,"", "","","",d.grand_total]
				data.append(row)
				
				group_total = group_total + d.grand_total
			
			project_total = project_total + group_total
			project_total_qty = project_total_qty + group_qty
		elif format == "Summary":
			row = ["",sp.sub_project,"", "" ,""]
			data.append(row)

			for i,d in enumerate(doc_list):
				group_total = group_total + d.grand_total
				group_qty = group_qty + d.room_qty
				rate = flt(d.grand_total)/flt(d.room_qty)
				row = [str(i+1),d.title,"","",d.room_qty,rate,d.grand_total]
				data.append(row)
			
			row = ["","Total","","",group_qty,"",group_total]
			data.append(row)

			project_total = project_total + group_total
			project_total_qty = project_total_qty + group_qty
	
	total_amount_in_words = ""
	if project_total:
		total_amount_in_words = money_in_words(project_total, "AED")
	if format == "Summary":
		row = ["","Project Total",total_amount_in_words,"", project_total_qty,"",project_total]
		

	elif format in ["BOQ","Delivery Note"]:
		row = ["","Project Total","","","","","", project_total_qty,"",""]
	else:
		row = ["","Project Total",total_amount_in_words,"","","","", "","",project_total]
	data.append(row)

				
	return columns, data
	
def get_columns(filters):

	columns = [
		_("Sr") + "::30",_("Item Name") + "::150",_("Description") + "::150",_("Brand") + "::80",_("Category") + "::80"
		,_("Remarks") + "::120",_("UOM") + "::80",_("Qty") + "::80"
	]
	
	if filters.get("format") in ["Prices"]:
		columns += [
			_("Rate") + "::80",_("Amount") + "::80"
		]
	elif filters.get("format") == "Summary":
		columns = [
			_("Sr") + "::30",_("Item Name") + "::150",_("Description") + "::150",_("UOM") + "::80",_("Qty") + "::80",_("Rate") + "::80",_("Amount") + "::80"
		]
	

		
	return columns
	
def get_project(project):
	sp_list = frappe.db.sql("""select expected_start_date,expected_end_date from `tabProject` where name = %s""",project, as_dict=1)
	return sp_list
	
def get_sub_projects(project):
	sp_list = frappe.db.sql("""select sub_project from `tabProject Item` where parent = %s order by idx ASC""",project, as_dict=1)
	return sp_list

def get_documents(project,doctype,sub_project=None):
	ss_list = []
	if sub_project:
		title = sub_project.sub_project
		if title == "Misc.":
			if doctype == "Quotation":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabQuotation` where project = %s and sub_project is NULL and docstatus < 2 order by title * 1""", project,as_dict = 1)
			
			elif doctype == "Sales Order":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabSales Order` where project = %s and sub_project is NULL and docstatus < 2 order by title * 1""", project,as_dict = 1)

			elif doctype == "Sales Invoice":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabSales Invoice` where project = %s and sub_project is NULL and docstatus < 2 order by title * 1""", project,as_dict = 1)
		
			elif doctype == "Delivery Note":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabDelivery Note` where project = %s and sub_project is NULL and docstatus < 2 order by title * 1""", project,as_dict = 1)
	
		else:
		
			if doctype == "Quotation":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabQuotation` where project = %s and sub_project = %s and docstatus < 2 order by title * 1""", [project,title],as_dict = 1)
			
			elif doctype == "Sales Order":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabSales Order` where project = %s and sub_project = %s and docstatus < 2 order by title * 1""", [project,title],as_dict = 1)

			elif doctype == "Sales Invoice":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabSales Invoice` where project = %s and sub_project = %s and docstatus < 2 order by title * 1""", [project,title],as_dict = 1)
	
			elif doctype == "Delivery Note":
				ss_list = frappe.db.sql("""select name,title,net_total,discount_amount,grand_total,room_qty from `tabDelivery Note` where project = %s and sub_project is NULL and docstatus < 2 order by title * 1""", project,as_dict = 1)
	
	else:
		frappe.throw(_("No Sub Projects Provided"))
	
	return ss_list

def get_items(name,doctype,sub_project=None):
	item_list = []


	if doctype == "Quotation":
		item_list = frappe.db.sql("select item_name,description,item_group,qty,uom,rate,amount from `tabQuotation Item` t2 where t2.parent =%s order by idx", name, as_dict = 1)
	
	elif doctype == "Sales Order":
		item_list = frappe.db.sql("select item_name,description,item_group,qty,uom,rate,amount from `tabSales Order Item` t2 where t2.parent =%s order by idx", name, as_dict = 1)

	elif doctype == "Sales Invoice":
		item_list = frappe.db.sql("select item_name,description,item_group,qty,uom,rate,amount from `tabSales Invoice Item` t2 where t2.parent =%s order by idx", name, as_dict = 1)
	elif doctype == "Delivery Note":
		item_list = frappe.db.sql("select item_name,description,item_group,qty,uom,rate,amount from `tabDelivery Note Item` t2 where t2.parent =%s order by idx", name, as_dict = 1)

	return item_list

def get_item_details(name):
	item_details = {}
	# item_details.setdefault(d.name, d)

	return frappe.db.sql("""select brand, warranty_period,manufacturer_part_no from `tabItem` where name = %s""",name, as_dict=1)