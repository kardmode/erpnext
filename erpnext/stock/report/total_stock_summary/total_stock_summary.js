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
			"default": "Warehouse",
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("Company"),
			"depends_on": "eval: doc.group_by != 'Company'",
		},
		{
			"fieldname":"hide_disabled",
			"label": __("Hide Disabled Warehouse"),
			"fieldtype": "Check",
			"reqd": 0,
			"default": 1,
		},
		{
			"fieldname":"hide_positive",
			"label": __("Hide Positive"),
			"fieldtype": "Check",
			"reqd": 0,
		},
		{
			"fieldname":"hide_negative",
			"label": __("Hide Negative"),
			"fieldtype": "Check",
			"reqd": 0,
		},
		{
			"fieldname":"hide_zero",
			"label": __("Hide Zero"),
			"fieldtype": "Check",
			"width": "80",
			"reqd": 0,
		},
	]
}
