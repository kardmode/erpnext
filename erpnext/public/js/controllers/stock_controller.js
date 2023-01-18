// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.stock");

erpnext.stock.StockController = frappe.ui.form.Controller.extend({
	onload: function() {
		// warehouse query if company
		if (this.frm.fields_dict.company) {
			this.setup_warehouse_query();
		}
	},

	setup_warehouse_query: function() {
		var me = this;
		erpnext.queries.setup_queries(this.frm, "Warehouse", function() {
			return erpnext.queries.warehouse(me.frm.doc);
		});
	},

	setup_posting_date_time_check: function() {
		// make posting date default and read only unless explictly checked
		frappe.ui.form.on(this.frm.doctype, 'set_posting_date_and_time_read_only', function(frm) {
			if(frm.doc.docstatus == 0 && frm.doc.set_posting_time) {
				frm.set_df_property('posting_date', 'read_only', 0);
				frm.set_df_property('posting_time', 'read_only', 0);
			} else {
				frm.set_df_property('posting_date', 'read_only', 1);
				frm.set_df_property('posting_time', 'read_only', 1);
			}
		})

		frappe.ui.form.on(this.frm.doctype, 'set_posting_time', function(frm) {
			frm.trigger('set_posting_date_and_time_read_only');
		});

		frappe.ui.form.on(this.frm.doctype, 'refresh', function(frm) {
			// set default posting date / time
			if(frm.doc.docstatus==0) {
				if(!frm.doc.posting_date) {
					frm.set_value('posting_date', frappe.datetime.nowdate());
				}
				if(!frm.doc.posting_time) {
					frm.set_value('posting_time', frappe.datetime.now_time());
				}
				frm.trigger('set_posting_date_and_time_read_only');
			}
		});
	},

	show_stock_ledger: function() {
		var me = this;
		if(this.frm.doc.docstatus===1) {
			cur_frm.add_custom_button(__("Stock Ledger"), function() {
				frappe.route_options = {
					voucher_no: me.frm.doc.name,
					from_date: me.frm.doc.posting_date,
					to_date: me.frm.doc.posting_date,
					company: me.frm.doc.company
				};
				frappe.set_route("query-report", "Stock Ledger");
			}, __("View"));
		}

	},

	show_general_ledger: function() {
		var me = this;
		if(this.frm.doc.docstatus===1) {
			cur_frm.add_custom_button(__('Accounting Ledger'), function() {
				frappe.route_options = {
					voucher_no: me.frm.doc.name,
					from_date: me.frm.doc.posting_date,
					to_date: me.frm.doc.posting_date,
					company: me.frm.doc.company,
					group_by: "Group by Voucher (Consolidated)"
				};
				frappe.set_route("query-report", "General Ledger");
			}, __("View"));
		}
	},
	mrp_setup_custom_buttons:function(){
		if (this.frm.doc.docstatus==0) {
			// cur_frm.add_custom_button(__('CSV'),
				// function() {
					// cur_frm.trigger('get_items_from_csv');				
				// }, __("Get items from"), "btn-default");
	
			
			cur_frm.add_custom_button(__('Any Document'),
				function() {
					cur_frm.trigger('get_items_from');
					
				}, __("Get items from"), "btn-default");
			
				
			cur_frm.add_custom_button(__('Items Quantity'),
				function() {
					cur_frm.trigger('multiply_items');
				}, __("Modify"), "btn-default");
				
			cur_frm.add_custom_button(__('Items Rate'),
				function() {
					cur_frm.trigger('multiply_rate');
				}, __("Modify"), "btn-default");
			
			cur_frm.add_custom_button(__('Pro Rata'),
				function() {
					cur_frm.trigger('pro_rata');
				}, __("Modify"), "btn-default");
			
		}
	},
	get_items_from_csv:function () {
		var me = this;

		var dialog = new frappe.ui.Dialog({
			title: "Add items from CSV",
			fields: [
				{"fieldtype": "HTML", "label": __(""), "fieldname": "import_html",
					"reqd": 1 },
				{"fieldtype": "HTML", "label": __(""), "fieldname": "import_log",
					"reqd": 1 },
				{"fieldtype": "Check", "label": __("Keep Previous Entries"), "fieldname": "keep_previous"},
				{"fieldtype": "Button", "label": __("Update"), "fieldname": "update"},
			]
		});

		var $wrapper = $(dialog.fields_dict.import_html.wrapper).empty();

		// upload
		frappe.upload.make({
			parent: $wrapper,
			args: {
				method: 'erpnext.controllers.queries.get_items_from_csv',
			},
			btn: $(dialog.fields_dict.update.wrapper),
			callback: function(attachment, r) {
				var $log_wrapper = $(dialog.fields_dict.import_log.wrapper).empty();
				var $keep_previous = $(dialog.fields_dict.keep_previous.wrapper).find('input[type="checkbox"]');
				
				var items = r.message.items;
				var messages = r.message.messages;
				var error = r.message.error;
				if(!r.messages) r.messages = [];

				r.messages = $.map(messages, function(v) {
					return v;
				});
				
				if (error){
					r.messages = ["<h4 style='color:red'>"+__("Import Failed")+"</h4>"]
						.concat(r.messages)

				} else {
					r.messages = ["<h4 style='color:green'>"+__("Import Succeeded")+"</h4>"]
						.concat(r.messages)
					
					if(!$keep_previous.is(":checked")){	
						 cur_frm.doc.items = [];
					}
					$.each(items, function(i, item) {
						var d = frappe.model.add_child(cur_frm.doc, cur_frm.doctype + " Item", "items");
						d.item_code = item.item_code;
						d.qty = item.qty;
						d.page_break = item.page_break;
						cur_frm.script_manager.trigger("item_code", d.doctype, d.name);
							
					});
				
					cur_frm.refresh_field('items');
					//me.calculate_taxes_and_totals();

				}
				
				$.each(r.messages, function(i, v) {
					var $p = $('<p>').html(v).appendTo($log_wrapper);
					if(v.substr(0,5)=='Error') {
						$p.css('color', 'red');
					}else if(v.substr(0,6)=='Header') {
						$p.css('color', 'green');
					} else if(v.substr(0,7)=='Updated') {
						$p.css('color', 'green');
					}
				});
			},
			is_private: false
		});

		
		dialog.show();
		
	},
	get_items_from:function () {
		var me=this;
		
		var dialog = new frappe.ui.Dialog({
			title: __("Get Items From Document"),
			fields: [
				{fieldname:'clear_items', fieldtype:'Check', label: __('Clear Previous Items'),default:1},
				{fieldname:'include_bundled_items', fieldtype:'Check', label: __('Include Bundled Items'),default:0},
				{fieldname:'sec_1', fieldtype:'Section Break'},
				{fieldname:'doc_type', fieldtype:'Link', options:"DocType", label: __('Type'),"reqd": 1 },
				{fieldname:'col_1', fieldtype:'Column Break'},
				{fieldname:'doc_name', fieldtype:'Dynamic Link', options: 'doc_type', label: __('Name'),"reqd": 1 },
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
				doc_name: filters.doc_name,
				include_bundled_items: filters.include_bundled_items
			},
			// freeze: true,
			// freeze_message: __("Getting Items..."),
			callback:function (r) {
			

				if(filters.clear_items === 1)
					cur_frm.doc.items = [];
				
				var row_info = {};
				var row_start = cur_frm.doc.items.length;

				for (var i=0; i< r.message.length; i++) {
					var row = cur_frm.add_child("items");					
					row.item_code = r.message[i].item_code
					var row_index = row_start + i;
					row_info[row_index] = r.message[i];
					
					cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
				}
				dialog.hide();
				frappe.show_progress(__("Getting Items.."),0);

				//code before the pause
				setTimeout(function(){
					
					// var length = cur_frm.doc.items.length;
					
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
						
						// frappe.show_progress(__("Getting Items.."),row_index/length * 100);

						
					}
					
					cur_frm.refresh_field('items');
					//me.calculate_taxes_and_totals();
					cur_frm.dirty();
					frappe.show_progress(__("Getting Items.."),100);

				}, 1500);

				
				
				
			}
		})
		});
		dialog.show();
	},
	
	
	multiply_room:function (frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Multiply Room"),
			fields: [
				// {fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				// {fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'qty', fieldtype:'Int', label: __('Quantity'),default:'1'},
			]
		});
		dialog.set_primary_action(__("Change"), function() {
		
			var filters = dialog.get_values();

			var qty =1;
			var filter_qty = 1;
			if ( dialog.get_value('qty') > 0)
				filter_qty = dialog.get_value('qty');
			
			original_qty = cur_frm.doc.room_qty;
			qty = flt(filter_qty)/flt(original_qty);
			cur_frm.set_value("room_qty",filter_qty);
			
			var items = cur_frm.doc.items;
			$.each(items, function(i, item) {
				item.qty = flt(item.qty) * flt(qty);
				cur_frm.script_manager.trigger("item_qty", item.doctype, item.name);

			});
			cur_frm.refresh_field('items');
					//me.calculate_taxes_and_totals();
			cur_frm.dirty();
			dialog.hide();
		});
		dialog.show();
	},
	
	multiply_items:function (frm) {
		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("Multiply All Items"),
			fields: [
				//{fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				//{fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'qty', fieldtype:'Float', label: __('Quantity'),default:'1'},
			]
		});
		dialog.set_primary_action(__("Multiply"), function() {
		
			var filters = dialog.get_values();
			var qty =1;
			var filter_qty = 1;
			if ( dialog.get_value('qty') > 0)
				filter_qty = dialog.get_value('qty');
			
			original_qty = cur_frm.doc.room_qty;
			qty = filter_qty;

			//cur_frm.set_value("room_qty",qty);
			
			var items = cur_frm.doc.items;

			$.each(items, function(i, item) {
				item.qty = flt(item.qty) * flt(qty);
				cur_frm.script_manager.trigger("item_code", item.doctype, item.name);

			});
			
			cur_frm.refresh_field('items');
			//me.calculate_taxes_and_totals();
			cur_frm.dirty();
			dialog.hide();
		});
		dialog.show();
	},
	
	multiply_rate:function (frm) {
		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("Multiply All Item Rate"),
			fields: [
				//{fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				//{fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'qty', fieldtype:'Float', label: __('Percent'),default:'100'},
			]
		});
		dialog.set_primary_action(__("Multiply"), function() {
		
			var filters = dialog.get_values();
			var percent = 100;
			if ( dialog.get_value('qty') > 0)
				percent = dialog.get_value('qty');
			
			
			var items = cur_frm.doc.items;

			$.each(items, function(i, item) {
				item.rate = flt(item.rate) * flt(percent)/100;
				//cur_frm.script_manager.trigger("item_code", item.doctype, item.name);

			});
			
			cur_frm.refresh_field('items');
			//me.calculate_taxes_and_totals();
			cur_frm.dirty();

			dialog.hide();
		});
		dialog.show();
	},

	pro_rata:function (frm) {
		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("Pro Rata Item Rate"),
			fields: [
				//{fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				{fieldname:'target', fieldtype:'Float', label: __('Total Required'),default:me.frm.doc.grand_total},
				//{fieldname:'base_variable', fieldtype:'Section Break'},
				//{fieldname:'qty', fieldtype:'Float', label: __('Percent'),default:'100'},
			]
		});
		dialog.set_primary_action(__("Rata"), function() {
		
			var filters = dialog.get_values();
			
			var target = original_total = me.frm.doc.grand_total;
			if ( dialog.get_value('target') > 0)
				target = dialog.get_value('target');
			
			var percent_change = (target-original_total)/original_total
			
			var items = cur_frm.doc.items;
			$.each(items, function(i, item) {
				var new_amount = item.amount*(1+percent_change);
				item.rate = flt(new_amount/item.qty);
			});
			
			cur_frm.refresh_field('items');
			//me.calculate_taxes_and_totals();
			cur_frm.dirty();

			dialog.hide();
		});
		dialog.show();
	},
});
