// Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Project Summary"] = {
	"filters": [
		{
			"fieldname":"project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project",
		},
		{
			fieldname: "format",
			label: __("Format"),
			fieldtype: "Select",
			options: [
				{ "value": "BOQ", "label": __("BOQ") },
				{ "value": "Quotation", "label": __("Quotation") },
				{ "value": "Summary", "label": __("Summary") }
			],
			default: "Summary"
		},
		{
			fieldname: "document",
			label: __("Document"),
			fieldtype: "Select",
			options: [
				{ "value": "Quotation", "label": __("Quotation") },
				{ "value": "Sales Order", "label": __("Sales Order") },
				{ "value": "Sales Invoice", "label": __("Sales Invoice") },
				{ "value": "Delivery Note", "label": __("Delivery Note") },
			],
			default: "Quotation"
		}
		
	]
}
