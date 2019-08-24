// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Import Bill', {
	refresh: function(frm) {
		
		
		frm.toggle_display('document_name', frm.doc.__islocal);
		

	}
});
