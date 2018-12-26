
// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Balance Main"] = {
	"filters": [
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item"
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Group",
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Warehouse",
			"get_query": function() {
				return{
					filters: [["Warehouse", "disabled", "=", 0]],
				}
					
				
			},
		},
		{
			"fieldname": "report_style",
			"label": __("Report Style"),
			"fieldtype": "Select",
			"options":["Default","Condensed"],
			"default":"Default"
		},
	]
}
