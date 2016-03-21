// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt


cur_frm.cscript.tax_table = "Sales Taxes and Charges";
{% include 'accounts/doctype/sales_taxes_and_charges_template/sales_taxes_and_charges_template.js' %}

frappe.provide("erpnext.selling");
frappe.require("assets/erpnext/js/controllers/transaction.js");

cur_frm.email_field = "contact_email";

erpnext.selling.SellingController = erpnext.TransactionController.extend({
	validate:function(){
		this._super();		
		this.calculate_headers();
	},
	
	onload: function() {
		this._super();
		this.setup_queries();
	},

	setup_queries: function() {
		var me = this;

		this.frm.add_fetch("sales_partner", "commission_rate", "commission_rate");

		$.each([["customer_address", "customer_filter"],
			["shipping_address_name", "customer_filter"],
			["contact_person", "customer_filter"],
			["customer", "customer"],
			["lead", "lead"]],
			function(i, opts) {
				if(me.frm.fields_dict[opts[0]])
					me.frm.set_query(opts[0], erpnext.queries[opts[1]]);
			});

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

		if(this.frm.fields_dict["items"].grid.get_field('batch_no')) {
			this.frm.set_query("batch_no", "items", function(doc, cdt, cdn) {
				var item = frappe.get_doc(cdt, cdn);
				if(!item.item_code) {
					frappe.throw(__("Please enter Item Code to get batch no"));
				} else {
					filters = {
						'item_code': item.item_code,
						'posting_date': me.frm.doc.posting_date || nowdate(),
					}
					if(item.warehouse) filters["warehouse"] = item.warehouse

					return {
						query : "erpnext.controllers.queries.get_batch_no",
						filters: filters
					}
				}
			});
		}
	},

	refresh: function() {
		this._super();
		this.frm.toggle_display("customer_name",
			(this.frm.doc.customer_name && this.frm.doc.customer_name!==this.frm.doc.customer));
		if(this.frm.fields_dict.packed_items) {
			var packing_list_exists = (this.frm.doc.packed_items || []).length;
			this.frm.toggle_display("packing_list", packing_list_exists ? true : false);
		}
		this.toggle_editable_price_list_rate();
		
		if (cur_frm.doc.items)
			this.refresh_headers();
		
		cur_frm.add_custom_button(__("Quotation Report"), function() {
						window.location.href = 'desk#query-report/Quotation%20Report';
					});
		
		cur_frm.add_custom_button(__("Project Item Report"), function() {
						window.location.href = 'desk#query-report/Item%20Summary%20By%20Project';
					});
		if (this.frm.doc.docstatus===0) {

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
									var d = frappe.model.add_child(cur_frm.doc, "Quotation Item", "items");
										d.item_code = item.item_code;
										d.qty = item.qty;
										d.page_break = item.page_break;
										console.log(d);
										cur_frm.script_manager.trigger("item_code", d.doctype, d.name);
										
									});
								me.calculate_headers();
								me.refresh_headers();
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
			}
		
		
	},

	customer: function() {
		var me = this;
		erpnext.utils.get_party_details(this.frm, null, null, function(){me.apply_pricing_rule()});
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
				msgprint(msg);
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
		this.batch_no(doc, cdt, cdn);
		var item = frappe.get_doc(cdt, cdn);
		if(item.item_code && item.warehouse) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_available_qty",
				child: item,
				args: {
					item_code: item.item_code,
					warehouse: item.warehouse,
				},
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
				msgprint(msg);
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

	shipping_rule: function() {
		var me = this;
		if(this.frm.doc.shipping_rule) {
			return this.frm.call({
				doc: this.frm.doc,
				method: "apply_shipping_rule",
				callback: function(r) {
					if(!r.exc) {
						me.calculate_taxes_and_totals();
					}
				}
			})
		}
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

			if (inList(['Delivery Note', 'Sales Invoice'], doc.doctype)) {
				help_msg = "<div class='alert alert-warning'>" +
					__("For 'Product Bundle' items, Warehouse, Serial No and Batch No will be considered from the 'Packing List' table. If Warehouse and Batch No are same for all packing items for any 'Product Bundle' item, those values can be entered in the main Item table, values will be copied to 'Packing List' table.")+
				"</div>";
				frappe.meta.get_docfield(doc.doctype, 'product_bundle_help', doc.name).options = help_msg;
			}
		} else {
			$(cur_frm.fields_dict.packing_list.row.wrapper).toggle(false);
			if (inList(['Delivery Note', 'Sales Invoice'], doc.doctype)) {
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
					console.log(r.message);
					frappe.set_route("Form", r.message.doctype, r.message.name);
				}
			}
		})
	},
	
	
	refresh_headers : function(){
		var items = cur_frm.doc.items;
		if (!items){
			return;
		}
		$.each(items, function(i, d) {
			var data_row = cur_frm.page.body.find('[data-fieldname="items"] [data-idx="'+ d.idx +'"] .data-row');
			data_row.removeClass("highlight-custom");
			if (d.item_group == "Header1"){		
				data_row.addClass("highlight-custom");
			} else if (d.item_group == "Header2"){
				data_row.addClass("highlight-custom");					
			}
		});
		refresh_field("items");
		
	},
	
	calculate_headers : function(){
		console.log("calcing headers")
		
		/* var me = this;
		frappe.call({
			method:"erpnext.selling.doctype.quotation.quotation.calculate_headers",
			args: {
				"doc": cur_frm.doc,
				"items": cur_frm.doc.items
			},
			callback: function(r) {
				me.refresh_headers();
			}
		})
		
		return; */
		
		
		var items = cur_frm.doc.items;
		if (!items){
			return;
		}
		$.each(items, function(i, d) {
	
			if (d.item_group == "Header1"){

				var sum = 0;

				for (var j = i+1; j < items.length; ++j) {
					var testitem = items[j];
					if (testitem.item_group == d.item_group)
						break;
					else if (testitem.item_group == "Header2") {
						break;
					} else {
						sum = sum + testitem.amount;
					} 
				}
				d.qty = 0;
				d.rate = sum;
				d.amount = 0;
				d.page_break = 1;

				if (d.idx == 1)
					d.page_break = 0;
			} else if (d.item_group == "Header2"){
				var sum = 0;

				for (var j = i+1; j < items.length; ++j) {
					var testitem = items[j];
					if (testitem.item_group == d.item_group)
						break;
					else if (testitem.item_group == "Header1") {
						break;
					} else {
						sum = sum + testitem.amount;
					} 
				}
				d.qty = 0;
				d.rate = sum;
				d.amount = 0;
				d.page_break = 0
			
			}
		});
	}
});

frappe.ui.form.on(cur_frm.doctype,"project", function(frm) {
	if(in_list(["Delivery Note", "Sales Invoice"], frm.doc.doctype)) {
		frappe.call({
			method:'erpnext.projects.doctype.project.project.get_cost_center_name' ,
			args: {	project: frm.doc.project	},
			callback: function(r, rt) {
				if(!r.exc) {
					$.each(frm.doc["items"] || [], function(i, row) {
						frappe.model.set_value(row.doctype, row.name, "cost_center", r.message);
						msgprint(__("Cost Center For Item with Item Code '"+row.item_name+"' has been Changed to "+ r.message));
					})
				}
			}
		})
	}
})

// Table modified
// ------------------------------------------------------------------------
frappe.ui.form.on(cur_frm.doctype + " Item", "Quotation Item_hide", function(frm,dt,dn){
	//frm.cscript.calculate_headers();
	//frm.cscript.refresh_headers();
	//cur_frm.refresh();
	//console.log("hide");
})

frappe.ui.form.on(cur_frm.doctype + " Item", "items_refresh", function(frm,dt,dn){
	//frm.cscript.calculate_headers();
	//frm.cscript.refresh_headers();
	//cur_frm.refresh();
	//console.log("refresh");
})

frappe.ui.form.on(cur_frm.doctype + " Item", "items_remove", function(frm,dt,dn){
	//frm.cscript.calculate_headers();
	//frm.cscript.refresh_headers();
	cur_frm.refresh();
})

frappe.ui.form.on(cur_frm.doctype + " Item", "items_add", function(frm,dt,dn){
	//frm.cscript.calculate_headers();
	//frm.cscript.refresh_headers();
	//cur_frm.refresh;
})

frappe.ui.form.on(cur_frm.doctype + " Item", "qty", function(frm,dt,dn){
	//frm.cscript.calculate_headers();
})
