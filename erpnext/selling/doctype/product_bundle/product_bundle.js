// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
{% include 'erpnext/selling/sales_common.js' %}

frappe.ui.form.on("Product Bundle", {
	setup: function(frm) {
		frm.set_query("bom_no", "items", function(doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: {
					'currency': doc.currency,
					'company': doc.company,
					'item': d.item_code,
					'is_active': 1,
					'docstatus': 1
				}
			};
		});
	},
	refresh: function(frm) {
					frm.add_custom_button(__('Any Document'),
				function() {
					frm.trigger('get_items_from');
					
				}, __("Get items from"), "btn-default");
	},
	onload: function(frm) {
		// if (!frm.doc.posting_date){
			// frm.set_value('posting_date', frappe.datetime.get_today())
		// }
		frm.set_query('project', function(doc, cdt, cdn) {
			return {
				// query: "erpnext.controllers.queries.get_project_name",
				filters: {
					// 'customer': doc.customer,
					'company':doc.company,
					'status':'Open'
				}
			}
		});
	},

	get_items_from:function (frm) {
		var me=this;
		
		var doc_options = ['Delivery Note','Purchase Order','Purchase Receipt','Product Collection','Sales Order',
		'Sales Invoice','Quotation'];
		
		var dialog = new frappe.ui.Dialog({
			title: __("Get Items From Document"),
			fields: [
				{fieldname:'clear_items', fieldtype:'Check', label: __('Clear Previous Items'),default:1},
				{fieldname:'sec_1', fieldtype:'Section Break'},
				{fieldname:'doc_type', fieldtype:'Link', options:"DocType", label: __('Type'),"reqd": 1 },
				{fieldname:'col_1', fieldtype:'Column Break'},
				{fieldname:'doc_name', fieldtype:'Dynamic Link', options: 'doc_type', label: __('Name'),"reqd": 1 },
				// {fieldname:'qty', fieldtype:'float', label: __('Quantity'),default:1},
			]
		});
		
		
		dialog.fields_dict["doc_name"].get_query = function(){
			return {
				filters: [
						['docstatus', '<', '2'],
						// ['status', '!=', 'Closed'],
						// ['company', '=', frm.doc.company],
					]
					
				
			};
		};
		
		dialog.set_primary_action(__("Get Items"), function() {
		
		var filters = dialog.get_values();

		frappe.call({
			method:'erpnext.controllers.queries.get_items_from',
			args:{
				doc_type: filters.doc_type,
				doc_name: filters.doc_name
			},
			// freeze: true,
			// freeze_message: __("Getting Items..."),
			callback:function (r) {
			

				if(filters.clear_items === 1)
					frm.doc.items = [];
				
				var row_info = {};
				var row_start = frm.doc.items.length;
				
				
				for (var i=0; i< r.message.length; i++) {
					var row = frm.add_child("items");
					row.item_code = r.message[i].item_code;
					var row_index = row_start + i;
					row_info[row_index] = r.message[i];
					row.qty = r.message[i].qty;
					row.description = r.message[i].description;
					row.uom = r.message[i].uom;
					row.rate = r.message[i].rate;
					cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
					
				}
				
				dialog.hide();
				frappe.show_progress(__("Getting Items.."),0);

				//code before the pause
				setTimeout(function(){
					for(var row_index in row_info)
					{
						var row = cur_frm.doc.items[row_index];
						var data = row_info[row_index];

						for (var key in data) {
							if(frappe.meta.has_field(row.doctype, key))
							{
								row[key] = data[key];
							}
					
						}
					}
					
					cur_frm.refresh_field('items');
					calculate_totals(frm);
					cur_frm.dirty();
					frappe.show_progress(__("Getting Items.."),100);

				}, 1000);

				
				
				
			}
		})
		});
		dialog.show();
	},
});


frappe.ui.form.on("Product Bundle Item", {
	qty: function(frm, cdt, cdn) {
		let item = frappe.get_doc(cdt, cdn);
		frm.trigger("conversion_factor");
		calculate_totals(cur_frm);
	},
	rate: function(frm, cdt, cdn) {
		// let item = frappe.get_doc(cdt, cdn);
		calculate_totals(cur_frm);
	},
	conversion_factor: function(frm, cdt, cdn) {
		if(frappe.meta.get_docfield(cdt, "stock_qty", cdn)) {
			var item = frappe.get_doc(cdt, cdn);
			frappe.model.round_floats_in(item, ["qty", "conversion_factor"]);
			item.stock_qty = flt(item.qty * item.conversion_factor, precision("stock_qty", item));
			// item.total_weight = flt(item.stock_qty * item.weight_per_unit);
			refresh_field("stock_qty", item.name, item.parentfield);
			// refresh_field("total_weight", item.name, item.parentfield);
			// this.toggle_conversion_factor(item);
			// this.calculate_net_weight();
			// if (!dont_fetch_price_list_rate &&
				// frappe.meta.has_field(doc.doctype, "price_list_currency")) {
				// this.apply_price_list(item, true);
			// }
		}
	},

/* 	toggle_conversion_factor: function(item) {
		// toggle read only property for conversion factor field if the uom and stock uom are same
		if(this.frm.get_field('items').grid.fields_map.conversion_factor) {
			this.frm.fields_dict.items.grid.toggle_enable("conversion_factor",
				((item.uom != item.stock_uom) && !frappe.meta.get_docfield(cur_frm.fields_dict.items.grid.doctype, "conversion_factor").read_only)? true: false);
		}

	}, */


	
	uom: function(frm, cdt, cdn) {
		var me = cur_frm.parent;
		var item = frappe.get_doc(cdt, cdn);
		if(item.item_code && item.uom) {
			return frappe.call({
				method: "erpnext.stock.get_item_details.get_conversion_factor",
				child: item,
				args: {
					item_code: item.item_code,
					uom: item.uom
				},
				callback: function(r) {
					if(!r.exc) {
						frm.trigger("conversion_factor");	
					}
				}
			});
		}
	},
	item_code: function(frm, cdt, cdn) {
		var me = cur_frm.parent;
		var item = locals[cdt][cdn];
		let args = null;
		if(item.item_code) {
			args = {
				'item_code': item.item_code,
				'currency': me.frm.doc.currency,
				'conversion_rate': me.frm.doc.conversion_rate,
				'price_list': me.frm.doc.selling_price_list || me.frm.doc.buying_price_list,
				'price_list_currency': me.frm.doc.price_list_currency,
				'plc_conversion_rate': me.frm.doc.plc_conversion_rate,
				'company': me.frm.doc.company,
				'order_type': 'selling',
				// 'transaction_date': me.frm.doc.transaction_date || me.frm.doc.posting_date,
				'transaction_date': '',
				'ignore_pricing_rule': 1,
				'doctype': 'Sales Order',
				'project': item.project || me.frm.doc.project,
				'qty': item.qty || 1,
				'stock_qty': item.stock_qty,
				'conversion_factor': item.conversion_factor,
				'uom' : item.uom,
				'stock_uom': item.stock_uom,
			};
			return frappe.call({
				method: "erpnext.stock.get_item_details.get_item_details",
				args: {args: args},
				callback: function(r) {
					if(r.message) {
						frappe.model.set_value(cdt, cdn, "item_name", r.message.item_name);
						frappe.model.set_value(cdt, cdn, "description", r.message.item_name);
						frappe.model.set_value(cdt, cdn, "stock_uom", r.message.stock_uom);
						frappe.model.set_value(cdt, cdn, "uom", r.message.uom);
						frappe.model.set_value(cdt, cdn, "conversion_factor", r.message.conversion_factor);
						frappe.model.set_value(cdt, cdn, "price_list_rate", r.message.price_list_rate);
						frappe.model.set_value(cdt, cdn, "qty", r.message.qty);
						frappe.model.set_value(cdt, cdn, "rate", r.message.price_list_rate);
						frappe.model.set_value(cdt, cdn, "amount", r.message.qty * r.message.price_list_rate);
						calculate_totals(cur_frm);

					}
				}
			});
		}
	}
});



var calculate_totals = function(frm)
{
	var total_qty = 0;
	var total = 0;
	for(var d in frm.doc.items)
	{
		frm.doc.items[d].amount = frm.doc.items[d].qty * frm.doc.items[d].rate
		total += frm.doc.items[d].amount;
		total_qty += frm.doc.items[d].qty;
		
	}
	
	frm.set_value('total_qty',total_qty);
	frm.set_value('total',total);
	frm.refresh_fields();

}




cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	cur_frm.toggle_enable('new_item_code', doc.__islocal);
}

cur_frm.fields_dict.new_item_code.get_query = function() {
	return{
		query: "erpnext.selling.doctype.product_bundle.product_bundle.get_new_item_code"
	}
}
cur_frm.fields_dict.new_item_code.query_description = __('Please select Item where "Is Stock Item" is "No" and "Is Sales Item" is "Yes" and there is no other Product Bundle');


/* erpnext.selling.ProductBundleController = erpnext.selling.SellingController.extend({
	onload: function(doc, dt, dn) {
		this._super();
	},
});

$.extend(cur_frm.cscript, new erpnext.selling.ProductBundleController({frm: cur_frm})); */