// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Item Summary By Document"] = {
	
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_default('company'),
			"on_change": function(query_report) {
				frappe.query_report.set_filter_value('name', "");
			}	
		},
		{
			"fieldname":"format",
			"label": __("Format"),
			"fieldtype": "Select",
			"options": [
				{ "value": "Quotation", "label": __("Quotation") },
				{ "value": "Sales Order", "label": __("Sales Order") },
				{ "value": "Delivery Note", "label": __("Delivery Note") },
				{ "value": "Product Bundle", "label": __("Product Bundle") }
			],
			'default': "Quotation",
			"on_change": function(query_report) {
				frappe.query_report.set_filter_value('name', "");
			}			
		},
		{
			"fieldname":"name",
			"label": __("Document"),
			"fieldtype": "Dynamic Link",
			"get_options": function() {
				var format = frappe.query_report.get_filter_value('format');
				if(!format) {
					frappe.throw(__("Please select Format first"));
				}
				return format;
			},
			
			
			"get_query": function() {
				var format = frappe.query_report.get_filter_value('format');
				var company = frappe.query_report.get_filter_value('company');

				return {
					filters: [[format, "docstatus", "<", 2],[format,"Company","=",company]],
				}				
			}
		},
		{
			fieldname: "bom_only",
			label: __("Show BOM"),
			fieldtype: "Select",
			options: [
				{ "value": "Without BOM", "label": __("Without BOM") },
				{ "value": "Only BOM Items", "label": __("Only BOM") },
				{ "value": "With BOM", "label": __("With BOM") },
				{ "value": "Consolidate BOM", "label": __("Consolidate BOM") }
			],
			default: "With BOM"
		}
	]
}