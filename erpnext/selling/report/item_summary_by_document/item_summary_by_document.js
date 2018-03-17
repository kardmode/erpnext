// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Item Summary By Document"] = {
	
	"filters": [
		{
			"fieldname":"name",
			"label": __("Document"),
			"fieldtype": "Link",
			"options": function() {
				var format = frappe.query_report_filters_by_name.format.get_value();
				return format;
			},
			"get_query": function() {
				var format = frappe.query_report_filters_by_name.format.get_value();
				return{
					filters: [[format, "docstatus", "<", 2]],
					}
					
				
			},
			"on_change":function(me) {
				var format = frappe.query_report_filters_by_name.format.get_value();
				var docname = frappe.query_report_filters_by_name.name.get_value();

				
				/* frappe.call({
					method: "erpnext.selling.report.item_summary_by_document.item_summary_by_document.get_title",
					args: { "docname": docname,"doctype":format },
					callback: function(r) {
						if(r.message) {
							
							var title_filter = frappe.query_report_filters_by_name.title;
							title_filter.set_input(r.message);
				
						}
					}
				}) */
				me.trigger_refresh();
			},
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
			fieldname: "bom_only",
			label: __("Show BOM"),
			fieldtype: "Select",
			options: [
				{ "value": "Without BOM", "label": __("Without BOM") },
				{ "value": "Only BOM Items", "label": __("Only BOM") },
				{ "value": "With BOM", "label": __("With BOM") },
				{ "value": "Consolidate BOM", "label": __("Consolidate BOM") }
			],
			default: "Consolidate BOM"
		}
	]
}

frappe.ui.form.on("Item Summary By Document", "quotation", function(frm, cdt, cdn) {
	console.log("Hello");
})