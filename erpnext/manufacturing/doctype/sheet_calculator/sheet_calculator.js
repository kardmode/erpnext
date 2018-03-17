// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sheet Calculator', {
	refresh: function(frm) {
		frm.trigger("calculate_sheets");
	},
	
	validate: function(frm) {
		frm.trigger("calculate_sheets");
	},
	
	calculate_sheets:function(frm) {
			
		var doc = frm.doc;
		if (!(frm.doc.sheet_length && frm.doc.sheet_width && frm.doc.sheet_height)){
			msgprint(__("Depth, width or height of sheet missing"));
			return;
		}
		
		if (!(frm.doc.panel_length && frm.doc.panel_width && frm.doc.panel_height)){
			msgprint(__("Depth, width or height of panel missing"));
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
	
	var length = convert_units(frm.doc.sheet_length_units,frm.doc.sheet_length);
	var width = convert_units(frm.doc.sheet_width_units,frm.doc.sheet_width);
	var height = convert_units(frm.doc.sheet_height_units,frm.doc.sheet_height);

	
	var perimeter = 2*flt(length)+2*flt(width);
	var farea = flt(length) * flt(width);
	var fvolumecubm = flt(length) * flt(width) * flt(height);
	var fvolumecft = fvolumecubm * 35.3147;
	
	var depthPanel = convert_units(frm.doc.panel_length_units,frm.doc.panel_length);
	var widthPanel = convert_units(frm.doc.panel_width_units,frm.doc.panel_width);
	
	
	var cft_conversion_factor = 1/flt(fvolumecft);
	
	var conversion_factor = 1/flt(farea);
	var panelarea = flt(depthPanel) * flt(widthPanel);

	var num_of_sheets = flt(panelarea) / flt(farea);
	var finished_qty_per_stock = 1/flt(num_of_sheets);
	
	frm.set_value("finished_qty_per_stock", finished_qty_per_stock);
	frm.set_value("num_of_sheets", num_of_sheets);
	frm.set_value("conversion_factor", conversion_factor);
	frm.set_value("cft_conversion_factor", cft_conversion_factor);

}