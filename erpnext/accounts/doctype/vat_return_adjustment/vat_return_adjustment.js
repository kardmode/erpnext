// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('VAT Return Adjustment', {
	setup: function(frm) {
		frm.add_fetch("document", 'posting_date', 'document_date');
	},
	onload: function(frm) {
		frm.set_query('document', function(doc) {
			return {
				filters: {
					"company": doc.company,
					"docstatus":1
				}
			};
		});
	},
	refresh: function(frm) {

	},
	
});
