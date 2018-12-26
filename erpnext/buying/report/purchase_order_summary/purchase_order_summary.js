// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Purchase Order Summary"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.get_today()
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
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			fieldname: "docstatus",
			label: __("Docstatus"),
			fieldtype: "Select",
			"reqd": 1,
			options: [
				{ "value": "Draft", "label": __("Draft") },
				{ "value": "Submitted", "label": __("Submitted") },
				{ "value": "Draft+Submitted", "label": __("Draft+Submitted") }
			],
			default: "Draft"
		},
	]
}