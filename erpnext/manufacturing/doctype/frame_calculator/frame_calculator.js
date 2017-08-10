// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Frame Calculator', {
	refresh: function(frm) {

	},
	door_frame: function(frm) {
		if(cint(frm.doc.door_frame)){
			frm.trigger("calculate_door_frame_length");
		}
		else{
						frm.trigger("calculate_perimeter");

		}
	},
	calculate_stock: function(frm) {
		
		if (flt(frm.doc.material_length)>0){
			var stock = flt(frm.doc.perimeter)/flt(frm.doc.material_length);
			frm.set_value("stock_required",stock);
		}
		
	},
	calculate_perimeter: function(frm) {
		var perimeter = 2*flt(frm.doc.length)+2*flt(frm.doc.width);
		frm.set_value("perimeter",perimeter);
	},
	calculate_door_frame_length: function(frm) {
		var perimeter = 2*flt(frm.doc.length)+ flt(frm.doc.width);
		frm.set_value("perimeter",perimeter);
	},
	length: function(frm) {
		if(cint(frm.doc.door_frame)){
			frm.trigger("calculate_door_frame_length");
		}
		else{
						frm.trigger("calculate_perimeter");

		}
	},
	
	width: function(frm) {
		if(cint(frm.doc.door_frame)){
			frm.trigger("calculate_door_frame_length");
		}
		else{
						frm.trigger("calculate_perimeter");

		}
	},
	
});
