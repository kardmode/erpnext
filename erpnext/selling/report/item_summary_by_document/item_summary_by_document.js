// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Item Summary By Document"] = {
	
	"filters": [
		{
			"fieldname":"title",
			"label": __("Title"),
			"fieldtype": "Data",
		},
		{
			"fieldname":"name",
			"label": __("Document"),
			"fieldtype": "Link",
			"options": function() {
				var format = frappe.query_report_filters_by_name.format.get_value();
				if (format == "Quotation")
					return "Quotation";
				else	
					return "Sales Order";
			},
			"get_query": function() {
				var format = frappe.query_report_filters_by_name.format.get_value();
				if (format == "Quotation")
				{
					return{
					filters: [["Quotation", "docstatus", "<", 2]],
					}
					
				} else{
					return{
					filters: [["Sales Order", "docstatus", "<", 2]],
					}
				}	
					
				
			},
			"on_change":function(me) {
				var format = frappe.query_report_filters_by_name.format.get_value();
				var docname = frappe.query_report_filters_by_name.name.get_value();

				
				frappe.call({
					method: "erpnext.selling.report.item_summary_by_document.item_summary_by_document.get_title",
					args: { "docname": docname,"doctype":format },
					callback: function(r) {
						if(r.message) {
							
							var title_filter = frappe.query_report_filters_by_name.title;
							title_filter.set_input(r.message);
				
						}
					}
				})
				me.trigger_refresh();
			},
		},
		{
			fieldname: "format",
			label: __("Format"),
			fieldtype: "Select",
			options: [
				{ "value": "Quotation", "label": __("Quotation") },
				{ "value": "Sales Order", "label": __("Sales Order") }
			],
			default: "Quotation"
		},
		{
			fieldname: "bom_only",
			label: __("Show BOM"),
			fieldtype: "Select",
			options: [
				{ "value": "Without BOM", "label": __("Without BOM") },
				{ "value": "With BOM", "label": __("With BOM") },
				{ "value": "Combined", "label": __("Combined") }
			],
			default: "Without BOM"
		}
	]
}

frappe.ui.form.on("Item Summary By Document", "quotation", function(frm, cdt, cdn) {
	console.log("Hello");
})