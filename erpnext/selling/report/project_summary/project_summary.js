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
				{ "value": "Boq", "label": __("Boq") },
				{ "value": "Quotation", "label": __("Quotation") },
				{ "value": "Summary", "label": __("Summary") }
			],
			default: "Quotation"
		}
		
	]
}
