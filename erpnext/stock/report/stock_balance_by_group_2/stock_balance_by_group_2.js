// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Balance By Group 2"] = {
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
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item"
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Group",
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Warehouse",
			"get_query": function() {
				return{
					filters: [["Warehouse", "disabled", "=", 0]],
				}
					
				
			},
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
			"label": __("Hide Disabled"),
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
