// Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Item Summary By Project"] = {
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
				{ "value": "Quotation", "label": __("Quotation") },
				{ "value": "Sales Order", "label": __("Sales Order") },
				{ "value": "Delivery Note", "label": __("Delivery Note") }
			],
			default: "Quotation"
		},
		{
			fieldname: "consolidate",
			label: __("Consolidate"),
			fieldtype: "Select",
			options: [
				{ "value": "Consolidate By Document", "label": __("Consolidate By Document") },
				{ "value": "Consolidate By Project", "label": __("Consolidate By Project") }
			],
			default: "Consolidate By Project"
		},
		{
			fieldname: "bom_only",
			label: __("Show BOM"),
			fieldtype: "Select",
			options: [
				{ "value": "Without BOM", "label": __("Without BOM") },
				{ "value": "Only BOM", "label": __("Only BOM") },
				{ "value": "Combined", "label": __("Combined") },
				{ "value": "Consolidate BOM", "label": __("Consolidate BOM") }
			],
			default: "Consolidate BOM"
		}
	]
}