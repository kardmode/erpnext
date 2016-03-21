# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, flt, getdate, rounded

from frappe import msgprint, _


def execute(filters=None):
	if not filters: filters = {}
	
	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	data = []
	if not conditions:
		return columns, data
	
	item_list,quotation = get_quotation(conditions, filters)
	
	
	if quotation:
		letter_head = frappe.db.get_value("Company", quotation.company, "default_letter_head") or ""
		filters["letter_head"] = letter_head
		
		
		
		row_count = 0
		section_count = 0
		total = 0
		
		first_item = item_list[0]
		has_header = 0
		has_headers = 0
		count = 0 
		if str(first_item.item_group).lower() in ["header1","header2","header3"]:
			has_header = 1

		
		for item in item_list:
			if count > 0 and str(item.item_group).lower() in ["header1","header2","header3"]:
				has_headers = 1
		
			count = count +1
			from frappe.utils import strip_html_tags
			item.description = strip_html_tags(item.description)
			
			if item.manufacturer_part_no:
				item.brand = str(item.brand) + " " + str(item.manufacturer_part_no)

			
			item.stock_uom  += ' '*10
			
			item.qty = str(item.stock_uom) + str(int(item.qty))
								
			if item.item_group.lower() in ["header1","header2","header3"]:
				
				# New Section
				if section_count:
					if filters.get("format") == "Quotation":
						row = ["","Total","","", "" ,"", "","",total]
						data.append(row)
						data.append([])	
					elif filters.get("format") == "BoqAmount":
						row = ["","Total","","", "" ,"", "",total]
						data.append(row)
						data.append([])	
					elif filters.get("format") == "Boq":
						data.append([])	
					
				row_count = 0
				total = 0
				section_count = section_count + 1
				
				if not filters.get("format") == "Summary":
					row = ["",item.item_name, item.description,"","","", "","",""]
				else:
					row = [section_count,item.item_name, item.description,item.rate]
				data.append(row)	
				
				
				
				
			else:
				if row_count == 0 and section_count == 0:
					section_count = section_count + 1
					if not filters.get("format") == "Summary":
						row = ["","No Header for first section","","","","","","",""]					
						data.append(row)
					else:
						row = [section_count,"No Header for first section","",""]					
						data.append(row)
					
					
				total = total + item.amount
				
				if filters.get("format") == "BoqAmount":
					row_count = row_count + 1
					row = [row_count,item.item_name, item.description,item.brand,item.item_group,item.warranty_period, item.qty,"",""]
					data.append(row)	
				elif not filters.get("format") == "Summary":
					row_count = row_count + 1
					row = [row_count,item.item_name, item.description,item.brand,item.item_group,item.warranty_period, item.qty,item.rate,item.amount]
					data.append(row)
			
		if filters.get("format") == "Quotation":
		
			row = ["","Total","","", "" ,"", "","",total]
			data.append(row)
			data.append([])
			
			if quotation.discount_amount:
				row = ["","Discount Amount","","", "" ,"", "","",quotation.discount_amount]
				data.append(row)
				data.append([])
			
			
			
			row = ["","Grand Total",quotation.in_words,"", "" ,"", "","",quotation.grand_total]
			data.append(row)
		elif filters.get("format") == "BoqAmount":
		
			row = ["","Total","","", "" ,"", "",total]
			data.append(row)
			data.append([])
			
			if quotation.discount_amount:
				row = ["","Discount Amount","","", "" ,"", "","",quotation.discount_amount]
				data.append(row)
				data.append([])
			
			row = ["","Grand Total",quotation.in_words,"", "" ,"", "",quotation.grand_total]
			data.append(row)
		elif filters.get("format") == "Summary":
			data.append([])
			
			if quotation.discount_amount:
				row = ["","Discount Amount","","", "" ,"", "","",quotation.discount_amount]
				data.append(row)
				data.append([])
			
			row = ["","Grand Total",quotation.in_words,quotation.grand_total]
			data.append(row)
		
		data.append([])
		
		if not has_header and has_headers:
			msgprint(_("Your items have headers but the first item is not a header."))

	return columns, data
	
def get_columns(filters):

	columns = [
		_("Sr") + "::30",_("Item Name") + "::150", _("Description") + "::440",_("Brand") + "::80",_("Category") + "::80"
		,_("Remarks") + "::120", _("Qty") + "::80"
	]
	
	if filters.get("format") == "Quotation":
		columns += [
			_("Rate") + ":Currency:80",_("Amount AED") + ":Currency:80"
		]
	elif filters.get("format") == "BoqAmount":
		columns += [
			_("Amount AED") + ":Currency:80"
		]
	
	elif filters.get("format") == "Summary":
		columns = [
			_("Sr") + "::30",_("Item Name") + "::150", _("Description") + "::440",_("Amount AED") + ":Currency:80"
		]
	
	

		
	return columns


def get_quotation(conditions, filters):
	quotation_list = frappe.db.sql("""select * from tabQuotation where %s""" %
		conditions, filters, as_dict=1)
	
	quotation = quotation_list[0].name
	item_list = frappe.db.sql("select item_name,description,item_group,qty,stock_uom,rate,amount,brand,manufacturer_part_no,warranty_period from `tabQuotation Item` t2 where t2.parent =%s order by idx", quotation, as_dict = 1)
	return item_list,quotation_list[0]

def get_conditions(filters):
	conditions = ""
	if not filters.get("quotation"):
		return conditions,filters
	
	if filters.get("quotation"): conditions = "name = %(quotation)s"


	return conditions, filters
