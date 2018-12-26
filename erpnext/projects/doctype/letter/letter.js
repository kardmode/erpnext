// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Letter', {
	setup: function(frm) {
		
		
		// frm.fields_dict['project'].get_query = function(doc) {
			// return {
				// filters: {
					// "company": doc.company
				// }
			// }
		// }
		
		frm.fields_dict['reference_name'].get_query = function(doc) {
			return {
				filters: {
					"company": doc.company
				}
			}
		}
		
	},
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			frm.set_value("posting_date",frappe.datetime.get_today());
			
		}
		else{
			if(!frm.doc.posting_date)
				frm.set_value("posting_date",frappe.datetime.get_today());
		}
	},
	// reference_doctype: function(frm){
		// if(frm.doc.reference_doctype != "Purchase Order"){
			
			// frm.fields_dict['reference_name'].get_query = function(doc) {
				// return {
					// filters: {
						// "company": doc.company
					// }
				// }
			// }
			
		// }
		// else{
			// frm.fields_dict['reference_name'].get_query = function(doc) {
				// return {
					// filters: {
						// "company": doc.company
					// }
				// }
			// }
		// }
	// },
	address: function(frm){
		if(frm.doc.address)
		{
			
			erpnext.utils.get_address_display(frm, 'address', 'address_display');
		}
		
	}
});
