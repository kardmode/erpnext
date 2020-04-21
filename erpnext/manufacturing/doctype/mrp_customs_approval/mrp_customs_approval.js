// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Customs Approval', {
	onload: function(frm) {
		if (frm.doc.__islocal) {
				frm.set_value("posting_date", frappe.datetime.nowdate());

				//frm.set_value("posting_time", frappe.datetime.now_time());
				//frm.set_value("posting_date", frappe.datetime.get_today()+frappe.datetime.now_time());
		}
		else
		{
		
		}
	},
	
	// refresh: function(frm) {

	// },

	
});

frappe.ui.form.on("MRP CA Item",{
	bom:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];;

		if(d.item_code && d.bom) {
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "BOM",
					name: d.bom
				},
				callback: function (r) {
					frappe.model.set_value(d.doctype, d.name, "dutible", r.message.dutible);
					frappe.model.set_value(d.doctype, d.name, "non_dutible", r.message.non_dutible);
					frappe.model.set_value(d.doctype, d.name, "non_duty_percent", r.message.non_duty_percent);
					frappe.model.set_value(d.doctype, d.name, "mfg_cost", r.message.mrp_total_production_overhead);
					frappe.model.set_value(d.doctype, d.name, "ex_factory_price", r.message.mrp_factory_price);
					frappe.model.set_value(d.doctype, d.name, "customs_price", r.message.total_duty);
					
					var operating_costs = [];
					for(var i=0;i<r.message.mrp_operating_costs.length;i++)
					{
						operating_costs.push({
							'type':r.message.mrp_operating_costs[i]['type'],
							'percent':r.message.mrp_operating_costs[i]['percent'],
							'amount':r.message.mrp_operating_costs[i]['amount']
						})
					}
					
					frappe.model.set_value(d.doctype, d.name, "data", JSON.stringify(operating_costs) );

				}
			})
			
			
			
			/* return frappe.call({
				
				method:'erpnext.manufacturing.doctype.mrp_production_order.mrp_production_order.get_item_det',
				args: {
					item_code: d.item_code
				},
				callback: function(r) {
					// frappe.model.set_value(d.doctype, d.name, "uom", r.message.stock_uom);
					// frappe.model.set_value(d.doctype, d.name, "height", r.message.height);
					// frappe.model.set_value(d.doctype, d.name, "heightunit", r.message.heightunit);
					// frappe.model.set_value(d.doctype, d.name, "width", r.message.width);
					// frappe.model.set_value(d.doctype, d.name, "widthunit", r.message.widthunit);
					// frappe.model.set_value(d.doctype, d.name, "depth", r.message.depth);
					// frappe.model.set_value(d.doctype, d.name, "depthunit", r.message.depthunit);
					// frappe.model.set_value(d.doctype, d.name, "bom", r.message.default_bom);
				}
			}); */
		}
		
		
		
	},
	item_code:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.item_code) {
			return frappe.call({
				
				method:'erpnext.manufacturing.doctype.mrp_production_order.mrp_production_order.get_item_det',
				args: {
					item_code: d.item_code
				},
				callback: function(r) {
					// frappe.model.set_value(d.doctype, d.name, "uom", r.message.stock_uom);
					// frappe.model.set_value(d.doctype, d.name, "height", r.message.height);
					// frappe.model.set_value(d.doctype, d.name, "heightunit", r.message.heightunit);
					// frappe.model.set_value(d.doctype, d.name, "width", r.message.width);
					// frappe.model.set_value(d.doctype, d.name, "widthunit", r.message.widthunit);
					// frappe.model.set_value(d.doctype, d.name, "depth", r.message.depth);
					// frappe.model.set_value(d.doctype, d.name, "depthunit", r.message.depthunit);
					frappe.model.set_value(d.doctype, d.name, "bom", r.message.default_bom);
				}
			});
		}
		
	},
});

cur_frm.fields_dict['items'].grid.get_field('bom').get_query = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.item_code) {
		return{
			filters:[
				['BOM', 'docstatus', '<', 2],['BOM', 'is_active', '=', 1],
			]
		}
	} 
}
