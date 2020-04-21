// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sheet Calculator', {
	refresh: function(frm) {
		frm.add_custom_button(__("Calculate"), function() {
					frm.trigger("calculate_sheets");
				},null,"primary");
				
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

var get_dimensions = function(frm) {
	
	var length = frappe.mrp.convert_units(frm.doc.sheet_length_units,frm.doc.sheet_length);
	var width = frappe.mrp.convert_units(frm.doc.sheet_width_units,frm.doc.sheet_width);
	var height = frappe.mrp.convert_units(frm.doc.sheet_height_units,frm.doc.sheet_height);

	
	var perimeter = 2*flt(length)+2*flt(width);
	var farea = flt(length) * flt(width);
	var fvolume = flt(length) * flt(width) * flt(height);
	var fvolumecft = fvolume * 35.3147;
	
	var price_per_sqm = frm.doc.price_per_sheet / farea;

	
	
	var stock_summary = "Perimeter (m): " + perimeter.toFixed(4) + "<br>"
	+ "Area (m2): " + farea.toFixed(4) + "<br>"
	+ "Volume (m3): " + fvolume.toFixed(4) + "<br>"
	+ "Volume (cft): " + fvolumecft.toFixed(4) + "<br>"
	+ "Price Per sqm: " + price_per_sqm.toFixed(5) + "<br>";
	
	
	
	var depthPanel = frappe.mrp.convert_units(frm.doc.panel_length_units,frm.doc.panel_length);
	var widthPanel = frappe.mrp.convert_units(frm.doc.panel_width_units,frm.doc.panel_width);
	var heightPanel = frappe.mrp.convert_units(frm.doc.panel_height_units,frm.doc.panel_height);
	
	
	
	var cubic_m_conversion_factor = 1/flt(fvolume)
	var cft_conversion_factor = 1/flt(fvolumecft);
	
	var panelperimeter = 2*flt(depthPanel)+2*flt(widthPanel);
	var panelarea = flt(depthPanel) * flt(widthPanel);
	var panelvolume = flt(depthPanel) * flt(widthPanel) * flt(heightPanel);
	var panelvolumecft = panelvolume * 35.3147;
	
	
	var price_per_panel = panelarea*frm.doc.price_per_sheet / farea;
	
	
	var panel_summary = "Perimeter (m): " + panelperimeter.toFixed(4) + "<br>"
	+ "Area (m2): " + panelarea.toFixed(4) + "<br>"
	+ "Volume (m3): " + panelvolume.toFixed(4) + "<br>"
	+ "Volume (cft): " + panelvolumecft.toFixed(4) + "<br>"
	+ "Number of sheets = Panel Area / Sheet Area" + "<br>"
	+ "Price Per Panel: " + price_per_panel.toFixed(5) + "<br>";


	
	var conversion_factor = 1/flt(farea);


	var num_of_sheets = flt(panelarea) / flt(farea);
	var finished_qty_per_stock = 1/flt(num_of_sheets);
	
	var num_of_stock_vol = flt(panelvolume) / flt(fvolume);
	var finished_qty_per_stock_vol = 1/flt(num_of_stock_vol);
	
	
	
	frm.set_value("stock_summary", stock_summary);
	frm.set_value("panel_summary", panel_summary);

	
	frm.set_value("finished_qty_per_stock", finished_qty_per_stock);
	frm.set_value("num_of_sheets", num_of_sheets);
	frm.set_value("conversion_factor", conversion_factor);
	
	frm.set_value("finished_qty_per_stock_vol", finished_qty_per_stock_vol);
	frm.set_value("num_of_stock_vol", num_of_stock_vol);
	frm.set_value("cft_conversion_factor", cft_conversion_factor);
	frm.set_value("cubic_m_conversion_factor", cubic_m_conversion_factor);
	
	var radiusCircle = frappe.mrp.convert_units(frm.doc.circle_radius_units,frm.doc.circle_radius);
	var circlearea = flt(radiusCircle) * flt(radiusCircle) * 3.14;
	var circleperimeter = flt(radiusCircle) * 3.14 * 2;

	var price_per_top = panelarea*frm.doc.price_per_sheet / circlearea;
	
	var number_of_sheets_round_top = flt(circlearea) / flt(farea);
	var finished_qty_per_stock_round_top = 1/flt(number_of_sheets_round_top);
	var round_top_summary = "Radius (m): " + radiusCircle.toFixed(4) + "<br>"
	+ "Perimeter (m): " + circleperimeter.toFixed(4) + "<br>"
	+ "Area (m2): " + circlearea.toFixed(4) + "<br>"
	+ "Number of sheets = Circle Area / Sheet Area" + "<br>"
	+ "Price Per Round Top: " + price_per_top.toFixed(5) + "<br>";
	
	frm.set_value("number_of_sheets_round_top", number_of_sheets_round_top);
	frm.set_value("finished_qty_per_stock_round_top", finished_qty_per_stock_round_top);
	frm.set_value("round_top_summary", round_top_summary);


}