// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Store Item', {
	setup: function(frm) {
		// frm.add_fetch("item", "description", "description");
		// frm.add_fetch("item", "image", "image");
		// frm.add_fetch("item", "item_name", "item_name");
		frm.add_fetch("item_code", "stock_uom", "stock_uom");
	
		frm.set_query("item_code", function() {
				return {
					query: "erpnext.controllers.queries.item_query"
				};
		});
		frm.set_query("location","items", function() {
			return {
				filters: {
					"disabled":0,
				}
			};
		});
	},
	refresh: function(frm) {
	}
});
