// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Total Stock Summary"] = {
	"filters": [
		{
			"fieldname":"group_by",
			"label": __("Group By"),
			"fieldtype": "Select",
			"width": "80",
			"reqd": 1,
			"options": ["Warehouse", "Company"],
			"default": "Warehouse"
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Company"
		},
		{
			"fieldname": "hide_disabled",
			"label": __("Hide Disabled"),
			"fieldtype": "Check",
			"default":1
		},
		{
			"fieldname": "hide_negative_qty",
			"label": __("Hide Negative Qty"),
			"fieldtype": "Check",
			"default":0
		},
	]
}
