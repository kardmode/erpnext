// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Balance By Group"] = {
	"filters": [
	{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.sys_defaults.year_start_date,
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Group"
		},
		
		{
			"fieldname": "report_style",
			"label": __("Report Style"),
			"fieldtype": "Select",
			"options":["By Item","By Group"],
			"default":"By Group"
		},
		{
			"fieldname": "hide_disabled",
			"label": __("Hide Disabled Warehouses"),
			"fieldtype": "Check",
			"default":1
		},
		{
			"fieldname": "hide_zero_qty",
			"label": __("Hide Zero Qty"),
			"fieldtype": "Check",
			"default":0
		},
		{
			"fieldname": "hide_negative_qty",
			"label": __("Hide Negative Qty"),
			"fieldtype": "Check",
			"default":0
		},
	]
}
