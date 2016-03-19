// Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Item Summary By Project"] = {
	"filters": [
		{
			"fieldname":"project_name",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project",
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
