// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customs Price Calculator', {
	setup: function(frm) {
		
		frm.set_query("bom", function() {
			return{
				filters: [["docstatus", "<", 2]]
			};
		});
		

	
	},

	refresh: function(frm) {
		//cur_frm.set_df_property("exploded_items", "read_only", 0);
		//cur_frm.add_fetch("bom", "exploded_items", "exploded_items");
		// frm.disable_save();
	
	
	},
	bom:function(frm){
		if (frm.doc.bom)
		{
			
			return frappe.call({
				doc: frm.doc,
				method: "get_child_exploded_items",
				freeze: true,
				args: {
					bom_no: frm.doc.bom,
					stock_qty:1
				},
				callback: function(r) {
					cur_frm.refresh_field('exploded_items');
					cur_frm.refresh_field('operating_cost');
					calculate_total_duty(frm.doc);

				}
			})
			
		}
		else{
			
		}
		
	},
});

frappe.ui.form.on('BOM Explosion Item', {
	exploded_items_add:function(frm, cdt, cdn){
		calculate_total_duty(frm.doc);
	},
	exploded_items_remove:function(frm, cdt, cdn){
		calculate_total_duty(frm.doc);
	},
	dutible:function(frm, cdt, cdn) {
		calculate_total_duty(frm.doc);
	},
});


var calculate_total_duty = function(doc) {
	var rm = doc.exploded_items || [];

	var dutible = 0;
	var non_dutible = 0;

	for(var i=0;i<rm.length;i++) {
		
		if(rm[i].dutible == 1)
		{
			dutible += rm[i].amount;
			
		}
		else{
			non_dutible += rm[i].amount;
		}
		
		
	}
	
	var customs_price = 0;
	var duty_percent = 0 
	if(dutible > 0)
	{
		duty_percent = doc.duty_percent;
		customs_price = ((duty_percent/100) * (dutible + non_dutible + doc.operating_cost)) + doc.operating_cost + dutible;

	}
	else
	{
		duty_percent = doc.non_duty_percent;
		customs_price = (duty_percent/100) * (dutible + non_dutible + doc.operating_cost);
	}
	
	cur_frm.set_value("customs_price", customs_price);
	cur_frm.set_value("dutible", dutible);
	cur_frm.set_value("non_dutible", non_dutible);

};
