// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.bom");

frappe.ui.form.on("BOM", {
	setup: function(frm) {
		frm.add_fetch('buying_price_list', 'currency', 'currency')
		frm.fields_dict["items"].grid.get_field("bom_no").get_query = function(doc, cdt, cdn){
			return {
				filters: {'currency': frm.doc.currency}
			}
		}
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

		}
		
		
		if(frm.doc.docstatus==2) {
			// show duplicate button when BOM is cancelled,
			// its not very intuitive
			frm.add_custom_button(__("Duplicate"), function() {
				frm.copy_doc();
			});
		}
	},

	update_cost: function(frm) {
		return frappe.call({
			doc: frm.doc,
			method: "update_cost",
			freeze: true,
			callback: function(r) {
				if(!r.exc) frm.refresh_fields();
			}
		})
	},
	
	
	
	build_bom: function(frm) {
		
		if (frm.doc.docstatus > 0) {
			return;
		}
		
		var doc = frm.doc;
		if (!(frm.doc.depth && frm.doc.width && frm.doc.height&& frm.doc.depthunit && frm.doc.heightunit&& frm.doc.widthunit)){
			msgprint(__("Depth, width or height missing"));
			return;
		}
		
		frappe.call({
			
		doc: frm.doc,
		method: "build_bom",
		// method: 'erpnext.manufacturing.doctype.bom.bom.build_bom',
		// args: {
			// items: doc.bomitems,
			// depthOriginal:doc.depth,
			// widthOriginal:doc.width,
			// heightOriginal:doc.height,
			// depthunit:doc.depthunit,
			// widthunit:doc.widthunit,
			// heightunit:doc.heightunit,
			// qty:1,
		// },
		callback: function(r) {
			if(r.message[1])
				summary = r.message[1];
			else
				summary = "";
			
			frm.set_value("summary",summary);
			
			frappe.call({
					doc: frm.doc,
					method: "update_bom_builder",
					freeze: false,
					args: {
						merged: r.message[0],
					},
					callback: function(r) {
						refresh_field("items");
						erpnext.bom.update_cost(frm.doc);	
					}
				}); 
			
			
		}
		});
	
	},
});

erpnext.bom.BomController = erpnext.TransactionController.extend({
	conversion_rate: function(doc, cdt, cdn) {
		if(this.frm.doc.currency === this.get_company_currency()) {
			this.frm.set_value("conversion_rate", 1.0);
		} else {
			erpnext.bom.update_cost(doc);
		}
	},
	
	item_code: function(doc, cdt, cdn){
		var scrap_items = false;
		child = locals[cdt][cdn];
		if(child.doctype == 'BOM Scrap Item') {
			scrap_items = true;
		}

		get_bom_material_detail(doc, cdt, cdn, scrap_items);
	},
})

$.extend(cur_frm.cscript, new erpnext.bom.BomController({frm: cur_frm}));

cur_frm.add_fetch("item", "description", "description");
cur_frm.add_fetch("item", "image", "image");
cur_frm.add_fetch("item", "item_name", "item_name");
cur_frm.add_fetch("item", "stock_uom", "uom");

cur_frm.add_fetch("item", "depth", "depth");
cur_frm.add_fetch("item", "width", "width");
cur_frm.add_fetch("item", "height", "height");
cur_frm.add_fetch("item", "depthunit", "depthunit");
cur_frm.add_fetch("item", "widthunit", "widthunit");
cur_frm.add_fetch("item", "heightunit", "heightunit");


/* cur_frm.cscript.hour_rate = function(doc, dt, dn) {
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_total(doc);
} */

/* cur_frm.cscript.time_in_mins = cur_frm.cscript.hour_rate;
 */
cur_frm.cscript.bom_no	= function(doc, cdt, cdn) {
	get_bom_material_detail(doc, cdt, cdn, false);
}

cur_frm.cscript.is_default = function(doc) {
	if (doc.is_default) cur_frm.set_value("is_active", 1);
}

var get_bom_material_detail= function(doc, cdt, cdn, scrap_items) {
	var d = locals[cdt][cdn];
	if (d.item_code) {
		return frappe.call({
			doc: doc,
			method: "get_bom_material_detail",
			args: {
				'item_code': d.item_code,
				'bom_no': d.bom_no != null ? d.bom_no: '',
				'qty': d.required_qty,
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

	if(d.item_code && d.stock_uom) {
		return frappe.call({
			method: "erpnext.stock.get_item_details.get_conversion_factor",
			child: d,
			args: {
				item_code: d.item_code,
				uom: d.required_uom
			},
			callback: function(r) {
				
				d.conversion_factor = r.message.conversion_factor
				refresh_field("conversion_factor", d.name, d.parentfield);
				if (!r.exc)
					erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);
			}
		});
	}
}


cur_frm.cscript.conversion_factor = function(doc, cdt, cdn) {
	erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);
}

erpnext.bom.calculate_conversion_factor = function(doc, cdt, cdn) {
	if(frappe.meta.get_docfield(cdt, "qty", cdn)) {
		var item = frappe.get_doc(cdt, cdn);
		frappe.model.round_floats_in(item, ["required_qty", "conversion_factor"]);
		item.qty = flt(item.required_qty * item.conversion_factor, precision("qty", item));
		item.required_rate = flt(item.rate * item.conversion_factor, precision("rate", item));
		
		refresh_field("required_rate", item.name, item.parentfield);
		refresh_field("qty", item.name, item.parentfield);
	
		erpnext.bom.update_cost(doc);
	}
}


cur_frm.cscript.required_qty = function(doc, cdt, cdn) {
	erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);	
}


cur_frm.cscript.rate = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	var scrap_items = false;

	if(d.doctype == 'BOM Scrap Item') {
		scrap_items = true;
	}

	if (d.bom_no) {
		msgprint(__("You can not change rate if BOM mentioned against any item"));
		get_bom_material_detail(doc, cdt, cdn, scrap_items);
	} else {
		erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);
	}
}

erpnext.bom.update_cost = function(doc) {
	erpnext.bom.calculate_rm_cost(doc);
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_scrap_materials_cost(doc);
	erpnext.bom.calculate_total(doc);
}

erpnext.bom.calculate_op_cost = function(doc) {
	var op = doc.operations || [];
	doc.operating_cost = 0.0;
	doc.base_operating_cost = 0.0;

	for(var i=0;i<op.length;i++) {
		op[i].time_in_mins = doc.raw_material_cost;	
		operating_cost = flt(flt(op[i].hour_rate)/100 * flt(op[i].time_in_mins), 2);
		base_operating_cost = flt(flt(op[i].base_hour_rate)/100 * flt(op[i].time_in_mins), 2);
		frappe.model.set_value('BOM Operation',op[i].name, "operating_cost", operating_cost);
		frappe.model.set_value('BOM Operation',op[i].name, "base_operating_cost", base_operating_cost);

		doc.operating_cost += operating_cost;
		doc.base_operating_cost += base_operating_cost;
	}
	
	refresh_field(['operations','operating_cost', 'base_operating_cost']);
	
	
	
}

// rm : raw material
erpnext.bom.calculate_rm_cost = function(doc) {
	var rm = doc.items || [];

	total_rm_cost = 0;
	base_total_rm_cost = 0;
	for(var i=0;i<rm.length;i++) {
		amount = flt(rm[i].rate) * flt(rm[i].qty);
		base_amount = flt(rm[i].rate) * flt(doc.conversion_rate) * flt(rm[i].qty);
		frappe.model.set_value('BOM Item', rm[i].name, 'base_rate', flt(rm[i].rate) * flt(doc.conversion_rate))
		frappe.model.set_value('BOM Item', rm[i].name, 'amount', amount)
		frappe.model.set_value('BOM Item', rm[i].name, 'qty_consumed_per_unit', flt(rm[i].qty)/flt(doc.quantity))
		frappe.model.set_value('BOM Item', rm[i].name, 'base_amount', base_amount)
		total_rm_cost += amount;
		base_total_rm_cost += base_amount;
	}
	cur_frm.set_value("raw_material_cost", total_rm_cost);
	cur_frm.set_value("base_raw_material_cost", base_total_rm_cost);
	
}

//sm : scrap material
erpnext.bom.calculate_scrap_materials_cost = function(doc) {
	var sm = doc.scrap_items || [];
	total_sm_cost = 0;
	base_total_sm_cost = 0;

	for(var i=0;i<sm.length;i++) {
		base_rate = flt(sm[i].rate) * flt(doc.conversion_rate);
		amount =	flt(sm[i].rate) * flt(sm[i].qty);
		base_amount =	flt(sm[i].rate) * flt(sm[i].qty) * flt(doc.conversion_rate);
		frappe.model.set_value('BOM Scrap Item',sm[i].name, 'base_rate', base_rate);
		frappe.model.set_value('BOM Scrap Item',sm[i].name, 'amount', amount);
		frappe.model.set_value('BOM Scrap Item',sm[i].name, 'base_amount', base_amount);
		
		total_sm_cost += amount;
		base_total_sm_cost += base_amount;
	}
	
	cur_frm.set_value("scrap_material_cost", total_sm_cost);
	cur_frm.set_value("base_scrap_material_cost", base_total_sm_cost);
}

// Calculate Total Cost
erpnext.bom.calculate_total = function(doc) {
	total_cost = flt(doc.operating_cost) + flt(doc.raw_material_cost) - flt(doc.scrap_material_cost);
	base_total_cost = flt(doc.base_operating_cost) + flt(doc.base_raw_material_cost) - flt(doc.base_scrap_material_cost);
	cur_frm.set_value("total_cost", total_cost);
	cur_frm.set_value("base_total_cost", base_total_cost);
	
		erpnext.bom.calculate_grand_total(doc);

}

cur_frm.cscript.duty = function(doc, cdt, cdn) {
	erpnext.bom.calculate_grand_total(doc);	
}

erpnext.bom.calculate_grand_total = function(doc) {
	
	var total_cost = flt(doc.operating_cost)+flt(doc.raw_material_cost)- flt(doc.base_scrap_material_cost);
	var total_duty = (flt(doc.duty/100)*flt(total_cost));

	cur_frm.set_value("total_cost", total_cost);
	cur_frm.set_value("total_duty", total_duty);

}

//////////////////////// queries
cur_frm.fields_dict['item'].get_query = function(doc) {
 	return{
		query: "erpnext.controllers.queries.item_query",
		filters: [
			['Item', 'item_group', 'in', 'Furniture,Finished Furniture,Products,Sub Assemblies']
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
		filters:{
			'item': d.item_code,
			'is_active': 1,
			'docstatus': 1
		}
	}
}

cur_frm.cscript.validate = function(doc, dt, dn) {
	erpnext.bom.update_cost(doc)
}

frappe.ui.form.on("BOM Operation", "operation", function(frm, cdt, cdn) {
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
});

frappe.ui.form.on("BOM Operation", "workstation", function(frm, cdt, cdn) {
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
						console.log(r);
						cur_frm.set_value("operation_summary",r.message);
					}
			})
	
			
			
			
		}
	})
});

frappe.ui.form.on("BOM Operation", "operations_remove", function(frm) {
	erpnext.bom.calculate_op_cost(frm.doc);
	erpnext.bom.calculate_total(frm.doc);
});

frappe.ui.form.on("BOM Item", "items_remove", function(frm) {
			erpnext.bom.update_cost(frm.doc);

});

var toggle_operations = function(frm) {
	frm.toggle_display("operations_section", cint(frm.doc.with_operations) == 1);
	// frm.toggle_display("template_section", cint(frm.doc.use_manufacturing_template) == 1);
	// frm.toggle_display("bom_builder", cint(frm.doc.use_manufacturing_template) == 1);
	// frm.toggle_display("summary", cint(frm.doc.use_manufacturing_template) == 1);
}



frappe.ui.form.on("BOM", "with_operations", function(frm) {
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
});

cur_frm.cscript.image = function() {
	refresh_field("image_view");
}


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

frappe.ui.form.on("BOM", "use_manufacturing_template", function(frm) {
	if (frm.doc.docstatus > 0)
		return;
	frappe.call({
		doc: frm.doc,
		method: "get_main_item_dimensions",
		freeze: false,
		callback: function(r) {
			if(!r.exc)frm.refresh_fields("depth","width","height","depthunit","widthunit","heightunit");
			
			cur_frm.dirty();
		}
	})
});

frappe.ui.form.on("BOM", "get_template", function(frm) {
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
			callback:function (r) {
				
				for (var i=0; i< r.message.length; i++) {
					var row = frappe.model.add_child(cur_frm.doc, cur_frm.fields_dict.bomitems.df.options, cur_frm.fields_dict.bomitems.df.fieldname);
					row.bb_item = r.message[i].bb_item;
					row.bb_qty = r.message[i].bb_qty;
					
					console.log(r.message[i]);
					
					row.side = r.message[i].side;
					row.edging = r.message[i].edging;
					row.edgebanding = r.message[i].edgebanding;
					row.laminate = r.message[i].laminate;
					row.laminate_sides = r.message[i].laminate_sides;
					row.requom = r.message[i].requom;
					get_dimensions_from_collection(row);

				}
				cur_frm.refresh_field('bomitems');

				dialog.hide();
			}
		})
		});
		dialog.show();
	
});


//----------------------------------------

frappe.ui.form.on("BOM Builder Item", "bomitems_add", function(frm, cdt, cdn) {
	var d = locals[cdt][cdn];
	get_dimensions(d);
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

var get_dimensions_from_collection = function(d) {
	if(!d.side) return;
	
	var side = d.side;
	var length = 0;
	var width = 0;
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
			if(r.message[0] == "top"){
				length = depthOriginal;
				width = widthOriginal;
			}
			else if(r.message[0] == "front"){
				length = heightOriginal;
				width = widthOriginal;
			}
			else if(r.message[0] == "side"){
				length = heightOriginal;
				width = depthOriginal;
			}
			else{
				length = depthOriginal;
				width = widthOriginal;
			}
			
			frappe.model.set_value(d.doctype, d.name, "length", length);
			frappe.model.set_value(d.doctype, d.name, "width", width);
			frappe.model.set_value(d.doctype, d.name, "requom", required_uom);
		}
	})

}

var get_dimensions = function(d) {
	if(!d.side) return;
	
	var side = d.side;
	var length = 0;
	var width = 0;
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
			if(r.message[0] == "top"){
				length = depthOriginal;
				width = widthOriginal;
			}
			else if(r.message[0] == "front"){
				length = heightOriginal;
				width = widthOriginal;
			}
			else if(r.message[0] == "side"){
				length = heightOriginal;
				width = depthOriginal;
			}
			else{
				length = depthOriginal;
				width = widthOriginal;
			}
			
			
			
			frappe.model.set_value(d.doctype, d.name, "length", length);
			frappe.model.set_value(d.doctype, d.name, "width", width);
			frappe.model.set_value(d.doctype, d.name, "requom", r.message[1]);
		}
	})
	

}
