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
		
		for i,item in enumerate(item_list):
		
			from frappe.utils import strip_html_tags
			item.description = strip_html_tags(item.description)
			
			if item.manufacturer_part_no:
				item.brand = str(item.brand) + " " + str(item.manufacturer_part_no)

			text_uom = str(item.uom or item.stock_uom) + ' '*10
			text_qty = str(text_uom) + str(int(item.qty))
					
			row_count = i + 1					
			if filters.get("format") == "BoqAmount":

				if filters.get("simplified"):
					row = [row_count,item.item_name, item.description,text_qty,"",item.warranty_period]
				else:
					row = [row_count,item.item_name, item.description,item.brand,item.item_group,text_qty,"",item.warranty_period]
				
				
				data.append(row)
			elif filters.get("format") == "Boq":
				if filters.get("simplified"):
					row = [row_count,item.item_name, item.description,text_qty,item.warranty_period]
				else:
					row = [row_count,item.item_name, item.description,item.brand,item.item_group,text_qty,item.warranty_period]
				
				data.append(row)
			
			elif filters.get("format") == "Quotation":
				
				if filters.get("simplified"):
					row = [row_count,item.item_name, item.description,text_qty,item.rate,item.amount,item.warranty_period]
				else:
					row = [row_count,item.item_name, item.description,item.brand,item.item_group, text_qty,item.rate,item.amount,item.warranty_period]
				
				data.append(row)
		
		
		if filters.get("format") == "Quotation":
			
			if quotation.discount_amount:
				
				if filters.get("simplified"):
					row = ["","Discount","", "","",quotation.discount_amount]
				else:
					row = ["","Discount","","", "" ,"", "","",quotation.discount_amount]
				data.append(row)
				
			
			
			if filters.get("simplified"):
				row = ["","Total",quotation.in_words, "","",quotation.grand_total]
			else:
				row = ["","Total",quotation.in_words,"", "" ,"", "",quotation.grand_total,""]
			data.append(row)
		elif filters.get("format") == "BoqAmount":
			
			if quotation.discount_amount:
				if filters.get("simplified"):
					row = ["","Discount","", "",quotation.discount_amount]
				else:
					row = ["","Discount","","", "" ,"",quotation.discount_amount, ""]
				data.append(row)
			
			if filters.get("simplified"):
				row = ["","Total",quotation.in_words,quotation.grand_total, ""]
			else:
				row = ["","Total",quotation.in_words,"", "",quotation.grand_total,""]
			data.append(row)
		
		
		
		
		data.append([])
		
	return columns, data
	
def get_columns(filters):

	
	
	if filters.get("simplified"):
		columns = [
		_("Sr") + "::30",_("Item Name") + "::150", _("Description") + "::440", _("Qty") + "::80"
		]
	else:
		columns = [
			_("Sr") + "::30",_("Item Name") + "::150", _("Description") + "::440",_("Brand") + "::80"
			,_("Category") + "::80", _("Qty") + "::80"
		]
	
	if filters.get("format") == "Quotation":
		columns += [
			_("Rate") + ":Currency:80",_("Amount") + ":Currency:80",_("Remarks") + "::120"
		]
	elif filters.get("format") == "BoqAmount":
		columns += [
			_("Remarks") + "::120"
		]
	elif filters.get("format") == "Boq":
		columns += [
			_("Remarks") + "::120"
		]


		
	return columns


def get_quotation(conditions, filters):
	quotation_list = frappe.db.sql("""select * from tabQuotation where %s""" %
		conditions, filters, as_dict=1)
	if quotation_list:
		quotation = quotation_list[0].name
		item_list = frappe.db.sql("select item_name,description,item_group,qty,stock_uom,rate,amount,brand,manufacturer_part_no,warranty_period from `tabQuotation Item` t2 where t2.parent =%s order by idx", quotation, as_dict = 1)
		return item_list,quotation_list[0]
	else:
		return None,None

def get_conditions(filters):
	conditions = ""
	if not filters.get("quotation"):
		return conditions,filters
	
	if filters.get("quotation"): conditions = "name = %(quotation)s"


	return conditions, filters
