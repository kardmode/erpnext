// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.item");

frappe.ui.form.on("Item", {
	setup: function(frm) {
		frm.add_fetch('attribute', 'numeric_values', 'numeric_values');
		frm.add_fetch('attribute', 'from_range', 'from_range');
		frm.add_fetch('attribute', 'to_range', 'to_range');
		frm.add_fetch('attribute', 'increment', 'increment');
		frm.add_fetch('tax_type', 'tax_rate', 'tax_rate');
	},
	onload: function(frm) {
		erpnext.item.setup_queries(frm);
		if (frm.doc.variant_of){
			frm.fields_dict["attributes"].grid.set_column_disp("attribute_value", true);
		}
		// should never check Private
		frm.fields_dict["website_image"].df.is_private = 0;
		
	},

	refresh: function(frm) {
		
		if (!frm.doc.__islocal){
			if(!frm.doc.parent_item_group && frm.doc.item_group)
			{		
				frappe.db.get_value('Item Group', {name: frm.doc.item_group}, 'parent_item_group', (r) => {
					parent_item_group = r && r.parent_item_group;
					frm.set_value("parent_item_group",parent_item_group);
				});
				
			}
			
		}
		
		


		if(frm.doc.is_stock_item) {
			frm.add_custom_button(__("Balance"), function() {
				frappe.route_options = {
					"item_code": frm.doc.name
				}
				frappe.set_route("query-report", "Stock Balance");
			}, __("View"));
			frm.add_custom_button(__("Ledger"), function() {
				frappe.route_options = {
					"item_code": frm.doc.name
				}
				frappe.set_route("query-report", "Stock Ledger");
			}, __("View"));
			frm.add_custom_button(__("Projected"), function() {
				frappe.route_options = {
					"item_code": frm.doc.name
				}
				frappe.set_route("query-report", "Stock Projected Qty");
			}, __("View"));
		}

		if(!frm.doc.is_fixed_asset) {
			erpnext.item.make_dashboard(frm);
		}

		// clear intro
		frm.set_intro();

		if (frm.doc.has_variants) {
			frm.set_intro(__("This Item is a Template and cannot be used in transactions. Item attributes will be copied over into the variants unless 'No Copy' is set"), true);
			frm.add_custom_button(__("Show Variants"), function() {
				frappe.set_route("List", "Item", {"variant_of": frm.doc.name});
			}, __("View"));

			frm.add_custom_button(__("Variant"), function() {
				erpnext.item.make_variant(frm);
			}, __("Make"));
			frm.page.set_inner_btn_group_as_primary(__("Make"));
		}
		if (frm.doc.variant_of) {
			frm.set_intro(__('This Item is a Variant of {0} (Template).',
				[`<a href="#Form/Item/${frm.doc.variant_of}">${frm.doc.variant_of}</a>`]), true);
		}

		if (frappe.defaults.get_default("item_naming_by")!="Naming Series" || frm.doc.variant_of) {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		erpnext.item.edit_prices_button(frm);

		// make sensitive fields(has_serial_no, is_stock_item, valuation_method, has_batch_no)
		// read only if any stock ledger entry exists
		if (!frm.doc.__islocal && frm.doc.is_stock_item) {
			frm.toggle_enable(['has_serial_no', 'is_stock_item', 'valuation_method', 'has_batch_no'],
				(frm.doc.__onload && frm.doc.__onload.sle_exists=="exists") ? false : true);
		}

		erpnext.item.toggle_attributes(frm);

		frm.toggle_enable("is_fixed_asset", (frm.doc.__islocal || (!frm.doc.is_stock_item &&
			((frm.doc.__onload && frm.doc.__onload.asset_exists) ? false : true))));

		frm.add_custom_button(__('Duplicate'), function() {
			var new_item = frappe.model.copy_doc(frm.doc);
			if(new_item.item_name===new_item.item_code) {
				new_item.item_name = null;
			}
			if(new_item.description===new_item.description) {
				new_item.description = null;
			}
			frappe.set_route('Form', 'Item', new_item.name);
		});

		if(frm.doc.has_variants) {
			frm.add_custom_button(__("Item Variant Settings"), function() {
				frappe.set_route("Form", "Item Variant Settings");
			}, __("View"));
		}

		if(frm.doc.__onload && frm.doc.__onload.stock_exists) {
			// Hide variants section if stock exists
			frm.toggle_display("variants_section", 0);
		}
	},

	validate: function(frm){
		erpnext.item.weight_to_validate(frm);
		calculate_conversion_factor(frm);
		
	},
	
	calculate_conversion: function(frm){
		calculate_conversion_factor(frm);
		frm.refresh_field("uoms");
	},

	image: function(frm) {
		refresh_field("image_view");
	},

	is_fixed_asset: function(frm) {
		if (frm.doc.is_fixed_asset) {
			frm.set_value("is_stock_item", 0);
			frm.set_value("default_warehouse", "");
		}
	},

	page_name: frappe.utils.warn_page_name_change,

	item_name: function(frm) {
		if(frm.doc.item_name)
		{
			var newword = process_string(frm.doc.item_name);
			frm.set_value("item_name", newword.trim());
		}
	},
	
	item_code: function(frm) {
		
		if(frm.doc.item_code)
		{
			
			var newword = process_string(frm.doc.item_code);
			frm.set_value("item_code", newword.trim());
		}
		
		
		// if(!frm.doc.item_name)
		frm.set_value("item_name", frm.doc.item_code);
		if(!frm.doc.description)
			frm.set_value("description", frm.doc.item_code);

	},
	
	item_group: function(frm) {
		if(frm.doc.item_group == "Services" || frm.doc.item_group == "Header1" || frm.doc.item_group == "Header2"){
			frm.set_value("is_stock_item", 0);
			frm.set_value("default_warehouse", "");
		}else {
			
			frm.set_value("default_warehouse", "Stores - SLI");
			
		}
	},
	
	opening_stock: function(frm) {
		if(frm.doc.opening_stock > 0){
			
			frappe.call({
				doc: frm.doc,
				method: "get_default_warehouse",
				callback: function(r) {
					if(r.message)
					{
						frm.set_value("opening_warehouse", r.message);
					}
				}
			});
		}

	},

	is_stock_item: function(frm) {
		if(!frm.doc.is_stock_item) {
			frm.set_value("has_batch_no", 0);
			frm.set_value("create_new_batch", 0);
			frm.set_value("has_serial_no", 0);
		}
	},

	copy_from_item_group: function(frm) {
		return frm.call({
			doc: frm.doc,
			method: "copy_specification_from_item_group"
		});
	},

	has_variants: function(frm) {
		erpnext.item.toggle_attributes(frm);
	},

	show_in_website: function(frm) {
		if (frm.doc.default_warehouse && !frm.doc.website_warehouse){
			frm.set_value("website_warehouse", frm.doc.default_warehouse);
		}
	},
	
	add_uom: function(frm) {
		var dialog = new frappe.ui.Dialog({
			fields: [
				{fieldtype:'Float', default:1,
					reqd:1, label:'Stock Qty'},
				{fieldtype:'Column Break',fieldname:'column1'},
				{fieldtype:'Link', options:'UOM',
					read_only:1, label:__('Stock UOM'),default:frm.doc.stock_uom},
				{fieldtype:'Section Break',fieldname:'section1'},
				{fieldtype:'Float', default:1,
					reqd:1, label:'Qty'},
				{fieldtype:'Column Break',fieldname:'column2'},

				{fieldtype:'Link', options:'UOM',
					reqd:1, label:__('UOM')},
					
					// {fieldname:'bundle', fieldtype:'Link', options: 'BOM Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				// {fieldname:'base_variable', fieldtype:'Section Break'},
			]
		});

		dialog.set_primary_action(__('Add'), function() {
			var data = dialog.get_values();
			if(!data) return;
			
			if(data.uom === data.stock_uom) return;
			var conversion_factor = flt(data.stock_qty) / flt(data.qty);
			
			
			check_conversion_factor(frm,data.uom,conversion_factor);
			dialog.hide();
			refresh_field("uoms");
		})

		dialog.show();
	}
});

frappe.ui.form.on('Item Reorder', {
	reorder_levels_add: function(frm, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		var type = frm.doc.default_material_request_type
		row.material_request_type = (type == 'Material Transfer')? 'Transfer' : type;
	}
})

$.extend(erpnext.item, {
	setup_queries: function(frm) {
		frm.fields_dict['expense_account'].get_query = function(doc) {
			return {
				query: "erpnext.controllers.queries.get_expense_account",
			}
		}

		frm.fields_dict['income_account'].get_query = function(doc) {
			return {
				query: "erpnext.controllers.queries.get_income_account"
			}
		}

		frm.fields_dict['buying_cost_center'].get_query = function(doc) {
			return {
				filters: { "is_group": 0 }
			}
		}

		frm.fields_dict['selling_cost_center'].get_query = function(doc) {
			return {
				filters: { "is_group": 0 }
			}
		}


		frm.fields_dict['taxes'].grid.get_field("tax_type").get_query = function(doc, cdt, cdn) {
			return {
				filters: [
					['Account', 'account_type', 'in',
						'Tax, Chargeable, Income Account, Expense Account'],
					['Account', 'docstatus', '!=', 2]
				]
			}
		}

		frm.fields_dict['item_group'].get_query = function(doc, cdt, cdn) {
			return {
				filters: [
					['Item Group', 'docstatus', '!=', 2]
				]
			}
		}

		frm.fields_dict.customer_items.grid.get_field("customer_name").get_query = function(doc, cdt, cdn) {
			return { query: "erpnext.controllers.queries.customer_query" }
		}

		frm.fields_dict.supplier_items.grid.get_field("supplier").get_query = function(doc, cdt, cdn) {
			return { query: "erpnext.controllers.queries.supplier_query" }
		}

		frm.fields_dict['default_warehouse'].get_query = function(doc) {
			return {
				filters: {
					"company": frappe.defaults.get_default("Company"),
					'is_group': 0
				}
			}
		}
		
		frm.fields_dict['opening_warehouse'].get_query = function(doc) {
			return {
				filters: {
					"company": frappe.defaults.get_default("Company"),
					'is_group': 0
				}
			}
		}

		frm.fields_dict.reorder_levels.grid.get_field("warehouse_group").get_query = function(doc, cdt, cdn) {
			return {
				filters: { "is_group": 1 }
			}
		}

		frm.fields_dict.reorder_levels.grid.get_field("warehouse").get_query = function(doc, cdt, cdn) {
			var d = locals[cdt][cdn];

			var filters = {
				"is_group": 0
			}

			if (d.parent_warehouse) {
				filters.extend({"parent_warehouse": d.warehouse_group})
			}

			return {
				filters: filters
			}
		}

	},

	make_dashboard: function(frm) {
		if(frm.doc.__islocal)
			return;

		// Show Stock Levels only if is_stock_item
		if (frm.doc.is_stock_item) {
			frappe.require('assets/js/item-dashboard.min.js', function() {
				var section = frm.dashboard.add_section('<h5 style="margin-top: 0px;">\
					<a href="#stock-balance">' + __("Stock Levels") + '</a></h5>');
				erpnext.item.item_dashboard = new erpnext.stock.ItemDashboard({
					parent: section,
					item_code: frm.doc.name
				});
				erpnext.item.item_dashboard.refresh();
			});
		}
	},

	edit_prices_button: function(frm) {
		frm.add_custom_button(__("Add / Edit Prices"), function() {
			frappe.set_route("List", "Item Price", {"item_code": frm.doc.name});
		}, __("View"));
	},

	weight_to_validate: function(frm){
		if((frm.doc.nett_weight || frm.doc.gross_weight) && !frm.doc.weight_uom) {
			frappe.msgprint(__('Weight is mentioned,\nPlease mention "Weight UOM" too'));
			frappe.validated = 0;
		}
	},

	make_variant: function(frm) {
		if(frm.doc.variant_based_on==="Item Attribute") {
			erpnext.item.show_modal_for_item_attribute_selection(frm);
		} else {
			erpnext.item.show_modal_for_manufacturers(frm);
		}
	},

	show_modal_for_manufacturers: function(frm) {
		var dialog = new frappe.ui.Dialog({
			fields: [
				{fieldtype:'Link', options:'Manufacturer',
					reqd:1, label:'Manufacturer'},
				{fieldtype:'Data', label:'Manufacturer Part Number',
					fieldname: 'manufacturer_part_no'},
			]
		});

		dialog.set_primary_action(__('Make'), function() {
			var data = dialog.get_values();
			if(!data) return;

			// call the server to make the variant
			data.template = frm.doc.name;
			frappe.call({
				method:"erpnext.controllers.item_variant.get_variant",
				args: data,
				callback: function(r) {
					var doclist = frappe.model.sync(r.message);
					dialog.hide();
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				}
			});
		})

		dialog.show();
	},

	show_modal_for_item_attribute_selection: function(frm) {
		var fields = []

		for(var i=0;i< frm.doc.attributes.length;i++){
			var fieldtype, desc;
			var row = frm.doc.attributes[i];
			if (row.numeric_values){
				fieldtype = "Float";
				desc = "Min Value: "+ row.from_range +" , Max Value: "+ row.to_range +", in Increments of: "+ row.increment
			}
			else {
				fieldtype = "Data";
				desc = ""
			}
			fields = fields.concat({
				"label": row.attribute,
				"fieldname": row.attribute,
				"fieldtype": fieldtype,
				"reqd": 1,
				"description": desc
			})
		}

		var d = new frappe.ui.Dialog({
			title: __("Make Variant"),
			fields: fields
		});

		d.set_primary_action(__("Make"), function() {
			var args = d.get_values();
			if(!args) return;
			frappe.call({
				method:"erpnext.controllers.item_variant.get_variant",
				args: {
					"template": frm.doc.name,
					"args": d.get_values()
				},
				callback: function(r) {
					// returns variant item
					if (r.message) {
						var variant = r.message;
						frappe.msgprint_dialog = frappe.msgprint(__("Item Variant {0} already exists with same attributes",
							[repl('<a href="#Form/Item/%(item_encoded)s" class="strong variant-click">%(item)s</a>', {
								item_encoded: encodeURIComponent(variant),
								item: variant
							})]
						));
						frappe.msgprint_dialog.hide_on_page_refresh = true;
						frappe.msgprint_dialog.$wrapper.find(".variant-click").on("click", function() {
							d.hide();
						});
					} else {
						d.hide();
						frappe.call({
							method:"erpnext.controllers.item_variant.create_variant",
							args: {
								"item": frm.doc.name,
								"args": d.get_values()
							},
							callback: function(r) {
								var doclist = frappe.model.sync(r.message);
								frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
							}
						});
					}
				}
			});
		});

		d.show();

		$.each(d.fields_dict, function(i, field) {

			if(field.df.fieldtype !== "Data") {
				return;
			}

			$(field.input_area).addClass("ui-front");

			var input = field.$input.get(0);
			input.awesomplete = new Awesomplete(input, {
				minChars: 0,
				maxItems: 99,
				autoFirst: true,
				list: [],
			});
			input.field = field;

			field.$input
				.on('input', function(e) {
					var term = e.target.value;
					frappe.call({
						method:"frappe.client.get_list",
						args:{
							doctype:"Item Attribute Value",
							filters: [
								["parent","=", i],
								["attribute_value", "like", term + "%"]
							],
							fields: ["attribute_value"]
						},
						callback: function(r) {
							if (r.message) {
								e.target.awesomplete.list = r.message.map(function(d) { return d.attribute_value; });
							}
						}
					});
				})
				.on('focus', function(e) {
					$(e.target).val('').trigger('input');
				})
		});
	},

	toggle_attributes: function(frm) {
		if((frm.doc.has_variants || frm.doc.variant_of)
			&& frm.doc.variant_based_on==='Item Attribute') {
			frm.toggle_display("attributes", true);

			var grid = frm.fields_dict.attributes.grid;

			if(frm.doc.variant_of) {
				// variant

				// value column is displayed but not editable
				grid.set_column_disp("attribute_value", true);
				grid.toggle_enable("attribute_value", false);

				grid.toggle_enable("attribute", false);

				// can't change attributes since they are
				// saved when the variant was created
				frm.toggle_enable("attributes", false);
			} else {
				// template - values not required!

				// make the grid editable
				frm.toggle_enable("attributes", true);

				// value column is hidden
				grid.set_column_disp("attribute_value", false);

				// enable the grid so you can add more attributes
				grid.toggle_enable("attribute", true);
			}

		} else {
			// nothing to do with attributes, hide it
			frm.toggle_display("attributes", false);
		}
	}
});

var check_parent_item_group = function(frm) {
	if(!frm.doc.parent_item_group)
	{		
		frappe.db.get_value('Item Group', {name: frm.doc.item_group}, 'parent_item_group', (r) => {
			parent_item_group = r && r.parent_item_group;
			frm.set_value("parent_item_group",parent_item_group);
		});
		
	}
}
var calculate_conversion_factor = function(frm) {
	
	if(!frm.doc.parent_item_group)
	{		
		frappe.db.get_value('Item Group', {name: frm.doc.item_group}, 'parent_item_group', (r) => {
			parent_item_group = r && r.parent_item_group;
			frm.set_value("parent_item_group",parent_item_group);
		});
		
	}
	else{
		
	}
	
	if (frm.doc.depth > 0 && frm.doc.width > 0 && check_current_units(frm.doc.stock_uom) 
	&& (frm.doc.parent_item_group == "Raw Material" || frm.doc.item_group == "Raw Material")){
			
			var conversion_factors = get_dimensions(frm);
			var conversion_factor = conversion_factors[0];
			var cft_conversion_factor = conversion_factors[1];
			conversion_factor = flt(conversion_factor.toFixed(5));
			cft_conversion_factor = flt(cft_conversion_factor.toFixed(5));

			check_conversion_factor(frm,"sqm",conversion_factor);
			check_conversion_factor(frm,"cft",cft_conversion_factor);

	}
	
}

var check_current_units = function(unit) {
	if (["sqm","cft","ft","m","cm","in","mm"].indexOf(unit) < 0){
		return true;
	}
		
	return false;
}


var check_conversion_factor = function(frm,unit,conversion_factor) {
	if(flt(conversion_factor) > 0)
	{
		var uoms = frm.doc.uoms || [];
	
		var hasUOM = false;
		for(var i=0;i<uoms.length;i++) {
			if(uoms[i].uom === unit){
				hasUOM = true;
				if(flt(uoms[i].conversion_factor) != conversion_factor){
					//frappe.msgprint(__("Dimensions given calculate conversion factor {0}", [conversion_factor]));
					uoms[i].conversion_factor = conversion_factor;
				}
				break;
			}
			
		}
		
		if(hasUOM == false){
			var row = frappe.model.add_child(cur_frm.doc, cur_frm.fields_dict.uoms.df.options, cur_frm.fields_dict.uoms.df.fieldname);
			row.uom = unit;
			row.conversion_factor = conversion_factor;
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

var process_string = function(code){
	
	code = code.replace(/  +/g, ' ');
			var newword = "";
			var tests = ["mm","cm","m","in","ft"];

			code.trim().split(" ").forEach(function(s) {
				if(s.toLowerCase() == "x"){
					var ss = s.toLowerCase();
					if (newword == "")
						newword = ss;
					else
						newword = newword + " " + ss;
				}
				else if (tests.indexOf(s.toLowerCase()) != -1)
				{
					var ss = s.toLowerCase();
					if (newword == "")
						newword = ss;
					else
						newword = newword + ss;
				}
				else
				{
					var ss = s;
					if (newword == "")
						newword = ss;
					else
						newword = newword + " " + ss;
					
				}
			});
			newword = newword.replace(" X ", "x");
			newword = newword.replace(" x ", "x");
			// newword = newword.replace('"', "");
			// newword = newword.replace(' " ', "");
			return newword.trim();
}

var get_dimensions = function(frm) {
	
	var length = convert_units(frm.doc.depthunit,frm.doc.depth);
	var width = convert_units(frm.doc.widthunit,frm.doc.width);
	var height = convert_units(frm.doc.heightunit,frm.doc.height);
	
	var perimeter = 2*flt(length)+2*flt(width);
	var farea = flt(length) * flt(width);
	var fvolume = flt(length) * flt(width) * flt(height);
	var fvolumecft = fvolume * 35.3147;
	
	var conversion_factor = 1/flt(farea);
	var cft_conversion_factor = 1/flt(fvolumecft);
	return [conversion_factor, cft_conversion_factor];
}
