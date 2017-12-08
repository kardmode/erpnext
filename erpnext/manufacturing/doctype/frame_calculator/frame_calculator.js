// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Frame Calculator', {
	validate: function(frm) {
					frm.trigger("calculate_stock");

	},
	refresh: function(frm) {
			frm.trigger("calculate_stock");

	},
	door_frame: function(frm) {
					frm.trigger("calculate_stock");

	},
	calculate_stock: function(frm) {
		var perimeter = 0;
		
		var material_length = convert_units(frm.doc.material_length_units,frm.doc.material_length);

		var finished_length = convert_units(frm.doc.finished_length_units,frm.doc.length);
		var finished_width = convert_units(frm.doc.finished_width_units,frm.doc.width);

		var conversion_factor = flt(1)/flt(material_length);

		
		if(cint(frm.doc.door_frame)){
			perimeter = 2*flt(finished_length)+ flt(finished_width);
			
		}
		else{
			perimeter = 2*flt(finished_length)+2*flt(finished_width);

		}
		frm.set_value("perimeter",perimeter);
		var stock_required = flt(perimeter)/flt(material_length);		
		var finished_qty_per_stock = 1/flt(stock_required);
		frm.set_value("conversion_factor", conversion_factor);

		frm.set_value("stock_required",stock_required);
		frm.set_value("finished_qty_per_stock", finished_qty_per_stock);
	},
	
	length: function(frm) {
		frm.trigger("calculate_stock");
	},
	
	width: function(frm) {
		frm.trigger("calculate_stock");
	},
	material_length: function(frm) {
		frm.trigger("calculate_stock");
	},
});

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
