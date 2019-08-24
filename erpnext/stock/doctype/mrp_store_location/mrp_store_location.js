// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Store Location', {
	refresh: function(frm) {
		frm.toggle_display('location_name', frm.doc.__islocal);
	}
});
