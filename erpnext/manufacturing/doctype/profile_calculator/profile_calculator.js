// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Profile Calculator', {
	refresh: function(frm) {
		frm.trigger("calculate");
	},
	
	validate: function(frm) {
		frm.trigger("calculate");
	},
	
	calculate:function(frm) {
			
		var doc = frm.doc;
		if (!(frm.doc.material_length)){
			msgprint(__("Length of material missing"));
			return;
		}
		
		if (!(frm.doc.finished_length)){
			msgprint(__("Length of finished good missing"));
			return;
		}
		
		get_dimensions(frm);
		
	
	},
});

/* 
cur_frm.cscript.refresh = function(doc) {
	cur_frm.disable_save();
}
 */
 
var convert_units = function(unit,value) {
	if (unit == "ft")
		finalvalue = flt(value) * flt(.3048);
	else if (unit == "cm")
		finalvalue = flt(value) * flt(.01);
	else if (unit == "mm")
		finalvalue = flt(value) * flt(0.001);
	else if (unit == "in")
		finalvalue = flt(value) * flt(.0254);
	else
		finalvalue = flt(value);
	return finalvalue;
}
var get_dimensions = function(frm) {
	
	var material_length = convert_units(frm.doc.material_length_units,frm.doc.material_length);
	var finished_length = convert_units(frm.doc.finished_length_units,frm.doc.finished_length);
	
	var conversion_factor = flt(1)/flt(material_length);
	var stock_required = flt(finished_length) / flt(material_length);
	var finished_qty_per_stock = 1/flt(stock_required);
	
	frm.set_value("stock_required", stock_required);
	frm.set_value("conversion_factor", conversion_factor);
	frm.set_value("finished_qty_per_stock", finished_qty_per_stock);

}
