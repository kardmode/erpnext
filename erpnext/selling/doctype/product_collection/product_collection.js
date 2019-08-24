// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Product Collection', {
	refresh: function(frm) {

	},
	
	validate: function(frm) {
		if(frm.doc.item_code)
		{
			
			var code = frm.doc.item_code;
			var newword = code.trim();
			frm.doc.item_code = newword.trim();
		}
	},
	
	item_code: function(frm) {
		
		if(frm.doc.item_code)
		{
			
			var code = frm.doc.item_code;
			var newword = code.trim();

			frm.set_value("item_code", newword.trim());
		}

	},
	
});

cur_frm.cscript.onload = function() {
	// set add fetch for item_code's item_name and description
	cur_frm.add_fetch('item_code', 'stock_uom', 'uom');
	cur_frm.add_fetch('item_code', 'description', 'description');
}