// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Frame Calculator', {
	refresh: function(frm) {
		frm.add_custom_button(__("Calculate"), function() {
					frm.trigger("calculate");
				},null,"primary");
				
		frm.trigger("calculate_stock");
	},
	validate: function(frm) {
		frm.trigger("calculate_stock");

	},
	door_frame: function(frm) {
		frm.trigger("calculate_stock");

	},
	calculate_stock: function(frm) {
		var perimeter = 0;
		
		var material_length = frappe.mrp.convert_units(frm.doc.material_length_units,frm.doc.material_length);

		var finished_length = frappe.mrp.convert_units(frm.doc.finished_length_units,frm.doc.length);
		var finished_width = frappe.mrp.convert_units(frm.doc.finished_width_units,frm.doc.width);

		var conversion_factor = flt(1)/flt(material_length);

		
		if(cint(frm.doc.door_frame)){
			perimeter = 2*flt(finished_length)+ flt(finished_width);
			
		}
		else{
			perimeter = 2*flt(finished_length)+2*flt(finished_width);

		}
	
		var stock_required = flt(perimeter)/flt(material_length);		
		var finished_qty_per_stock = 1/flt(stock_required);
		var price_per_piece = perimeter * frm.doc.price_per_stock / material_length;
		var stock_summary = "Price Per Piece: " + price_per_piece.toFixed(5) + "<br>";
		
		
		frm.set_value("perimeter",perimeter);
		frm.set_value("conversion_factor", conversion_factor);

		frm.set_value("stock_required",stock_required);
		frm.set_value("finished_qty_per_stock", finished_qty_per_stock);
		frm.set_value("stock_summary", stock_summary);
	
	},
});

