// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.bom");

frappe.ui.form.on("BOM", {
	setup(frm) {
		// frm.custom_make_buttons = {
			// 'Work Order': 'Work Order',
			// 'Quality Inspection': 'Quality Inspection'
		// };


		// frm.set_query("bom_no", "items", function() {
			// return {
				// filters: {
					// 'currency': frm.doc.currency,
					// 'company': frm.doc.company
				// }
			// };
		// });

		frm.set_query("source_warehouse", "items", function () {
			return {
				filters: {
					company: frm.doc.company,
				},
			};
		});

		frm.set_query("item", function () {
			return {
				query: "erpnext.manufacturing.doctype.bom.bom.item_query",
				filters: {
					is_stock_item: 1,
				},
			};
		});

		frm.set_query("project", function () {
			return {
				filters: [["Project", "status", "not in", "Completed, Cancelled"]],
			};
		});

		frm.set_query("item_code", "items", function (doc) {
			return {
				query: "erpnext.manufacturing.doctype.bom.bom.item_query",
				filters: {
					include_item_in_manufacturing: 1,
					is_fixed_asset: 0,
				},
			};
		});

		frm.set_query("bom_no", "items", function (doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: [
					["currency", "=", cur_frm.doc.currency],
					["company", "=", cur_frm.doc.company],
					["item", "=", d.item_code],
					["is_active", "=", 1],
					["docstatus", "<", 2],
				]
			};
		});
		
		frm.set_query("bom", "bomitems", function(doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: [
					["currency", "=", cur_frm.doc.currency],
					["company", "=", cur_frm.doc.company],
					["item", "=", d.item_code],
					["is_active", "=", 1],
					["docstatus", "<", 2],
				]
			};
		});
	},

	validate(frm) {
		if (frm.doc.fg_based_operating_cost && frm.doc.with_operations) {
			frappe.throw({
				message: __("Please check either with operations or FG Based Operating Cost."),
				title: __("Mandatory"),
			});
		}
	},
	with_operations(frm) {
		frm.set_df_property("fg_based_operating_cost", "hidden", frm.doc.with_operations ? 1 : 0);
	},

	fg_based_operating_cost(frm) {
		frm.set_df_property("with_operations", "hidden", frm.doc.fg_based_operating_cost ? 1 : 0);
	},

	onload_post_render(frm) {
		frm.get_field("items").grid.set_multiple_add("item_code", "qty");
		
		/* setTimeout(function(){
				
						frm.trigger("refresh_builder_editable");
			}, 1000); */
	},
	
	refresh(frm) {
		// frm.toggle_enable("item", frm.doc.__islocal);


		frm.set_indicator_formatter("item_code", function (doc) {
			if (doc.original_item) {
				return doc.item_code != doc.original_item ? "orange" : "";
			}
			return "";
		});

		if (!frm.is_new() && frm.doc.docstatus < 2) {
			frm.add_custom_button(__("Update Cost"), function () {
				frm.events.update_cost(frm, true);
			});
			frm.add_custom_button(__("Browse BOM"), function () {
				frappe.route_options = {
					bom: frm.doc.name,
				};
				frappe.set_route("Tree", "BOM");
			});
		}

		if (!frm.is_new() && !frm.doc.docstatus == 0) {
			frm.add_custom_button(__("New Version"), function () {
				let new_bom = frappe.model.copy_doc(frm.doc);
				frappe.set_route("Form", "BOM", new_bom.name);
			});
		}
		
		/* if(frm.doc.docstatus!=0) {
		}

		if (frm.doc.docstatus == 1) {
			frm.add_custom_button(
				__("Work Order"),
				function () {
					frm.trigger("make_work_order");
				},
				__("Create")
			);

			if (frm.doc.has_variants) {
				frm.add_custom_button(
					__("Variant BOM"),
					function () {
						frm.trigger("make_variant_bom");
					},
					__("Create")
				);
			}

			if (frm.doc.inspection_required) {
				frm.add_custom_button(
					__("Quality Inspection"),
					function () {
						frm.trigger("make_quality_inspection");
					},
					__("Create")
				);
			}

			frm.page.set_inner_btn_group_as_primary(__('Create'));
		} */

		if (frm.doc.items && frm.doc.allow_alternative_item) {
			const has_alternative = frm.doc.items.find((i) => i.allow_alternative_item === 1);
			if (frm.doc.docstatus == 0 && has_alternative) {
				frm.add_custom_button(__("Alternate Item"), () => {
					erpnext.utils.select_alternate_items({
						frm: frm,
						child_docname: "items",
						warehouse_field: "source_warehouse",
						child_doctype: "BOM Item",
						original_item_field: "original_item",
						condition: (d) => {
							if (d.allow_alternative_item) {
								return true;
							}
						},
					});
				});
			}
		}
		
		if (frm.doc.docstatus<1)
		{
			frm.get_field("build_bom").$input.addClass("btn-primary");
		}
		
		if (frm.doc.has_variants) {
			frm.set_intro(
				__("This is a Template BOM and will be used to make the work order for {0} of the item {1}", [
					`<a class="variants-intro">variants</a>`,
					`<a href="/app/item/${frm.doc.item}">${frm.doc.item}</a>`,
				]),
				true
			);

			frm.$wrapper.find(".variants-intro").on("click", () => {
				frappe.set_route("List", "Item", { variant_of: frm.doc.item });
			});
		}
	},

	make_work_order(frm) {
		frm.events.setup_variant_prompt(frm, "Work Order", (frm, item, data, variant_items) => {
			frappe.call({
				method: "erpnext.manufacturing.doctype.work_order.work_order.make_work_order",
				args: {
					bom_no: frm.doc.name,
					item: item,
					qty: data.qty || 0.0,
					project: frm.doc.project,
					variant_items: variant_items,
				},
				freeze: true,
				callback(r) {
					if (r.message) {
						let doc = frappe.model.sync(r.message)[0];
						frappe.set_route("Form", doc.doctype, doc.name);
					}
				},
			});
		});
	},

	make_variant_bom(frm) {
		frm.events.setup_variant_prompt(
			frm,
			"Variant BOM",
			(frm, item, data, variant_items) => {
				frappe.call({
					method: "erpnext.manufacturing.doctype.bom.bom.make_variant_bom",
					args: {
						source_name: frm.doc.name,
						bom_no: frm.doc.name,
						item: item,
						variant_items: variant_items,
					},
					freeze: true,
					callback(r) {
						if (r.message) {
							let doc = frappe.model.sync(r.message)[0];
							frappe.set_route("Form", doc.doctype, doc.name);
						}
					},
				});
			},
			true
		);
	},

	setup_variant_prompt(frm, title, callback, skip_qty_field) {
		const fields = [];

		if (frm.doc.has_variants) {
			fields.push({
				fieldtype: "Link",
				label: __("Variant Item"),
				fieldname: "item",
				options: "Item",
				reqd: 1,
				get_query() {
					return {
						query: "erpnext.controllers.queries.item_query",
						filters: {
							variant_of: frm.doc.item,
						},
					};
				},
			});
		}

		if (!skip_qty_field) {
			fields.push({
				fieldtype: "Float",
				label: __("Qty To Manufacture"),
				fieldname: "qty",
				reqd: 1,
				default: 1,
				onchange: () => {
					const { quantity, items: rm } = frm.doc;
					const variant_items_map = rm.reduce((acc, item) => {
						acc[item.item_code] = item.qty;
						return acc;
					}, {});
					const mf_qty = cur_dialog.fields_list.filter((f) => f.df.fieldname === "qty")[0]?.value;
					const items = cur_dialog.fields.filter((f) => f.fieldname === "items")[0]?.data;

					if (!items) {
						return;
					}

					items.forEach((item) => {
						item.qty = (variant_items_map[item.item_code] * mf_qty) / quantity;
					});

					cur_dialog.refresh();
				},
			});
		}

		var has_template_rm = frm.doc.items.filter((d) => d.has_variants === 1) || [];
		if (has_template_rm && has_template_rm.length > 0) {
			fields.push({
				fieldname: "items",
				fieldtype: "Table",
				label: __("Raw Materials"),
				fields: [
					{
						fieldname: "item_code",
						options: "Item",
						label: __("Template Item"),
						fieldtype: "Link",
						in_list_view: 1,
						reqd: 1,
					},
					{
						fieldname: "variant_item_code",
						options: "Item",
						label: __("Variant Item"),
						fieldtype: "Link",
						in_list_view: 1,
						reqd: 1,
						get_query(data) {
							if (!data.item_code) {
								frappe.throw(__("Select template item"));
							}

							return {
								query: "erpnext.controllers.queries.item_query",
								filters: {
									variant_of: data.item_code,
								},
							};
						},
					},
					{
						fieldname: "qty",
						label: __("Quantity"),
						fieldtype: "Float",
						in_list_view: 1,
						reqd: 1,
					},
					{
						fieldname: "source_warehouse",
						label: __("Source Warehouse"),
						fieldtype: "Link",
						options: "Warehouse",
					},
					{
						fieldname: "operation",
						label: __("Operation"),
						fieldtype: "Data",
						hidden: 1,
					},
				],
				in_place_edit: true,
				data: [],
				get_data() {
					return [];
				},
			});
		}

		let dialog = frappe.prompt(
			fields,
			(data) => {
				let item = data.item || frm.doc.item;
				let variant_items = data.items || [];

				variant_items.forEach((d) => {
					if (!d.variant_item_code) {
						frappe.throw(__("Select variant item code for the template item {0}", [d.item_code]));
					}
				});

				callback(frm, item, data, variant_items);
			},
			__(title),
			__("Create")
		);

		has_template_rm.forEach((d) => {
			dialog.fields_dict.items.df.data.push({
				item_code: d.item_code,
				variant_item_code: "",
				qty: d.qty,
				source_warehouse: d.source_warehouse,
				operation: d.operation,
			});
		});

		if (has_template_rm && has_template_rm.length) {
			dialog.fields_dict.items.grid.refresh();
		}
	},

	make_quality_inspection(frm) {
		frappe.model.open_mapped_doc({
			method: "erpnext.stock.doctype.quality_inspection.quality_inspection.make_quality_inspection",
			frm: frm,
		});
	},

	update_cost(frm, save_doc = false) {
		return frappe.call({
			doc: frm.doc,
			method: "update_cost",
			freeze: true,
			args: {
				update_parent: true,
				save: save_doc,
				from_child_bom: false,
			},
			callback(r) {
				refresh_field("items");
				if (!r.exc) frm.refresh_fields();
			},
		});
	},

	rm_cost_as_per(frm) {
		if (in_list(["Valuation Rate", "Last Purchase Rate"], frm.doc.rm_cost_as_per)) {
			frm.set_value("plc_conversion_rate", 1.0);
		}
	},

	routing(frm) {
		if (frm.doc.routing) {
			frappe.call({
				doc: frm.doc,
				method: "get_routing",
				freeze: true,
				callback(r) {
					if (!r.exc) {
						frm.refresh_fields();
						erpnext.bom.calculate_op_cost(frm.doc);
						erpnext.bom.calculate_total(frm.doc);
					}
				},
			});
		}
	},
	item(frm) {
		frm.events.use_manufacturing_template(frm);
	},
	
	use_manufacturing_template(frm) {
		if (frm.doc.docstatus > 0 || !frm.doc.item)
			return;
		
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Item",
				filters: { "name": frm.doc.item},
				fields: ["depth","width","height","depthunit","widthunit","heightunit"]
			},
			freeze: true,
			callback: function (r) {
				frm.set_value({"depth":r.message["depth"],
				"width":r.message["width"],
				"height":r.message["height"],
				"depthunit":r.message["depthunit"],
				"widthunit":r.message["widthunit"],
				"heightunit":r.message["heightunit"]})
				
				var bomitems = frm.doc.bomitems || [];
				refresh_builder_editable_row(bomitems,true,true)

	
			}
		});
	},	
	
	refresh_part_dimensions(frm) {
		var bomitems = frm.doc.bomitems || [];
		refresh_builder_editable_row(bomitems,false,true)

	},
	build_bom(frm) {
		
		if (frm.doc.docstatus > 0) {
			return;
		}
		
		var bomitems = frm.doc.bomitems || [];

		if(bomitems.length == 0)
		{
			cur_frm.dirty();
			return;
		}
					
		if(!frm.doc.depth || !frm.doc.width || !frm.doc.height){
			frappe.msgprint(__("Depth, width and height missing or equal to 0"));
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
	
	mrp_duty_percent(frm) {
		erpnext.bom.calculate_total(frm.doc);	
	},
	non_duty_percent(frm) {
		erpnext.bom.calculate_total(frm.doc);	
	},
	mrp_profit_percent(frm) {
		erpnext.bom.calculate_total(frm.doc);	
	},
	get_production_overheads(frm){
		if(frm.doc.__islocal)
		{
			frappe.msgprint(__("Document needs to be saved first"));
			return;
			
		}

		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Operating Cost Type",
				filters: { "default_cost": "1"},
				fields: ["name"],
				order_by: "sort_order",
			},
			callback: function (r) {
				frm.doc.mrp_operating_costs = [];
				for(var i=0;i<r.message.length;i++) {
					var row = frappe.model.add_child(frm.doc,"mrp_operating_costs");
					row.type = r.message[i].name;
					cur_frm.script_manager.trigger("type", row.doctype, row.name);

				}
				refresh_field("mrp_operating_costs");
	
			}
		});
	},
		
		

	process_loss_percentage(frm) {
		let qty = 0.0;
		if (frm.doc.process_loss_percentage) {
			qty = (frm.doc.quantity * frm.doc.process_loss_percentage) / 100;
		}

		frm.set_value("process_loss_qty", qty);
	},
});

erpnext.bom.BomController = class BomController extends erpnext.TransactionController {
	conversion_rate(doc) {
		if (this.frm.doc.currency === this.get_company_currency()) {
			this.frm.set_value("conversion_rate", 1.0);
		} else {
			erpnext.bom.update_cost(doc);
		}
	}

	item_code(doc, cdt, cdn) {
		var scrap_items = false;
		var child = locals[cdt][cdn];
		if (child.doctype == "BOM Scrap Item") {
			scrap_items = true;
		}

		if (child.bom_no) {
			child.bom_no = "";
		}

		get_bom_material_detail(doc, cdt, cdn, scrap_items);
	}

	buying_price_list(doc) {
		this.apply_price_list();
	}

	plc_conversion_rate(doc) {
		if (!this.in_apply_price_list) {
			this.apply_price_list(null, true);
		}
	}

	conversion_factor(doc, cdt, cdn) {
		if (frappe.meta.get_docfield(cdt, "stock_qty", cdn)) {
			var item = frappe.get_doc(cdt, cdn);
			frappe.model.round_floats_in(item, ["qty", "conversion_factor"]);
			item.stock_qty = flt(item.qty * item.conversion_factor, precision("stock_qty", item));
			refresh_field("stock_qty", item.name, item.parentfield);
			this.toggle_conversion_factor(item);
			this.frm.events.update_cost(this.frm);
		}
	}
};

extend_cscript(cur_frm.cscript, new erpnext.bom.BomController({ frm: cur_frm }));

cur_frm.cscript.hour_rate = function (doc) {
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_total(doc);
};

cur_frm.cscript.time_in_mins = cur_frm.cscript.hour_rate;

cur_frm.cscript.bom_no = function (doc, cdt, cdn) {
	get_bom_material_detail(doc, cdt, cdn, false);
};

cur_frm.cscript.is_default = function (doc) {
	if (doc.is_default) cur_frm.set_value("is_active", 1);
};

var get_bom_material_detail = function (doc, cdt, cdn, scrap_items) {
	if (!doc.company) {
		frappe.throw({ message: __("Please select a Company first."), title: __("Mandatory") });
	}

	var d = locals[cdt][cdn];
	if (d.item_code) {
		return frappe.call({
			doc: doc,
			method: "get_bom_material_detail",
			args: {
				company: doc.company,
				item_code: d.item_code,
				bom_no: d.bom_no != null ? d.bom_no : "",
				scrap_items: scrap_items,
				qty: d.qty,
				stock_qty: d.stock_qty,
				include_item_in_manufacturing: d.include_item_in_manufacturing,
				uom: d.uom,
				stock_uom: d.stock_uom,
				conversion_factor: d.conversion_factor,
				sourced_by_supplier: d.sourced_by_supplier,
				do_not_explode: d.do_not_explode,
			},
			callback: function (r) {
				d = locals[cdt][cdn];

				$.extend(d, r.message);
				
				refresh_field("items");
				refresh_field("scrap_items");

				doc = locals[doc.doctype][doc.name];
				erpnext.bom.calculate_rm_cost(doc);
				erpnext.bom.calculate_scrap_materials_cost(doc);
				erpnext.bom.calculate_total(doc);
			},
			freeze: true,
		});
	}
};

cur_frm.cscript.qty = function (doc) {
	erpnext.bom.calculate_rm_cost(doc);
	erpnext.bom.calculate_scrap_materials_cost(doc);
	erpnext.bom.calculate_total(doc);
};

cur_frm.cscript.rate = function (doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	const is_scrap_item = cdt == "BOM Scrap Item";

	if (d.bom_no) {
		frappe.msgprint(__("You cannot change the rate if BOM is mentioned against any Item."));
		get_bom_material_detail(doc, cdt, cdn, is_scrap_item);
	} else {
		erpnext.bom.calculate_rm_cost(doc);
		erpnext.bom.calculate_scrap_materials_cost(doc);
		erpnext.bom.calculate_total(doc);
	}
};

erpnext.bom.update_cost = function (doc) {
	erpnext.bom.calculate_op_cost(doc);
	erpnext.bom.calculate_rm_cost(doc);
	erpnext.bom.calculate_scrap_materials_cost(doc);
	erpnext.bom.calculate_total(doc);
	cur_frm.dirty();
};

erpnext.bom.calculate_op_cost = function (doc) {
	doc.operating_cost = 0.0;
	doc.base_operating_cost = 0.0;

	if (doc.with_operations) {
		doc.operations.forEach((item) => {
			let operating_cost = flt((flt(item.hour_rate) * flt(item.time_in_mins)) / 60, 2);
			let base_operating_cost = flt(operating_cost * doc.conversion_rate, 2);
			frappe.model.set_value("BOM Operation", item.name, {
				operating_cost: operating_cost,
				base_operating_cost: base_operating_cost,
			});

			doc.operating_cost += operating_cost;
			doc.base_operating_cost += base_operating_cost;
		});
	} else if (doc.fg_based_operating_cost) {
		let total_operating_cost = doc.quantity * flt(doc.operating_cost_per_bom_quantity);
		doc.operating_cost = total_operating_cost;
		doc.base_operating_cost = flt(total_operating_cost * doc.conversion_rate, 2);
	}
	refresh_field(["operating_cost", "base_operating_cost"]);
};

// rm : raw material
erpnext.bom.calculate_rm_cost = function (doc) {
	var rm = doc.items || [];
	var total_rm_cost = 0;
	var base_total_rm_cost = 0;
	for(var i=0;i<rm.length;i++) {
		
		// TODO FIX THIS - FIXED
		//var amount = flt(rm[i].rate) * flt(rm[i].stock_qty);
		var amount = flt(rm[i].rate) * flt(rm[i].qty);
		var base_amount = amount * flt(doc.conversion_rate);

		// TODO FIX BY ME
		frappe.model.set_value('BOM Item', rm[i].name, 'base_stock_rate',
			flt(rm[i].stock_rate) * flt(doc.conversion_rate));


		frappe.model.set_value('BOM Item', rm[i].name, 'base_rate',
			flt(rm[i].rate) * flt(doc.conversion_rate));
		frappe.model.set_value('BOM Item', rm[i].name, 'amount', amount);
		frappe.model.set_value('BOM Item', rm[i].name, 'base_amount', base_amount);
		frappe.model.set_value('BOM Item', rm[i].name,
			'qty_consumed_per_unit', flt(rm[i].stock_qty)/flt(doc.quantity));

		total_rm_cost += amount;
		base_total_rm_cost += base_amount;
	}
	cur_frm.set_value("raw_material_cost", total_rm_cost);
	cur_frm.set_value("base_raw_material_cost", base_total_rm_cost);
};

// sm : scrap material
erpnext.bom.calculate_scrap_materials_cost = function (doc) {
	var sm = doc.scrap_items || [];
	var total_sm_cost = 0;
	var base_total_sm_cost = 0;

	for (var i = 0; i < sm.length; i++) {
		var base_rate = flt(sm[i].rate) * flt(doc.conversion_rate);
		var amount = flt(sm[i].rate) * flt(sm[i].stock_qty);
		var base_amount = amount * flt(doc.conversion_rate);

		frappe.model.set_value("BOM Scrap Item", sm[i].name, "base_rate", base_rate);
		frappe.model.set_value("BOM Scrap Item", sm[i].name, "amount", amount);
		frappe.model.set_value("BOM Scrap Item", sm[i].name, "base_amount", base_amount);

		total_sm_cost += amount;
		base_total_sm_cost += base_amount;
	}

	cur_frm.set_value("scrap_material_cost", total_sm_cost);
	cur_frm.set_value("base_scrap_material_cost", base_total_sm_cost);
};

// Calculate Total Cost
erpnext.bom.calculate_total = function (doc) {
	var total_cost = flt(doc.operating_cost) + flt(doc.raw_material_cost) - flt(doc.scrap_material_cost);
	var base_total_cost =
		flt(doc.base_operating_cost) + flt(doc.base_raw_material_cost) - flt(doc.base_scrap_material_cost);

	cur_frm.set_value("total_cost", total_cost);
	cur_frm.set_value("base_total_cost", base_total_cost);
	calculate_duty(doc);
};

cur_frm.cscript.validate = function (doc) {
	erpnext.bom.update_cost(doc);
};

frappe.ui.form.on('BOM Operation', {
	operation: function(frm, cdt, cdn) {
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
		});
	},

	workstation: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(!d.workstation) return;
		
		frappe.call({
			"method": "frappe.client.get",
			args: {
				doctype: "Workstation",
				name: d.workstation
			},
			callback: function (data) {
				frappe.model.set_value(d.doctype, d.name, "base_hour_rate", data.message.hour_rate);
				frappe.model.set_value(d.doctype, d.name, "hour_rate",
					flt(flt(data.message.hour_rate) / flt(frm.doc.conversion_rate)), 2);

				erpnext.bom.calculate_op_cost(frm.doc);
				erpnext.bom.calculate_total(frm.doc);
			}
		});
	},
	hour_rate: function(frm, cdt, cdn) {
		erpnext.bom.calculate_op_cost(frm.doc);
		erpnext.bom.calculate_total(frm.doc);
	},

	time_in_mins: function(frm, cdt, cdn) {
		erpnext.bom.calculate_op_cost(frm.doc);
		erpnext.bom.calculate_total(frm.doc);
	},
});

frappe.ui.form.on("BOM Item", {
	do_not_explode: function (frm, cdt, cdn) {
		get_bom_material_detail(frm.doc, cdt, cdn, false);
	},
});

frappe.ui.form.on("BOM Item", "qty", function (frm, cdt, cdn) {
	var d = locals[cdt][cdn];
	d.stock_qty = d.qty * d.conversion_factor;
	refresh_field("stock_qty", d.name, d.parentfield);
});

frappe.ui.form.on("BOM Item", "item_code", function (frm, cdt, cdn) {
	var d = locals[cdt][cdn];
	frappe.db.get_value("Item", { name: d.item_code }, "allow_alternative_item", (r) => {
		d.allow_alternative_item = r.allow_alternative_item;
	});
	refresh_field("allow_alternative_item", d.name, d.parentfield);
});

frappe.ui.form.on("BOM Item", "sourced_by_supplier", function (frm, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.sourced_by_supplier) {
		d.rate = 0;
		refresh_field("rate", d.name, d.parentfield);
	}
});

frappe.ui.form.on("BOM Item", "rate", function (frm, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.sourced_by_supplier) {
		d.rate = 0;
		refresh_field("rate", d.name, d.parentfield);
	}
});

frappe.ui.form.on("BOM Operation", "operations_remove", function (frm) {
	erpnext.bom.calculate_op_cost(frm.doc);
	erpnext.bom.calculate_total(frm.doc);
});

frappe.ui.form.on("BOM Item", "items_remove", function (frm) {
	erpnext.bom.calculate_rm_cost(frm.doc);
	erpnext.bom.calculate_total(frm.doc);
});

frappe.ui.form.on("BOM", "with_operations", function(frm) {
	if(!cint(frm.doc.with_operations)) {
		frm.set_value("operations", []);
	}
	toggle_operations(frm);
});


//////////////////////////////

frappe.ui.form.on("Operating Cost", {
	
	type:function(frm, cdt, cdn) {
		
		var d = locals[cdt][cdn];

		if(!d.type) return;

		frappe.call({
			"method": "frappe.client.get",
			args: {
				doctype: "Operating Cost Type",
				name: d.type
			},
			callback: function (data) {
				
				var percent = data.message.default_percent;
				var raw_material_cost = frm.doc.raw_material_cost || 0;
				var amount = flt(data.message.default_percent/100 * raw_material_cost).toFixed(2);
				frappe.model.set_value(d.doctype, d.name, "percent",percent);
				frappe.model.set_value(d.doctype, d.name, "amount",amount);
				calculate_duty(frm.doc);
			}

		})
	},
	
	percent:function(frm, cdt, cdn) {
		
		var d = locals[cdt][cdn];

		if(!d.type) return;
			var amount = flt(d.percent/100 * cur_frm.doc.raw_material_cost).toFixed(2);
		frappe.model.set_value(d.doctype, d.name, "amount", amount);
		calculate_duty(frm.doc);
	},
	
	mrp_operating_costs_remove:function(frm, cdt, cdn) {
		calculate_duty(frm.doc);
	},
});


frappe.ui.form.on('BOM Explosion Item', {
	dutible:function(frm, cdt, cdn) {
		calculate_duty(frm.doc);
	},
});



var calculate_duty = function(doc) {	
	var rm = doc.exploded_items || [];
	var production_overheads = doc.mrp_operating_costs || [];
	var dutible = 0;
	var non_dutible = 0;
	var mrp_total_production_overhead = 0;

	for(var i=0;i<rm.length;i++) {
		
		if(rm[i].dutible == 1)
		{
			dutible += flt(rm[i].amount);
			
		}
		else{
			non_dutible += flt(rm[i].amount);
		}
		
		
	}
	var raw_material_cost = doc.raw_material_cost || 0;

	for(var i=0;i<production_overheads.length;i++) {
		
		production_overheads[i].amount = flt(production_overheads[i].percent/100 * raw_material_cost).toFixed(2);
		mrp_total_production_overhead += flt(production_overheads[i].amount);
	}
	
	var mrp_base_total_production_overhead = mrp_total_production_overhead * flt(doc.conversion_rate);
	var mrp_factory_price = flt(dutible + non_dutible + mrp_total_production_overhead);	
	var mrp_base_factory_price = flt(mrp_factory_price) * flt(doc.conversion_rate);
	var total_duty = dutible + (mrp_factory_price * (doc.non_duty_percent/100));	
	var base_total_duty = flt(total_duty) * flt(doc.conversion_rate);
	
	total_duty = Math.ceil(total_duty);
	base_total_duty = Math.ceil(base_total_duty);
	
	var mrp_final_price = flt(mrp_factory_price) + (total_duty * (doc.mrp_duty_percent/100));
	var mrp_base_final_price = flt(mrp_final_price) * flt(doc.conversion_rate);
	
	
	var mrp_final_price_plus_profit = flt(mrp_factory_price) + (mrp_final_price * (doc.mrp_profit_percent/100));
	var mrp_base_final_price_plus_profit = flt(mrp_final_price_plus_profit) * flt(doc.conversion_rate);

	cur_frm.set_value("dutible", dutible);
	cur_frm.set_value("non_dutible", non_dutible);
	cur_frm.set_value("total_duty", total_duty);
	cur_frm.set_value("base_total_duty", base_total_duty);
	cur_frm.set_value("mrp_factory_price", mrp_factory_price);
	cur_frm.set_value("mrp_base_factory_price", mrp_base_factory_price);
	cur_frm.set_value("mrp_total_production_overhead", mrp_total_production_overhead);
	cur_frm.set_value("mrp_base_total_production_overhead", mrp_base_total_production_overhead);
	cur_frm.set_value("mrp_final_price", mrp_final_price);
	cur_frm.set_value("mrp_base_final_price", mrp_base_final_price);
	
	cur_frm.set_value("mrp_final_price_plus_profit", mrp_final_price_plus_profit);
	cur_frm.set_value("mrp_base_final_price_plus_profit", mrp_base_final_price_plus_profit);

};


// builder ---------------------------------
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
		filters: [["Item", "name", "!=", cur_frm.doc.item]]
	}
}

frappe.ui.form.on('BOM Builder Item', {
	bomitems_add:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
	},
	
	bomitems_remove:function(frm, cdt, cdn) {
		frappe.msgprint(__("Build BOM Required"));
		cur_frm.dirty();
		// Slows down with multiple removes
		// cur_frm.trigger("build_bom");
	},
	
	bb_item: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item && d.side){
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
	bom: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.bb_item){
			cur_frm.trigger("build_bom");
		
		}
	},
});

var refresh_builder_editable_row = function(rows,build=false,update_dimensions=false) {
	
	var depthOriginal = frappe.mrp.convert_units(cur_frm.doc.depthunit,cur_frm.doc.depth);
	var widthOriginal = frappe.mrp.convert_units(cur_frm.doc.widthunit,cur_frm.doc.width);
	var heightOriginal = frappe.mrp.convert_units(cur_frm.doc.heightunit,cur_frm.doc.height);
	frappe.call({
		method:'erpnext.manufacturing.doctype.bom.bom.get_all_part_details',
		args:{
			args: rows,
		},
		callback:function (r) {
			for (let index = 0; index < r.message.length; ++index) {
				const d = r.message[index];
				if(!d.name)
					continue;
				var row_name = d.name;
				var length = d.length;
				var width = d.width;
				var height = d.height;		
				var side = d.side;
				var plane = d.plane;
				var requom = d.requom;

				var allow_col1 = Boolean(Number(d.allow_col1)) ;
				var allow_col2 = Boolean(Number(d.allow_col2)) ;
				var allow_col3 = Boolean(Number(d.allow_col3)) ;
				var allow_edit = false;
				
				if(plane == "top"){
					allow_edit = false;
					length = depthOriginal;
					width = widthOriginal;
					height = heightOriginal;
				}
				else if(plane == "front"){
					allow_edit = false;
					length = heightOriginal;
					width = widthOriginal;
					height = depthOriginal;
				}
				else if(plane == "side"){
					allow_edit = false;
					length = depthOriginal;
					width = heightOriginal;
					height = widthOriginal;
				}
				else{
					allow_edit = true;
					length = d.length;
					width = d.width;
					height = d.height;
				}
				
				var grid_row = cur_frm.get_field('bomitems').grid.get_row(row_name);
				if(grid_row)
				{
					if(allow_edit)
					{	
						grid_row.toggle_editable("length", allow_col1);
						grid_row.toggle_editable("width", allow_col2);
						grid_row.toggle_editable("bb_item", allow_col3);
					}
					else
					{
						// grid_row.toggle_editable("length", false);
						// grid_row.toggle_editable("width", false);
						// grid_row.toggle_editable("height", false);
					}
				
				}
				
				if(update_dimensions){
					frappe.model.set_value(d.doctype, d.name, "length", length);
					frappe.model.set_value(d.doctype, d.name, "height", height);
					frappe.model.set_value(d.doctype, d.name, "width", width);
					frappe.model.set_value(d.doctype, d.name, "requom", requom);
				}	
			}
			if(build){
				cur_frm.trigger("build_bom");
			}	
		}
	})
}

var calculate_builder_dimensions = function(d, build=false) {
	if(!d.bb_item)
		return;
	
	if(!d.side) 
		return;

	var side = d.side;
	var length = 0;
	var width = 0;
	var height = 0;
	var requom = d.requom;
	var row_name = d.name;
	
	var depthOriginal = frappe.mrp.convert_units(cur_frm.doc.depthunit,cur_frm.doc.depth);
	var widthOriginal = frappe.mrp.convert_units(cur_frm.doc.widthunit,cur_frm.doc.width);
	var heightOriginal = frappe.mrp.convert_units(cur_frm.doc.heightunit,cur_frm.doc.height);

	frappe.call({
		method:'erpnext.manufacturing.doctype.bom.bom.get_part_details',
		args:{
			part: side,
			item_code:d.bb_item,
		},
		callback:function (r) {
			var plane = r.message[0];
			var requom = r.message[1];
			
			
			var allow_col1 = Boolean(Number(r.message[2])) ;
			var allow_col2 = Boolean(Number(r.message[3])) ;
			var allow_col3 = Boolean(Number(r.message[4])) ;
			
			var allow_edit = false;
			
			if(plane == "top"){
				allow_edit = false;
				length = depthOriginal;
				width = widthOriginal;
				height = heightOriginal;
			}
			else if(plane == "front"){
				allow_edit = false;
				length = heightOriginal;
				width = widthOriginal;
				height = depthOriginal;
			}
			else if(plane == "side"){
				allow_edit = false;
				length = depthOriginal;
				width = heightOriginal;
				height = widthOriginal;
			}
			else{
				allow_edit = true;
				length = d.length;
				width = d.width;
				height = d.height;
			}
			
			/* if(cur_frm.get_field('items').grid.fields_map.conversion_factor) {
			cur_frm.fields_dict.items.grid.toggle_enable("conversion_factor",
				((item.uom != item.stock_uom) && !frappe.meta.get_docfield(cur_frm.fields_dict.items.grid.doctype, "conversion_factor").read_only)? true: false);
			} */
			
			var grid_row = cur_frm.get_field('bomitems').grid.get_row(row_name);
			if(grid_row)
			{
				if(allow_edit)
				{
					grid_row.toggle_editable("length", allow_col1);
					grid_row.toggle_editable("width", allow_col2);
					grid_row.toggle_editable("height", allow_col3);
				}
				else
				{
					// grid_row.toggle_editable("length", false);
					// grid_row.toggle_editable("width", false);
					// grid_row.toggle_editable("height", false);
				}
			}
			
			frappe.model.set_value(d.doctype, d.name, "length", length);
			frappe.model.set_value(d.doctype, d.name, "height", height);
			frappe.model.set_value(d.doctype, d.name, "width", width);
			frappe.model.set_value(d.doctype, d.name, "requom", requom);
			
			
			
			if(d.bb_item){
				if(build){
					cur_frm.trigger("build_bom");
				}	
			}
				

		}
	})
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
				d.conversion_factor = r.message.conversion_factor || 1.0;
				d.stock_qty = d.qty * d.conversion_factor;
				
				d.rate = d.stock_rate * d.conversion_factor;
				refresh_field("rate", d.name, d.parentfield);
				refresh_field("conversion_factor", d.name, d.parentfield);
				refresh_field("stock_qty", d.name, d.parentfield);
				erpnext.bom.update_cost(cur_frm.doc);

			}
		});
	}
};


cur_frm.cscript.stock_rate = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];

	if(d.conversion_factor && d.stock_rate) {
		d.rate = d.stock_rate * d.conversion_factor;
		refresh_field("rate", d.name, d.parentfield);
		erpnext.bom.update_cost(cur_frm.doc);
	}
};

frappe.tour['BOM'] = [
	{
		fieldname: "item",
		title: "Item",
		description: __(
			"Select the Item to be manufactured. The Item name, UoM, Company, and Currency will be fetched automatically."
		),
	},
	{
		fieldname: "quantity",
		title: "Quantity",
		description: __(
			"Enter the quantity of the Item that will be manufactured from this Bill of Materials."
		),
	},
	{
		fieldname: "with_operations",
		title: "With Operations",
		description: __("To add Operations tick the 'With Operations' checkbox."),
	},
	{
		fieldname: "items",
		title: "Raw Materials",
		description: __("Select the raw materials (Items) required to manufacture the Item"),
	},
];

frappe.ui.form.on("BOM Scrap Item", {
	item_code(frm, cdt, cdn) {
		const { item_code } = locals[cdt][cdn];
	},
});

function trigger_process_loss_qty_prompt(frm, cdt, cdn, item_code) {
	frappe.prompt(
		{
			fieldname: "percent",
			fieldtype: "Percent",
			label: __("% Finished Item Quantity"),
			description:
				__("Set quantity of process loss item:") +
				` ${item_code} ` +
				__("as a percentage of finished item quantity"),
		},
		(data) => {
			const row = locals[cdt][cdn];
			row.stock_qty = (frm.doc.quantity * data.percent) / 100;
			row.qty = row.stock_qty / (row.conversion_factor || 1);
			refresh_field("scrap_items");
		},
		__("Set Process Loss Item Quantity"),
		__("Set Quantity")
	);
}
