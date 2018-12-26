// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.bom");

frappe.ui.form.on("BOM", {
	setup: function(frm) {
		frm.add_fetch("item", "description", "description");
		frm.add_fetch("item", "image", "image");
		frm.add_fetch("item", "item_name", "item_name");
		frm.add_fetch("item", "stock_uom", "uom");

		// frm.set_query("bom_no", "items", function() {
			// return {
				// filters: {
					// 'currency': frm.doc.currency,
					// 'company': frm.doc.company
				// }
			// }
		// });
		

		frm.set_query("source_warehouse", "items", function() {
			return {
				filters: {
					'company': frm.doc.company
				}
			};
		});

		frm.set_query("item", function() {
			return {
				query: "erpnext.controllers.queries.item_query"
			};
		});

		frm.set_query("project", function() {
			return{
				filters:[
					['Project', 'status', 'not in', 'Completed, Cancelled']
				]
			};
		});

		frm.set_query("item_code", "items", function() {
			return {
				query: "erpnext.controllers.queries.item_query",
				filters: [["Item", "name", "!=", cur_frm.doc.item]]
			};
		});

		// frm.set_query("bom_no", "items", function(doc, cdt, cdn) {
			// var d = locals[cdt][cdn];
			// return {
				// filters: {
					// 'currency': cur_frm.doc.currency,
					// 'company': cur_frm.doc.company,
					// 'item': d.item_code,
					// 'is_active': 1,
					// 'docstatus': 1
				// }
			// };
		// });
	},

	onload_post_render: function(frm) {
		frm.get_field("items").grid.set_multiple_add("item_code", "qty");
	},

	refresh: function(frm) {
		frm.toggle_enable("item", frm.doc.__islocal);
		toggle_operations(frm);

		if (!frm.doc.__islocal && frm.doc.docstatus<2) {
			frm.add_custom_button(__("Update Cost"), function() {
				frm.events.update_cost(frm);
			});
			frm.add_custom_button(__("Browse BOM"), function() {
				frappe.route_options = {
					"bom": frm.doc.name
				};
				frappe.set_route("Tree", "BOM");
			});
			
			// frm.add_custom_button(__("Make"), function() {
				// frm.trigger("show_manufacture_dialog");
			// });

		}
		
		if (frm.doc.docstatus<1)
			frm.get_field("build_bom").$input.addClass("btn-primary");
			

		if(frm.doc.docstatus!=0) {
			frm.add_custom_button(__("Duplicate"), function() {
				frm.copy_doc();
			});
			
			
		}
	},
	
	show_manufacture_dialog: function(frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Make Stock Entry For Item Using Current BOM"),
			fields: [
				{fieldname:'item', fieldtype:'Link', options: 'Item',label: __('Item'),reqd:1},
				{fieldname:'qty', fieldtype:'Float', label: __('Quantity'),default:1,reqd:1},
				{fieldname:'delivery_note', fieldtype:'Link', options: 'Delivery Note', label: __('Delivery Note')},
				{fieldname:'project', fieldtype:'Link', options: 'Project', label: __('Project')},
				{fieldname:'add_operating_costs', fieldtype:'Check', label: __('Add Operating Costs'),default:0},
				// {fieldname:'submit', fieldtype:'Check', label: __('Submit'),default:0},
				{fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'remarks', fieldtype:'Small Text',label: __('Remarks')},
			]
		});
		dialog.set_primary_action(__("Make"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: frm.doc,
				args:{
					fg_item:filters.item,
					project: filters.project,
					qty:filters.qty,
					purpose:"Manufacture",
					add_operating_costs:filters.add_operating_costs,
					remarks:filters.remarks
				},
				method: "make_stock_entry",
				callback: function(r) {
					console.log(r);
					dialog.hide();
					frappe.set_route("Form", "Stock Entry", r.message);
					
				}
			});

		
		});
		dialog.show();
	},

	update_cost: function(frm) {
		return frappe.call({
			doc: frm.doc,
			method: "update_cost",
			freeze: true,
			args: {
				update_parent: true,
				from_child_bom:false
			},
			callback: function(r) {
				frm.refresh_fields();
			}
		})
	},
	
	item: function(frm) {
		if(frm.doc.item)
			frm.trigger("use_manufacturing_template");
	
	},
	
	use_manufacturing_template: function(frm) {
		if (frm.doc.docstatus > 0)
			return;
		frappe.call({
			doc: frm.doc,
			method: "get_main_item_dimensions",
			freeze: false,
			callback: function(r) {
					frm.refresh_fields("depth","width","height","depthunit","widthunit","heightunit");
				
					var bomitems = frm.doc.bomitems || [];
					

					for(var i=0;i<bomitems.length;i++) {
						var row = bomitems[i];
						calculate_builder_dimensions(row,false);
					}
					setTimeout(function(){
						cur_frm.trigger("build_bom");
						

					}, 1000);
					

			}
		})
	},
	
	refresh_part_dimensions: function(frm) {
		if (frm.doc.docstatus > 0)
			return;
		var bomitems = frm.doc.bomitems || [];
	
		for(var i=0;i<bomitems.length;i++) {
			var row = bomitems[i];
			calculate_builder_dimensions(row,false);
		}
		setTimeout(function(){
			cur_frm.trigger("build_bom");
			

		}, 1000);
	},
	
	get_template: function(frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Get Items From Collection"),
			fields: [
				{fieldname:'bundle', fieldtype:'Link', options: 'BOM Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				// {fieldname:'base_variable', fieldtype:'Section Break'},
			]
		});
		dialog.set_primary_action(__("Add"), function() {
		
		var filters = dialog.get_values();
/* 		if ('base' in filters) {
			delete filters.base
		} */
		frappe.call({
			method:'erpnext.manufacturing.doctype.bom.bom.get_product_bundle_items',
			args:{
				item_code: filters.bundle
			},
			freeze:false,
			callback:function (r) {
				
				for (var i=0; i< r.message.length; i++) {
					var row = frappe.model.add_child(cur_frm.doc, cur_frm.fields_dict.bomitems.df.options, cur_frm.fields_dict.bomitems.df.fieldname);
					row.bb_item = r.message[i].bb_item;
					row.bb_qty = r.message[i].bb_qty;
										
					row.side = r.message[i].side;
					row.edging = r.message[i].edging;
					row.edgebanding = r.message[i].edgebanding;
					row.laminate = r.message[i].laminate;
					row.laminate_sides = r.message[i].laminate_sides;
					row.requom = r.message[i].requom;
					calculate_builder_dimensions(row,false);

				}
				
				setTimeout(function(){
						cur_frm.refresh_field('bomitems');
						cur_frm.trigger("build_bom");
						//cur_frm.dirty();

					}, 1000);

				dialog.hide();
			}
		})
		});
		dialog.show();
	},

	
	build_bom: function(frm) {
		var doc = frm.doc;
		
		if (frm.doc.docstatus > 0) {
			return;
		}
		
		

		if(frm.doc.bomitems.length == 0)
		{
				cur_frm.dirty();
			return;

		}
					
		
		if (frm.doc.depth === 0 && frm.doc.width === 0 && frm.doc.height === 0){
			frappe.msgprint(__("Depth, width and height missing or equal to 0"));
									cur_frm.dirty();
			return;
		}
		
		frappe.call({
			
			doc: frm.doc,
			method: "build_bom",
			freeze:true,
			callback: function(r) {
				refresh_field("summary");
				refresh_field("items");
				refresh_field("exploded_items");
				erpnext.bom.update_cost(frm.doc);	
			}
		});
	
	},
	
	duty: function(frm) {

	
		erpnext.bom.calculate_total(frm.doc);	
	},
	
	is_default: function(frm) {

		if (frm.doc.is_default) cur_frm.set_value("is_active", 1);
	},
	
	with_operations: function(frm) {

		if(!cint(frm.doc.with_operations)) {
			frm.set_value("operations", []);
			erpnext.bom.calculate_op_cost(frm.doc);
			erpnext.bom.calculate_total(frm.doc);
		}
		else{
			var row = frappe.model.add_child(frm.doc,"operations");
			cur_frm.script_manager.trigger("operation", row.doctype, row.name);
		}
		toggle_operations(frm);
	},
	
	with_operations: function(frm) {

		if(!cint(frm.doc.with_operations)) {
			frm.set_value("operations", []);
			erpnext.bom.calculate_op_cost(frm.doc);
			erpnext.bom.calculate_total(frm.doc);
		}
		else{
			var row = frappe.model.add_child(frm.doc,"operations");
			cur_frm.script_manager.trigger("operation", row.doctype, row.name);
		}
		toggle_operations(frm);
	},

});

erpnext.bom.BomController = erpnext.TransactionController.extend({
	conversion_rate: function(doc) {
		if(this.frm.doc.currency === this.get_company_currency()) {
			this.frm.set_value("conversion_rate", 1.0);
		} else {
			erpnext.bom.update_cost(doc);
		}
	},

	item_code: function(doc, cdt, cdn){
		var scrap_items = false;
		var child = locals[cdt][cdn];
		if(child.doctype == 'BOM Scrap Item') {
			scrap_items = true;
		}

		if (child.bom_no) {
			child.bom_no = '';
		}

		get_bom_material_detail(doc, cdt, cdn, scrap_items);
	},
	conversion_factor: function(doc, cdt, cdn) {
		if(frappe.meta.get_docfield(cdt, "stock_qty", cdn)) {
			var item = frappe.get_doc(cdt, cdn);
			frappe.model.round_floats_in(item, ["qty", "conversion_factor"]);
			//item.stock_qty = flt(item.qty * item.conversion_factor, precision("stock_qty", item));
			item.stock_qty = flt(item.qty * item.conversion_factor);
			refresh_field("stock_qty", item.name, item.parentfield);
			this.toggle_conversion_factor(item);
			this.frm.events.update_cost(this.frm);
		}
	},
});

$.extend(cur_frm.cscript, new erpnext.bom.BomController({frm: cur_frm}));



/* cur_frm.cscript.hour_rate = function(doc, dt, dn) {
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_total(doc);
} */


/* cur_frm.cscript.time_in_mins = cur_frm.cscript.hour_rate;
 */
cur_frm.cscript.bom_no	= function(doc, cdt, cdn) {
	get_bom_material_detail(doc, cdt, cdn, false);
};



var get_bom_material_detail= function(doc, cdt, cdn, scrap_items) {
	var d = locals[cdt][cdn];
	if (d.item_code) {
		return frappe.call({
			doc: doc,
			method: "get_bom_material_detail",
			args: {
				'item_code': d.item_code,
				'bom_no': d.bom_no != null ? d.bom_no: '',
				'qty': d.qty,
				"scrap_items": scrap_items,
			},
			callback: function(r) {
				d = locals[cdt][cdn];
				$.extend(d, r.message);
				
				doc = locals[doc.doctype][doc.name];
				
				refresh_field("items");
				refresh_field("scrap_items");
				
				erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);	
				

			},
			freeze: false
		});
	}
}

cur_frm.cscript.required_uom = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];

	if(d.item_code && d.stock_uom && d.required_uom) {
		return frappe.call({
			method: "erpnext.stock.get_item_details.get_conversion_factor",
			child: d,
			args: {
				item_code: d.item_code,
				uom: d.required_uom
			},
			callback: function(r) {
				d.uom = d.required_uom;
				//console.log(r);
				d.conversion_factor = r.message.conversion_factor || 1.0
				refresh_field("conversion_factor", d.name, d.parentfield);
				refresh_field("uom", d.name, d.parentfield);

				erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);
			}
		});
	}
}

cur_frm.cscript.uom = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];

	if(d.item_code && d.stock_uom && d.uom) {
		return frappe.call({
			method: "erpnext.stock.get_item_details.get_conversion_factor",
			child: d,
			args: {
				item_code: d.item_code,
				uom: d.uom
			},
			callback: function(r) {
				console.log(r);
				d.required_uom = d.uom;
				d.conversion_factor = r.message.conversion_factor || 1.0
				refresh_field("conversion_factor", d.name, d.parentfield);
				refresh_field("required_uom", d.name, d.parentfield);

				erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);
			}
		});
	}
};



cur_frm.cscript.conversion_factor = function(doc, cdt, cdn) {
	erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);
}

erpnext.bom.calculate_conversion_factor = function(doc, cdt, cdn) {
	if(frappe.meta.get_docfield(cdt, "qty", cdn)) {
		var item = frappe.get_doc(cdt, cdn);
		frappe.model.round_floats_in(item, ["qty", "conversion_factor"]);
		//item.stock_qty = flt(item.qty * item.conversion_factor, precision("stock_qty", item));
		item.stock_qty = flt(item.qty * item.conversion_factor);
		refresh_field("stock_qty", item.name, item.parentfield);
		// this.toggle_conversion_factor(item);
		erpnext.bom.update_cost(doc);
	}
}


cur_frm.cscript.qty = function(doc, cdt, cdn) {
	erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);	
}

cur_frm.cscript.rate = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	var scrap_items = false;


	if(cdt == 'BOM Scrap Item') {
		scrap_items = true;
	}

	if (d.bom_no) {

		frappe.msgprint(__("You can not change rate if BOM mentioned against any item"));
		get_bom_material_detail(doc, cdt, cdn, scrap_items);
	} else {
			erpnext.bom.update_cost(doc);

	}
};

erpnext.bom.update_cost = function(doc) {
	erpnext.bom.calculate_rm_cost(doc);
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_scrap_materials_cost(doc);
	erpnext.bom.calculate_total(doc);
};

erpnext.bom.calculate_op_cost = function(doc) {
	var op = doc.operations || [];
	doc.operating_cost = 0.0;
	doc.base_operating_cost = 0.0;

	for(var i=0;i<op.length;i++) {
		op[i].time_in_mins = doc.raw_material_cost;	
		var operating_cost = flt(flt(op[i].hour_rate)/100 * flt(op[i].time_in_mins), 2);
		var base_operating_cost = flt(flt(op[i].base_hour_rate)/100 * flt(op[i].time_in_mins), 2);


		frappe.model.set_value('BOM Operation',op[i].name, "operating_cost", operating_cost);
		frappe.model.set_value('BOM Operation',op[i].name, "base_operating_cost", base_operating_cost);
		base_operating_cost = operating_cost * flt(doc.conversion_rate);
		doc.operating_cost += operating_cost;
		doc.base_operating_cost += base_operating_cost;
	}
	
	refresh_field(['operations','operating_cost', 'base_operating_cost']);

};

// rm : raw material
erpnext.bom.calculate_rm_cost = function(doc) {
	var rm = doc.items || [];

	var total_rm_cost = 0;
	var base_total_rm_cost = 0;

	for(var i=0;i<rm.length;i++) {
		var amount = flt(rm[i].rate) * flt(rm[i].stock_qty);
		var base_amount = amount * flt(doc.conversion_rate);
		frappe.model.set_value('BOM Item', rm[i].name, 'base_rate',flt(rm[i].rate) * flt(doc.conversion_rate));
		frappe.model.set_value('BOM Item', rm[i].name, 'amount', amount);
		frappe.model.set_value('BOM Item', rm[i].name, 'base_amount', base_amount);
		frappe.model.set_value('BOM Item', rm[i].name,'qty_consumed_per_unit', flt(rm[i].stock_qty)/flt(doc.quantity));


		total_rm_cost += amount;
		base_total_rm_cost += base_amount;
	}
	cur_frm.set_value("raw_material_cost", total_rm_cost);
	cur_frm.set_value("base_raw_material_cost", base_total_rm_cost);

};

// sm : scrap material
erpnext.bom.calculate_scrap_materials_cost = function(doc) {
	var sm = doc.scrap_items || [];
	var total_sm_cost = 0;
	var base_total_sm_cost = 0;

	for(var i=0;i<sm.length;i++) {
		var base_rate = flt(sm[i].rate) * flt(doc.conversion_rate);
		var amount = flt(sm[i].rate) * flt(sm[i].stock_qty);
		var base_amount = amount * flt(doc.conversion_rate);

		frappe.model.set_value('BOM Scrap Item',sm[i].name, 'base_rate', base_rate);
		frappe.model.set_value('BOM Scrap Item',sm[i].name, 'amount', amount);
		frappe.model.set_value('BOM Scrap Item',sm[i].name, 'base_amount', base_amount);

		total_sm_cost += amount;
		base_total_sm_cost += base_amount;
	}

	cur_frm.set_value("scrap_material_cost", total_sm_cost);
	cur_frm.set_value("base_scrap_material_cost", base_total_sm_cost);
};

// Calculate Total Cost
erpnext.bom.calculate_total = function(doc) {
	var total_cost = flt(doc.operating_cost) + flt(doc.raw_material_cost) - flt(doc.scrap_material_cost);
	var base_total_cost = flt(doc.base_operating_cost) + flt(doc.base_raw_material_cost)
		- flt(doc.base_scrap_material_cost);
	
	


	cur_frm.set_value("total_cost", total_cost);
	cur_frm.set_value("base_total_cost", base_total_cost);

	calculate_total_duty(doc);

}

frappe.ui.form.on('BOM Explosion Item', {
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
			dutible += flt(rm[i].amount);
			
		}
		else{
			non_dutible += flt(rm[i].amount);
		}
		
		
	}
	
	var customs_price = 0.0;
	var duty_percent = 0.0;
	if(dutible > 0.0)
	{
		duty_percent = doc.duty;
		customs_price = (flt(duty_percent)/100 * flt(dutible + non_dutible + doc.operating_cost)) + flt(doc.operating_cost) + flt(dutible);

	}
	else
	{
		duty_percent = doc.non_duty_percent;
		customs_price = flt(duty_percent)/100 * flt(dutible + non_dutible + doc.operating_cost);
	}
	
	var base_total_duty = flt(customs_price) * flt(doc.conversion_rate);

	cur_frm.set_value("total_duty", customs_price);
	cur_frm.set_value("base_total_duty", base_total_duty);

	cur_frm.set_value("dutible", dutible);
	cur_frm.set_value("non_dutible", non_dutible);

};




////////////////////// queries
cur_frm.fields_dict['item'].get_query = function(doc) {
 	return{
		query: "erpnext.controllers.queries.item_query",
		filters: [
			['Item', 'is_stock_item', '=', '1'],
			// ['Item', 'parent_item_group', 'not in', 'Raw Material,Hardware']
		]

	}
}

cur_frm.fields_dict['project'].get_query = function(doc, dt, dn) {
	return{
		filters:[
			['Project', 'status', 'not in', 'Completed, Cancelled']
		]
	}
}

cur_frm.fields_dict['items'].grid.get_field('item_code').get_query = function(doc) {
	return{
		query: "erpnext.controllers.queries.item_query",
		filters: [["Item", "name", "!=", cur_frm.doc.item]]
	}
}

cur_frm.fields_dict['items'].grid.get_field('bom_no').get_query = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	return{
		filters: {
			'currency': cur_frm.doc.currency,
			'company': cur_frm.doc.company,
			'item': d.item_code,
			'is_active': 1,
			'docstatus': 1
		}
	}
	
}



cur_frm.cscript.validate = function(doc) {
	erpnext.bom.update_cost(doc);
};

frappe.ui.form.on("BOM Operation", {
	
	operation:function(frm, cdt, cdn) {
		
		var d = locals[cdt][cdn];

	if(!d.operation) return;

	frappe.call({
		"method": "frappe.client.get",
		args: {
			doctype: "Operation",
			name: d.operation
		},
		callback: function (data) {
			if(data.message.description) {
				frappe.model.set_value(d.doctype, d.name, "description", data.message.description);
			}
			if(data.message.workstation) {
				frappe.model.set_value(d.doctype, d.name, "workstation", data.message.workstation);
			}
		}
	})
	},
	
	workstation:function(frm, cdt, cdn) {
		
		var d = locals[cdt][cdn];


	frappe.call({
		"method": "frappe.client.get",
		args: {
			doctype: "Workstation",
			name: d.workstation
		},
		freeze: false,
		callback: function (data) {

			frappe.model.set_value(d.doctype, d.name, "hour_rate", data.message.hour_rate);
			frappe.model.set_value(d.doctype, d.name, "base_hour_rate", flt(data.message.hour_rate) * flt(frm.doc.conversion_rate));
			frappe.model.set_value(d.doctype, d.name, "time_in_mins", frm.doc.raw_material_cost);
			

			erpnext.bom.calculate_op_cost(frm.doc);
			erpnext.bom.calculate_total(frm.doc);
			
			frappe.call({
					doc: frm.doc,
					method: "update_operation_summary",
					freeze: false,
					callback: function(r) {
						cur_frm.set_value("operation_summary",r.message);
					}
			})
	
			
			
			
		}
	})
	},
	
	operations_remove:function(frm, cdt, cdn) {
		erpnext.bom.calculate_op_cost(frm.doc);
		erpnext.bom.calculate_total(frm.doc);
	},


});


frappe.ui.form.on("BOM Item",{
	
	qty:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		d.stock_qty = d.qty * d.conversion_factor;
		refresh_field("items");
	},
	
	items_remove:function(frm, cdt, cdn) {
		erpnext.bom.update_cost(frm.doc);
	},
});
 

var toggle_operations = function(frm) {
	frm.toggle_display("operations_section", cint(frm.doc.with_operations) == 1);
	// frm.toggle_display("template_section", cint(frm.doc.use_manufacturing_template) == 1);
	// frm.toggle_display("bom_builder", cint(frm.doc.use_manufacturing_template) == 1);
	// frm.toggle_display("summary", cint(frm.doc.use_manufacturing_template) == 1);
}





cur_frm.cscript.image = function() {
	refresh_field("image_view");
};


//---------------------------------
cur_frm.fields_dict['bomitems'].grid.get_field('laminate').get_query = function(doc, cdt, cdn) {
	return {
		query: "erpnext.controllers.queries.item_query",
		filters: {
			'item_group': "Laminate"
		}
	}
}

cur_frm.fields_dict['bomitems'].grid.get_field('edging').get_query = function(doc, cdt, cdn) {
	return {
		query: "erpnext.controllers.queries.item_query",
		filters: {
			'item_group': "PVC Edging"
		}
	}
}

// cur_frm.fields_dict['glue'].get_query = function(doc, cdt, cdn) {
	// return {
		// query: "erpnext.controllers.queries.item_query",
		// filters: {
			// 'item_group': "Glue"
		// }
	// }
// }

cur_frm.fields_dict['bomitems'].grid.get_field('item_code').get_query = function(doc) {
	return{
		query: "erpnext.controllers.queries.item_query",
		filters: [["Item", "name", "!=", cur_frm.doc.item],["Item", "item_group", "!=", "Header1"]]
	}
}




//----------------------------------------



frappe.ui.form.on('BOM Builder Item', {
	
	bomitems_add:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		calculate_builder_dimensions(d,false);
	},
	
	bomitems_remove:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		cur_frm.trigger("build_bom");
	},
	
	bb_item: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	
	side:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		calculate_builder_dimensions(d,true);
	},
	
	bb_qty:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	
	requom:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		}
	},
	
	edging:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	
	edgebanding:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	laminate:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	laminate_sides:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},	
	
	length:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	
	width:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	height:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
	
	
});


var convert_units = function(unit,value) {
	var finalvalue = 0;
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


var calculate_builder_dimensions = function(d, build=false) {
	if(!d.side) return;
	
	var side = d.side;
	var length = 0;
	var width = 0;
	var height = 0;
	var required_uom = d.requom;
	
	var depthOriginal = convert_units(cur_frm.doc.depthunit,cur_frm.doc.depth);
	var widthOriginal = convert_units(cur_frm.doc.widthunit,cur_frm.doc.width);
	var heightOriginal = convert_units(cur_frm.doc.heightunit,cur_frm.doc.height);
	
	frappe.call({
		method:'erpnext.manufacturing.doctype.bom.bom.get_part_details',
		args:{
			part: side,
			item_code:d.bb_item,
		},
		callback:function (r) {
			var plane = r.message[0];
			required_uom = r.message[1];
			
			if(plane == "top"){
				length = depthOriginal;
				width = widthOriginal;
				height = heightOriginal;
			}
			else if(plane == "front"){
				length = heightOriginal;
				width = widthOriginal;
				height = depthOriginal;
			}
			else if(plane == "side"){
				length = depthOriginal;
				width = heightOriginal;
				height = widthOriginal;
			}
			else{
				length = d.length;
				width = d.width;
				height = d.height;
			}
			
			
			// d.length = length;
			// d.height = height;
			// d.width = width;
			// d.requom = required_uom;
			// cur_frm.refresh_field("bomitems");
			
			frappe.model.set_value(d.doctype, d.name, "length", length);
			frappe.model.set_value(d.doctype, d.name, "height", height);
			frappe.model.set_value(d.doctype, d.name, "width", width);
			frappe.model.set_value(d.doctype, d.name, "requom", required_uom);
			
			if(d.bb_item){
				if(build){
					cur_frm.trigger("build_bom");
				}
					
			
			}
				

		}
	})
	

}

