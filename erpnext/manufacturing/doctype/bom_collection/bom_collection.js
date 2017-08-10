// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('BOM Collection', {
	refresh: function(frm) {

	}
});
frappe.ui.form.on('BOM Builder Item', {
	
	side:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		get_dimensions(d)
	},
	
	bb_item: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		get_stock_uom(d)
		
	},
});

var get_stock_uom = function(d) {
	if (d.side == "hardware")
	{
		if(d.bb_item) {
			
			frappe.call({
				method:'erpnext.stock.get_item_details.get_default_uom',
				args:{
					item_code: d.bb_item
				},
				callback:function (r) {
					frappe.model.set_value(d.doctype, d.name, "requom", r.message);
				}
			})

			
		}
		
	}
}
var get_dimensions = function(d) {
	if(!d.side) return;
	var side = d.side;

	
	frappe.call({
		method:'erpnext.manufacturing.doctype.bom.bom.get_part_details',
		args:{
			part: side,
			item_code:d.bb_item,
		},
		callback:function (r) {
			frappe.model.set_value(d.doctype, d.name, "requom", r.message[1]);
		}
	})

}