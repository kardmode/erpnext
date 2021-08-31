// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Import Bill', {
	refresh: function(frm) {
		frm.toggle_display('document_name', frm.doc.__islocal);
		
		frm.add_custom_button(__('Get Summary'),
		function() {
			frm.trigger('get_summary');
			
		});
		
	},
	validate: function(frm) {
		frm.doc.summary = '';
	},
	get_summary: function(frm) {
		if(!frm.doc.__islocal)
		{
			frappe.call({
				doc: frm.doc,
				method: "get_summary",
				freeze: true,
				callback: function(r) {
					frm.refresh();
					// cur_frm.dirty();
				}
			});

			
		}
	},
});
