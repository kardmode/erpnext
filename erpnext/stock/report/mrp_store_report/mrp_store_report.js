// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["MRP Store Report"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("Company")
		},
		/* {
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Group"
		}, */
		{
			"fieldname": "item_code",
			"label": __("Item Code"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item",
			"get_query": function() {
				return {
					query: "erpnext.controllers.queries.item_query"
				}
			}
		},
		{
			"fieldname": "location",
			"label": __("Store Location"),
			"fieldtype": "Link",
			"width": "80",
			"options": "MRP Store Location",
			"get_query": function() {
				return{
					filters: [["MRP Store Location", "disabled", "=", 0],
					["MRP Store Location", "company", "=", frappe.query_report_filters_by_name.company.get_value()]],
				}
					
				
			},
		},
		
	]
}

