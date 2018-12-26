// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt


cur_frm.cscript.tax_table = "Sales Taxes and Charges";
{% include 'erpnext/accounts/doctype/sales_taxes_and_charges_template/sales_taxes_and_charges_template.js' %}


cur_frm.email_field = "contact_email";

frappe.provide("erpnext.selling");
erpnext.selling.SellingController = erpnext.TransactionController.extend({

	setup: function() {
		this._super();
	},

	onload: function() {
		this._super();
		this.setup_queries();
		this.frm.set_query('shipping_rule', function() {
			return {
				filters: {
					"shipping_rule_type": "Selling"
				}
			};
		});
	},

	setup_queries: function() {
		var me = this;

		this.frm.add_fetch("sales_partner", "commission_rate", "commission_rate");

		$.each([["customer", "customer"],
			["lead", "lead"]],
			function(i, opts) {
				if(me.frm.fields_dict[opts[0]])
					me.frm.set_query(opts[0], erpnext.queries[opts[1]]);
			});

		me.frm.set_query('contact_person', erpnext.queries.contact_query);
		//me.frm.set_query('customer_address', erpnext.queries.address_query);
		//me.frm.set_query('shipping_address_name', erpnext.queries.address_query);

		if(this.frm.fields_dict.taxes_and_charges) {
			this.frm.set_query("taxes_and_charges", function() {
				return {
					filters: [
						['Sales Taxes and Charges Template', 'company', '=', me.frm.doc.company],
						['Sales Taxes and Charges Template', 'docstatus', '!=', 2]
					]
				}
			});
		}

		if(this.frm.fields_dict.selling_price_list) {
			this.frm.set_query("selling_price_list", function() {
				return { filters: { selling: 1 } };
			});
		}

		if(!this.frm.fields_dict["items"]) {
			return;
		}

		if(this.frm.fields_dict["items"].grid.get_field('item_code')) {
			this.frm.set_query("item_code", "items", function() {

				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {'is_sales_item': 1}
				}
			});
		}

		if(this.frm.fields_dict["packed_items"] &&
			this.frm.fields_dict["packed_items"].grid.get_field('batch_no')) {
			this.frm.set_query("batch_no", "packed_items", function(doc, cdt, cdn) {
				return me.set_query_for_batch(doc, cdt, cdn)
			});
		}
		
		this.frm.set_query('warehouse', 'items', function(doc, cdt, cdn) {
			
			var item = locals[cdt][cdn];
			if(!item.item_code) {
				
			} else {
				return {
					query : "erpnext.stock.doctype.stock_entry.stock_entry.get_warehouses_with_stock",
					filters: {"item_code":item.item_code,"company":doc.company}
				}
			}
		});
	},

	refresh: function() {
		this._super();

		frappe.dynamic_link = {doc: this.frm.doc, fieldname: 'customer', doctype: 'Customer'}

		this.frm.toggle_display("customer_name",
			(this.frm.doc.customer_name && this.frm.doc.customer_name!==this.frm.doc.customer));
		if(this.frm.fields_dict.packed_items) {
			var packing_list_exists = (this.frm.doc.packed_items || []).length;
			this.frm.toggle_display("packing_list", packing_list_exists ? true : false);
		}
		this.toggle_editable_price_list_rate();
		

		
		if (this.frm.doc.docstatus==0) {
			cur_frm.add_custom_button(__('CSV'),
			function() {
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
						method: 'erpnext.selling.doctype.quotation.quotation.upload',
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
									console.log(d);
									cur_frm.script_manager.trigger("item_code", d.doctype, d.name);
									
								});
						
							cur_frm.refresh_field('items');
							me.calculate_taxes_and_totals();

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

				
				
			}, __("Get items from"), "btn-default");
	
			
			cur_frm.add_custom_button(__('Collection'),
				function() {
					/* erpnext.utils.map_current_doc({
						method: "erpnext.selling.doctype.quotation.quotation.make_quotation",
						source_doctype: "Product Bundle",
						get_query_filters: {
						}
					}) */
					cur_frm.trigger('add_bundle');
					
				}, __("Get items from"), "btn-default");
			
			cur_frm.add_custom_button(__('Room Quantity'),
				function() {
					/* erpnext.utils.map_current_doc({
						method: "erpnext.selling.doctype.quotation.quotation.make_quotation",
						source_doctype: "Product Bundle",
						get_query_filters: {
						}
					}) */
					cur_frm.trigger('multiply_room');
					
				}, __("Modify"), "btn-default");
				
			cur_frm.add_custom_button(__('Items Quantity'),
				function() {
					/* erpnext.utils.map_current_doc({
						method: "erpnext.selling.doctype.quotation.quotation.make_quotation",
						source_doctype: "Product Bundle",
						get_query_filters: {
						}
					}) */
					cur_frm.trigger('multiply_items');
					
				}, __("Modify"), "btn-default");
			cur_frm.add_custom_button(__('Items Rate'),
				function() {

					cur_frm.trigger('multiply_rate');
					
				}, __("Modify"), "btn-default");
			
			cur_frm.add_custom_button(__('Pro Bata'),
				function() {

					cur_frm.trigger('pro_rata');
					
				}, __("Modify"), "btn-default");
			
		}
		
	},
	
	add_bundle:function (frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Get Items From Collection"),
			fields: [
				{fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				{fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'qty', fieldtype:'Int', label: __('Quantity'),default:1},
			]
		});
		dialog.set_primary_action(__("Add"), function() {
		
		var filters = dialog.get_values();
/* 		if ('base' in filters) {
			delete filters.base
		} */
		frappe.call({
			method:'erpnext.selling.doctype.quotation.quotation.get_product_bundle_items',
			args:{
				item_code: filters.bundle
			},
			callback:function (r) {
				//console.log(r);
				
				var qty =1;
				if ( dialog.get_value('qty') >0)
					qty = dialog.get_value('qty');
				
				cur_frm.set_value("room_qty",qty);
					
				for (var i=0; i< r.message.length; i++) {
					var row = frappe.model.add_child(cur_frm.doc, cur_frm.fields_dict.items.df.options, cur_frm.fields_dict.items.df.fieldname);
					row.item_code = r.message[i].item_code;
					
					

					row.qty = r.message[i].qty * qty;
					cur_frm.script_manager.trigger("item_code", row.doctype, row.name);


				}
				cur_frm.refresh_field('items');
					me.calculate_taxes_and_totals();
cur_frm.dirty();
				dialog.hide();
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
					me.calculate_taxes_and_totals();
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
					me.calculate_taxes_and_totals();
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
			me.calculate_taxes_and_totals();
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
		dialog.set_primary_action(__("Bata"), function() {
		
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
			me.calculate_taxes_and_totals();
			cur_frm.dirty();

			dialog.hide();
		});
		dialog.show();
	},
	
	customer: function() {
		var me = this;
		erpnext.utils.get_party_details(this.frm, null, null,
			function(){ me.apply_pricing_rule() });
	},

	customer_address: function() {
		erpnext.utils.get_address_display(this.frm, "customer_address");
	},

	shipping_address_name: function() {
		erpnext.utils.get_address_display(this.frm, "shipping_address_name", "shipping_address");
	},

	sales_partner: function() {
		this.apply_pricing_rule();
	},

	campaign: function() {
		this.apply_pricing_rule();
	},

	selling_price_list: function() {
		this.apply_price_list();
	},

	price_list_rate: function(doc, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		frappe.model.round_floats_in(item, ["price_list_rate", "discount_percentage"]);


		// check if child doctype is Sales Order Item/Qutation Item and calculate the rate
		if(in_list(["Quotation Item", "Sales Order Item", "Delivery Note Item", "Sales Invoice Item"]), cdt)
			this.apply_pricing_rule_on_item(item);
		else
			item.rate = flt(item.price_list_rate * (1 - item.discount_percentage / 100.0),
				precision("rate", item));

		this.calculate_taxes_and_totals();
	},

	discount_percentage: function(doc, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		if(!item.price_list_rate) {
			item.discount_percentage = 0.0;
		} else {
			this.price_list_rate(doc, cdt, cdn);
		}
	},

	commission_rate: function() {
		this.calculate_commission();
		refresh_field("total_commission");
	},

	total_commission: function() {
		if(this.frm.doc.base_net_total) {
			frappe.model.round_floats_in(this.frm.doc, ["base_net_total", "total_commission"]);

			if(this.frm.doc.base_net_total < this.frm.doc.total_commission) {
				var msg = (__("[Error]") + " " +
					__(frappe.meta.get_label(this.frm.doc.doctype, "total_commission",
						this.frm.doc.name)) + " > " +
					__(frappe.meta.get_label(this.frm.doc.doctype, "base_net_total", this.frm.doc.name)));
				frappe.msgprint(msg);
				throw msg;
			}

			this.frm.set_value("commission_rate",
				flt(this.frm.doc.total_commission * 100.0 / this.frm.doc.base_net_total));
		}
	},

	allocated_percentage: function(doc, cdt, cdn) {
		var sales_person = frappe.get_doc(cdt, cdn);

		if(sales_person.allocated_percentage) {
			sales_person.allocated_percentage = flt(sales_person.allocated_percentage,
				precision("allocated_percentage", sales_person));
			sales_person.allocated_amount = flt(this.frm.doc.base_net_total *
				sales_person.allocated_percentage / 100.0,
				precision("allocated_amount", sales_person));

			refresh_field(["allocated_percentage", "allocated_amount"], sales_person.name,
				sales_person.parentfield);
		}
	},

	warehouse: function(doc, cdt, cdn) {
		var me = this;
		var item = frappe.get_doc(cdt, cdn);

		if(item.item_code && item.warehouse) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_bin_details_and_serial_nos",
				child: item,
				args: {
					item_code: item.item_code,
					warehouse: item.warehouse,
					stock_qty: item.stock_qty,
					serial_no: item.serial_no || ""
				},
				callback:function(r){
					if (in_list(['Delivery Note', 'Sales Invoice'], doc.doctype)) {
					    me.set_batch_number(cdt, cdn);
						me.batch_no(doc, cdt, cdn);
					}
				}
			});
		}
	},

	toggle_editable_price_list_rate: function() {
		var df = frappe.meta.get_docfield(this.frm.doc.doctype + " Item", "price_list_rate", this.frm.doc.name);
		var editable_price_list_rate = cint(frappe.defaults.get_default("editable_price_list_rate"));

		if(df && editable_price_list_rate) {
			df.read_only = 0;
		}
	},

	calculate_commission: function() {
		if(this.frm.fields_dict.commission_rate) {
			if(this.frm.doc.commission_rate > 100) {
				var msg = __(frappe.meta.get_label(this.frm.doc.doctype, "commission_rate", this.frm.doc.name)) +
					" " + __("cannot be greater than 100");
				frappe.msgprint(msg);
				throw msg;
			}

			this.frm.doc.total_commission = flt(this.frm.doc.base_net_total * this.frm.doc.commission_rate / 100.0,
				precision("total_commission"));
		}
	},

	calculate_contribution: function() {
		var me = this;
		$.each(this.frm.doc.doctype.sales_team || [], function(i, sales_person) {
			frappe.model.round_floats_in(sales_person);
			if(sales_person.allocated_percentage) {
				sales_person.allocated_amount = flt(
					me.frm.doc.base_net_total * sales_person.allocated_percentage / 100.0,
					precision("allocated_amount", sales_person));
			}
		});
	},

	batch_no: function(doc, cdt, cdn) {
		var me = this;
		var item = frappe.get_doc(cdt, cdn);

		if(item.warehouse && item.item_code && item.batch_no) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_batch_qty",
				child: item,
				args: {
					"batch_no": item.batch_no,
					"warehouse": item.warehouse,
					"item_code": item.item_code
				},
				"fieldname": "actual_batch_qty"
			});
		}
	},

	set_dynamic_labels: function() {
		this._super();
		this.set_product_bundle_help(this.frm.doc);
	},

	set_product_bundle_help: function(doc) {
		if(!cur_frm.fields_dict.packing_list) return;
		if ((doc.packed_items || []).length) {
			$(cur_frm.fields_dict.packing_list.row.wrapper).toggle(true);

			if (in_list(['Delivery Note', 'Sales Invoice'], doc.doctype)) {
				var help_msg = "<div class='alert alert-warning'>" +
					__("For 'Product Bundle' items, Warehouse, Serial No and Batch No will be considered from the 'Packing List' table. If Warehouse and Batch No are same for all packing items for any 'Product Bundle' item, those values can be entered in the main Item table, values will be copied to 'Packing List' table.")+
				"</div>";
				frappe.meta.get_docfield(doc.doctype, 'product_bundle_help', doc.name).options = help_msg;
			}
		} else {
			$(cur_frm.fields_dict.packing_list.row.wrapper).toggle(false);
			if (in_list(['Delivery Note', 'Sales Invoice'], doc.doctype)) {
				frappe.meta.get_docfield(doc.doctype, 'product_bundle_help', doc.name).options = '';
			}
		}
		refresh_field('product_bundle_help');
	},

	make_payment_request: function() {
		frappe.call({
			method:"erpnext.accounts.doctype.payment_request.payment_request.make_payment_request",
			args: {
				"dt": cur_frm.doc.doctype,
				"dn": cur_frm.doc.name,
				"recipient_id": cur_frm.doc.contact_email
			},
			callback: function(r) {
				if(!r.exc){
					var doc = frappe.model.sync(r.message);

					frappe.set_route("Form", r.message.doctype, r.message.name);
				}
			}
		})
	},
	
	
	refresh_headers : function(){
		console.log("refresh headers")

		var items = cur_frm.doc.items;
		if (!items){
			return;
		}
		$.each(items, function(i, d) {
			var data_row = cur_frm.page.body.find('[data-fieldname="items"] [data-idx="'+ d.idx +'"]');
			data_row.removeClass("highlight-custom");
			
			if (d.item_group == "Header1"){
				d.page_break = 1;
				if(i==0)
					d.page_break = 0;				
				data_row.addClass("highlight-custom");
			} else if (d.item_group == "Header2"){
				d.page_break = 0;
				data_row.addClass("highlight-custom");					
			}
		});
		refresh_field("items");
		
	},
	
	
	calculate_headers : function(){
		console.log("calculating headers")
		return $c_obj(cur_frm.doc, 'calculate_headers','',function(r, rt) {
			cur_frm.refresh();
			cur_frm.dirty();
		});
	},

	margin_rate_or_amount: function(doc, cdt, cdn) {
		// calculated the revised total margin and rate on margin rate changes
		var item = locals[cdt][cdn];
		this.apply_pricing_rule_on_item(item)
		this.calculate_taxes_and_totals();
		cur_frm.refresh_fields();
	},

	margin_type: function(doc, cdt, cdn){
		// calculate the revised total margin and rate on margin type changes
		var item = locals[cdt][cdn];
		if(!item.margin_type) {
			frappe.model.set_value(cdt, cdn, "margin_rate_or_amount", 0);
		} else {
			this.apply_pricing_rule_on_item(item, doc,cdt, cdn)
			this.calculate_taxes_and_totals();
			cur_frm.refresh_fields();
		}
	},

	company_address: function() {
		var me = this;
		if(this.frm.doc.company_address) {
			frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {"address_dict": this.frm.doc.company_address },
				callback: function(r) {
					if(r.message) {
						me.frm.set_value("company_address_display", r.message)
					}
				}
			})
		} else {
			this.frm.set_value("company_address_display", "");
		}
	},

	conversion_factor: function(doc, cdt, cdn, dont_fetch_price_list_rate) {
	    this._super(doc, cdt, cdn, dont_fetch_price_list_rate);
		if(frappe.meta.get_docfield(cdt, "stock_qty", cdn)) {
			this.set_batch_number(cdt, cdn);
		}
	},

	qty: function(doc, cdt, cdn) {
	    this._super(doc, cdt, cdn);
		this.set_batch_number(cdt, cdn);
	},

	/* Determine appropriate batch number and set it in the form.
	* @param {string} cdt - Document Doctype
	* @param {string} cdn - Document name
	*/
	set_batch_number: function(cdt, cdn) {
		const doc = frappe.get_doc(cdt, cdn);
		if (doc && doc.has_batch_no) {
			this._set_batch_number(doc);
		}
	},

	_set_batch_number: function(doc) {
		return frappe.call({
			method: 'erpnext.stock.doctype.batch.batch.get_batch_no',
			args: {'item_code': doc.item_code, 'warehouse': doc.warehouse, 'qty': flt(doc.qty) * flt(doc.conversion_factor)},
			callback: function(r) {
				if(r.message) {
					frappe.model.set_value(doc.doctype, doc.name, 'batch_no', r.message);
				} else {
				    frappe.model.set_value(doc.doctype, doc.name, 'batch_no', r.message);
				}
			}
		});
	},
});

frappe.ui.form.on(cur_frm.doctype,"project", function(frm) {
	if(in_list(["Delivery Note", "Sales Invoice"], frm.doc.doctype)) {
		if(frm.doc.project) {
			frappe.call({
				method:'erpnext.projects.doctype.project.project.get_cost_center_name' ,
				args: {	project: frm.doc.project	},
				callback: function(r, rt) {
					if(!r.exc) {
						$.each(frm.doc["items"] || [], function(i, row) {
							if(r.message) {
								frappe.model.set_value(row.doctype, row.name, "cost_center", r.message);
								frappe.msgprint(__("Cost Center For Item with Item Code '"+row.item_name+"' has been Changed to "+ r.message));
							}
						})
					}
				}
			})
		}
	}
})

