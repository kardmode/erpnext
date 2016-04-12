// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Item Summary By Document"] = {
	"filters": [
		{
			"fieldname":"quotation",
			"label": __("Quotation"),
			"fieldtype": "Link",
			"options": "Quotation",
		},
		{
			"fieldname":"salesorder",
			"label": __("Sales Order"),
			"fieldtype": "Link",
			"options": "Sales Order",
		},
		{
			fieldname: "format",
			label: __("Format"),
			fieldtype: "Select",
			options: [
				{ "value": "Quotation", "label": __("Quotation") },
				{ "value": "SO", "label": __("Sales Order") }
			],
			default: "Quotation"
		}
	]
}
