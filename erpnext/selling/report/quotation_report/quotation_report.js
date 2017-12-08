// Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Quotation Report"] = {
	"filters": [
		{
			"fieldname":"quotation",
			"label": __("Quotation Name"),
			"fieldtype": "Link",
			"options": "Quotation",
		},
		{
			fieldname: "format",
			label: __("Format"),
			fieldtype: "Select",
			options: [
				{ "value": "Boq", "label": __("Boq") },
				{ "value": "BoqAmount", "label": __("Boq With Amount") },
				{ "value": "Quotation", "label": __("Quotation") }
			],
			default: "Quotation"
		},
		{
			fieldname: "simplified",
			label: __("Simplified"),
			fieldtype: "Check",
			default: false
		}
		
	]
}
