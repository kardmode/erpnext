// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.bom");



frappe.ui.form.on("BOM", {
	onload_post_render: function(frm) {
		frm.get_field("items").grid.set_multiple_add("item_code", "qty");
		
		
	},
	refresh: function(frm) {
		frm.toggle_enable("item", frm.doc.__islocal);
		toggle_operations(frm);

		frm.get_docfield("items").allow_bulk_edit = 1;
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
		
		if (frm.doc.docstatus == 2) {
			return;
		}
		
		if(!frm.doc.use_manufacturing_template){
			
			msgprint(__("Check Use Manufacturing Template to use bom builder"));
			return;
		}
		
	
			
		
		var doc = frm.doc;
		if (!(frm.doc.depth && frm.doc.width && frm.doc.height&& frm.doc.depthunit && frm.doc.heightunit&& frm.doc.widthunit)){
			msgprint(__("Depth, width or height missing"));
			return;

			
		}
		
		
		frappe.call({
		method: 'erpnext.manufacturing.doctype.bom.bom.build_bom',
		args: {
			items: doc.bomitems,
			depthOriginal:doc.depth,
			widthOriginal:doc.width,
			heightOriginal:doc.height,
			depthunit:doc.depthunit,
			widthunit:doc.widthunit,
			heightunit:doc.heightunit,
			qty:1,
		},
		callback: function(r) {
			if(r.message[1])
				doc.summary = r.message[1];
			else
				doc.summary = "";
			frm.refresh_fields();
			return frappe.call({
					doc: frm.doc,
					method: "update_bom_builder",
					freeze: true,
					args: {
						merged: r.message[0],
					},
					callback: function(r) {

						erpnext.bom.calculate_rm_cost(doc);
						erpnext.bom.calculate_scrap_materials_cost(doc);
						erpnext.bom.calculate_op_cost(doc);
						erpnext.bom.calculate_total(doc);
						frm.refresh_fields();
					}
				})
			
			
		}
		});
		
			
		
			
		
		

		
	}
});

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

cur_frm.cscript.hour_rate = function(doc, dt, dn) {
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_total(doc);
}

cur_frm.cscript.time_in_mins = cur_frm.cscript.hour_rate;


frappe.ui.form.on("BOM Item", "item_code", function(frm, cdt, cdn) {
	get_bom_material_detail(frm.doc, cdt, cdn);

});

cur_frm.cscript.bom_no	= function(doc, cdt, cdn) {
	get_bom_material_detail(doc, cdt, cdn);
}

cur_frm.cscript.is_default = function(doc) {
	if (doc.is_default) cur_frm.set_value("is_active", 1);
}




var get_bom_material_detail= function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.item_code) {
		return frappe.call({
			doc: doc,
			method: "get_bom_material_detail",
			args: {
				'item_code': d.item_code,
				'bom_no': d.bom_no != null ? d.bom_no: '',
				'qty': d.required_qty
			},
			callback: function(r) {
				d = locals[cdt][cdn];
				$.extend(d, r.message);
				
				doc = locals[doc.doctype][doc.name];
				erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);	
				refresh_field("items");
				refresh_field("scrap_items");
			},
			freeze: true
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
	
		erpnext.bom.calculate_rm_cost(doc);
		erpnext.bom.calculate_scrap_materials_cost(doc);
		erpnext.bom.calculate_op_cost(doc);
		erpnext.bom.calculate_total(doc);
	}
}

cur_frm.cscript.required_qty = function(doc, cdt, cdn) {
	erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);	
}

cur_frm.cscript.rate = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.bom_no) {
		msgprint(__("You can not change rate if BOM mentioned against any item"));
		get_bom_material_detail(doc, cdt, cdn);
	} else {
		erpnext.bom.calculate_conversion_factor(doc, cdt, cdn);

	}
}

erpnext.bom.calculate_op_cost = function(doc) {
	var op = doc.operations || [];
	doc.operating_cost = 0.0;
	for(var i=0;i<op.length;i++) {
		operating_cost = flt(flt(op[i].hour_rate)/100 * flt(op[i].time_in_mins), 2);
		frappe.model.set_value('BOM Operation',op[i].name, "operating_cost", operating_cost);
		doc.operating_cost += operating_cost;
	}
	
	refresh_field('operating_cost');
	
	return frappe.call({
			doc: doc,
			method: "update_operation_summary",
			freeze: true,
			callback: function(r) {
				refresh_field('operations');
				refresh_field('operation_summary');
			}
		})
}

// rm : raw material
erpnext.bom.calculate_rm_cost = function(doc) {
	var rm = doc.items || [];
	total_rm_cost = 0;
	for(var i=0;i<rm.length;i++) {
		amt =	flt(rm[i].rate) * flt(rm[i].qty);
		set_multiple('BOM Item',rm[i].name, {'amount': amt}, 'items');
		set_multiple('BOM Item',rm[i].name,
			{'qty_consumed_per_unit': flt(rm[i].qty)/flt(doc.quantity)}, 'items');
		total_rm_cost += amt;
	}
	cur_frm.set_value("raw_material_cost", total_rm_cost);
	
	if(cint(doc.with_operations)) {
		$.each(doc.operations, function(i, d) {
			frappe.model.set_value(d.doctype, d.name, "time_in_mins", total_rm_cost);

		});
	}
}

//sm : scrap material
erpnext.bom.calculate_scrap_materials_cost = function(doc) {
	var sm = doc.scrap_items || [];
	total_sm_cost = 0;
	for(var i=0;i<sm.length;i++) {
		amt =	flt(sm[i].rate) * flt(sm[i].qty);
		set_multiple('BOM Scrap Item',sm[i].name, {'amount': amt}, 'scrap_items');
	}
}

// Calculate Total Cost
erpnext.bom.calculate_total = function(doc) {
	
	total_cost = flt(doc.operating_cost) + flt(doc.raw_material_cost);
		
	frappe.model.set_value(doc.doctype, doc.name, "total_cost", total_cost);
	erpnext.bom.calculate_grand_total(doc);

}

cur_frm.cscript.duty = function(doc, cdt, cdn) {
	erpnext.bom.calculate_grand_total(doc);	
}

erpnext.bom.calculate_grand_total = function(doc) {
	
	if(!doc.duty){
		grand_total = flt(doc.operating_cost) + flt(doc.raw_material_cost);

	}
	else {
		grand_total = flt(doc.operating_cost)*(1+flt(doc.duty)/100) + flt(doc.raw_material_cost);
	}
	frappe.model.set_value(doc.doctype, doc.name, "grand_total", grand_total);
}


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
	erpnext.bom.calculate_rm_cost(doc);
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_scrap_materials_cost(doc);
	erpnext.bom.calculate_total(doc);
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
		callback: function (data) {
			frappe.model.set_value(d.doctype, d.name, "hour_rate", data.message.hour_rate);
			frappe.model.set_value(d.doctype, d.name, "time_in_mins", frm.doc.raw_material_cost);

			erpnext.bom.calculate_op_cost(frm.doc);
			erpnext.bom.calculate_total(frm.doc);
		}
	})
});

frappe.ui.form.on("BOM Operation", "operations_remove", function(frm) {
	erpnext.bom.calculate_op_cost(frm.doc);
	erpnext.bom.calculate_total(frm.doc);
});

frappe.ui.form.on("BOM Item", "items_remove", function(frm) {
	erpnext.bom.calculate_rm_cost(frm.doc);
	erpnext.bom.calculate_scrap_materials_cost(frm.doc);
	erpnext.bom.calculate_op_cost(frm.doc);
	erpnext.bom.calculate_total(frm.doc);
});

var toggle_operations = function(frm) {
	frm.toggle_display("operations_section", cint(frm.doc.with_operations) == 1);
	frm.toggle_display("bom_builder", cint(frm.doc.use_manufacturing_template) == 1);

	frm.toggle_display("template_section", cint(frm.doc.use_manufacturing_template) == 1);
	frm.toggle_display("summary", cint(frm.doc.use_manufacturing_template) == 1);

	//frm.grid.grid_buttons.find('.btn-custom').addClass('hidden');
}

frappe.ui.form.on("BOM", "with_operations", function(frm) {
	if(!cint(frm.doc.with_operations)) {
		frm.set_value("operations", []);
		erpnext.bom.calculate_op_cost(frm.doc);
		erpnext.bom.calculate_total(frm.doc);
	}
	else{
		var row = frappe.model.add_child(frm.doc,"operations");
		row.operation = "General";
		cur_frm.script_manager.trigger("operation", row.doctype, row.name);
		
		refresh_field(frm.doc.operations);
	}
	toggle_operations(frm);
});

frappe.ui.form.on("BOM", "use_manufacturing_template", function(frm) {
	if(!cint(frm.doc.use_manufacturing_template)) {
		frm.set_value("bomitems", []);
		frm.set_value("summary", "");
	}
	else{
		frappe.call({
			doc: frm.doc,
			method: "validate_main_item",
			freeze: true,
			callback: function(r) {
				if(!r.exc) frm.refresh_fields("depth","width","height","depthunit","widthunit","heightunit");
			}
		})
		
	}
	
	
	

	toggle_operations(frm);
});
//----------------------------------------



//----------------------------------
cur_frm.cscript.image = function() {
	refresh_field("image_view");
}

//------------
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

