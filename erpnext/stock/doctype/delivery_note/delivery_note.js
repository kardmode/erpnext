// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

{% include 'erpnext/selling/sales_common.js' %};

cur_frm.add_fetch('customer', 'tax_id', 'tax_id');

frappe.provide("erpnext.stock");
frappe.provide("erpnext.stock.delivery_note");

frappe.ui.form.on("Delivery Note", {
	setup: function(frm) {
		frm.custom_make_buttons = {
			'Packing Slip': 'Packing Slip',
			'Installation Note': 'Installation Note',
			'Sales Invoice': 'Invoice',
			'Stock Entry': 'Return',
		},
		frm.set_indicator_formatter('item_code',
			function(doc) {
				return (doc.docstatus==1 || doc.qty<=doc.actual_qty) ? "green" : "orange"
			});


		// erpnext.queries.setup_queries(frm, "Warehouse", function() {
			// return erpnext.queries.warehouse(frm.doc);
		// });
		// erpnext.queries.setup_warehouse_query(frm);

		/* frm.set_query('project', function(doc) {
			return {
				filters: [
						['Project', 'customer', '=', doc.customer],
						['Project', 'status', 'in', ['Open']],
						['Project', 'company', '=', doc.company],
					]
			}
		}) */

		frm.set_query('transporter', function() {
			return {
				filters: {
					'is_transporter': 1
				}
			}
		});

		frm.set_query('driver', function(doc) {
			return {
				filters: {
					'transporter': doc.transporter
				}
			}
		});


		frm.set_query('expense_account', 'items', function(doc, cdt, cdn) {
			if (erpnext.is_perpetual_inventory_enabled(doc.company)) {
				return {
					filters: {
						"report_type": "Profit and Loss",
						"company": doc.company,
						"is_group": 0
					}
				}
			}
		});

		frm.set_query('cost_center', 'items', function(doc, cdt, cdn) {
			if (erpnext.is_perpetual_inventory_enabled(doc.company)) {
				return {
					filters: {
						'company': doc.company,
						"is_group": 0
					}
				}
			}
		});
		
		

		
	},

	print_without_amount: function(frm) {
		erpnext.stock.delivery_note.set_print_hide(frm.doc);
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.is_return === 1 && frm.doc.per_billed !== 100) {
			frm.add_custom_button(__('Credit Note'), function() {
				frappe.model.open_mapped_doc({
					method: "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
					frm: cur_frm
				})
			}, __('Create'));
			frm.page.set_inner_btn_group_as_primary(__('Create'));
		}
	},
});

frappe.ui.form.on("Delivery Note Item", {
	expense_account: function(frm, dt, dn) {
		var d = locals[dt][dn];
		frm.update_in_all_rows('items', 'expense_account', d.expense_account);
	},
	cost_center: function(frm, dt, dn) {
		var d = locals[dt][dn];
		frm.update_in_all_rows('items', 'cost_center', d.cost_center);
	},
	item_code: function(frm, dt, dn) {
		var d = locals[dt][dn];
		
		// setTimeout(function() {
			// if(d.manufacturer_part_no)
			// {
				// var item_name = d.item_name;
				// if(d.item_name === d.item_code)
				// {
					// item_name = d.manufacturer_part_no + " " + d.item_code;
				// }
				// else
				// {
					// item_name = d.manufacturer_part_no + " " + d.item_name;
				// }
				// frappe.model.set_value(d.doctype, d.name, "item_name", item_name);
				
			// }
			
		// }, 500);

		
	},
	manufacturer_part_no: function(frm, dt, dn) {
		if(d.manufacturer_part_no)
		{
			// var item_name = d.manufacturer_part_no + " " + d.item_code;
			// frappe.model.set_value(d.doctype, d.name, "item_name", item_name);
				
		}
	},
});

erpnext.stock.DeliveryNoteController = erpnext.selling.SellingController.extend({
	setup: function(doc) {
		this.setup_posting_date_time_check();

		this._super(doc);
		this.frm.make_methods = {
			'Delivery Trip': this.make_delivery_trip,
		};
	},
	
	refresh: function(doc, dt, dn) {
		var me = this;
		this._super();
		if ((!doc.is_return) && (doc.status!="Closed" || this.frm.is_new())) {
			if (this.frm.doc.docstatus===0) {
				this.frm.add_custom_button(__('Sales Order'),
					function() {
						erpnext.utils.map_current_doc({
							method: "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note",
							source_doctype: "Sales Order",
							target: me.frm,
							setters: {
								customer: me.frm.doc.customer || undefined,
							},
							get_query_filters: {
								docstatus: 1,
								status: ["not in", ["Closed", "On Hold"]],
								per_delivered: ["<", 99.99],
								company: me.frm.doc.company,
								project: me.frm.doc.project || undefined,
							}
						})
					}, __("Get items from"));
			}
		}

		if (!doc.is_return && doc.status!="Closed") {
			if(flt(doc.per_installed, 2) < 100 && doc.docstatus==1)
				this.frm.add_custom_button(__('Installation Note'), function() {
					me.make_installation_note() }, __('Create'));

			if (doc.docstatus==1) {
				this.frm.add_custom_button(__('Sales Return'), function() {
					me.make_sales_return() }, __('Create'));
					
				this.frm.add_custom_button(__('Purchase Receipt - For Transfer'), function() {
					me.make_purchase_receipt() }, __("Create"));
					
				this.frm.add_custom_button(__('Delivery Note - For Transfer'), function() {
					me.make_transfer_dn() }, __("Create"));
					
			}

			if (doc.docstatus==1) {
				this.frm.add_custom_button(__('Delivery Trip'), function() {
					me.make_delivery_trip() }, __('Create'));
			}

			if(doc.docstatus==0 && !doc.__islocal) {
				
				this.frm.add_custom_button(__('Packing Slip'), function() {
					frappe.model.open_mapped_doc({
						method: "erpnext.stock.doctype.delivery_note.delivery_note.make_packing_slip",
						frm: me.frm
				}) }, __('Create'));
			}


			if (this.frm.doc.docstatus===0) {
				this.frm.add_custom_button(__('Sales Order'),
					function() {
						erpnext.utils.map_current_doc({
							method: "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note",
							source_doctype: "Sales Order",
							target: me.frm,
							setters: {
								customer: me.frm.doc.customer || undefined,
							},
							get_query_filters: {
								docstatus: 1,
								status: ["!=", "Closed"],
								per_delivered: ["<", 99.99],
								company: me.frm.doc.company,
								project: me.frm.doc.project || undefined,
							}
						})
					}, __("Get items from"));
					
				this.frm.add_custom_button(__('Sales Invoice'),
					function() {
						erpnext.utils.map_current_doc({
							method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note",
							source_doctype: "Sales Invoice",
							target: me.frm,
							date_field: "posting_date",
							setters: {
								customer: me.frm.doc.customer || undefined,
							},
							get_query_filters: {
								docstatus: ["!=", "2"],
								status: ["!=", "Closed"],
								company: me.frm.doc.company,
								project: me.frm.doc.project || undefined,
							}
						})
					}, __("Get items from"));
			}		
			if (!doc.__islocal && doc.docstatus==1) {
				this.frm.page.set_inner_btn_group_as_primary(__('Create'));
			}

		}

		if (doc.docstatus==1) {
			this.show_stock_ledger();
			if (erpnext.is_perpetual_inventory_enabled(doc.company)) {
				this.show_general_ledger();
			}
			if (this.frm.has_perm("submit") && doc.status !== "Closed") {
				me.frm.add_custom_button(__("Close"), function() { me.close_delivery_note() },
					__("Status"));
			}
		}

		if(doc.docstatus==1 && !doc.is_return && doc.status!="Closed" && flt(doc.per_billed) < 100) {
			// show Make Invoice button only if Delivery Note is not created from Sales Invoice
			var from_sales_invoice = false;
			from_sales_invoice = me.frm.doc.items.some(function(item) {
				return item.against_sales_invoice ? true : false;
			});

			if(!from_sales_invoice) {
				this.frm.add_custom_button(__('Sales Invoice'), function() { me.make_sales_invoice() },
					__('Create'));
			}
		}

		if(doc.docstatus==1 && doc.status === "Closed" && this.frm.has_perm("submit")) {
			this.frm.add_custom_button(__('Reopen'), function() { me.reopen_delivery_note() },
				__("Status"));
		}
		erpnext.stock.delivery_note.set_print_hide(doc, dt, dn);

		if(doc.docstatus==1 && !doc.is_return && !doc.auto_repeat) {
			cur_frm.add_custom_button(__('Subscription'), function() {
				erpnext.utils.make_subscription(doc.doctype, doc.name)
			}, __('Create'));
		}
	},

	make_sales_invoice: function() {
		frappe.model.open_mapped_doc({
			method: "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
			frm: this.frm
		});
	},

	make_installation_note: function() {
		frappe.model.open_mapped_doc({
			method: "erpnext.stock.doctype.delivery_note.delivery_note.make_installation_note",
			frm: this.frm
		});
	},

	make_sales_return: function() {
		frappe.model.open_mapped_doc({
			method: "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_return",
			frm: this.frm
		});
	},
	
	make_purchase_receipt: function() {
		
		frappe.model.open_mapped_doc({
				method: "erpnext.stock.doctype.delivery_note.delivery_note.make_purchase_receipt",
				frm: cur_frm
			});
		/* 
		var dialog = new frappe.ui.Dialog({
			title: __("Make Purchase Receipt"),
			fields: [
				{fieldname:'company', fieldtype:'Link', options: 'Company',label: __('Company'),reqd:1},
				{fieldname:'supplier', fieldtype:'Link', options: 'Supplier',label: __('Supplier'),reqd:1},
			]
		});
		
		dialog.fields_dict["company"].get_query = function(){
			return {
				filters: [
					]
					
				
			};
		};
			
		
		dialog.set_primary_action(__("Make"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				args:{
					company:filters.company,
					supplier:filters.customer,
					source_name:cur_frm.doc.name,
					project:filters.project,
				},
				method: "erpnext.stock.doctype.delivery_note.delivery_note.make_purchase_receipt",
				callback: function(r) {
					dialog.hide();

				}
			});
		
		});
		dialog.show();
		 */
	}, 
	
	make_transfer_dn: function() {
			
		var dialog = new frappe.ui.Dialog({
			title: __("Make Delivery Note"),
			fields: [
				{fieldname:'company', fieldtype:'Link', options: 'Company',label: __('Company'),reqd:1},
				{fieldname:'customer', fieldtype:'Link', options: 'Customer',label: __('Customer'),reqd:1},
				{fieldname:'project', fieldtype:'Link', options: 'Project',label: __('Project'),reqd:1},
			]
		});
		
		
		dialog.fields_dict["project"].get_query = function(){
			
			var dialog_filters = dialog.get_values();
			
			return {
				filters: [
						['Project', 'customer', '=', dialog_filters.customer],
						['Project', 'status', 'in', ['Open']],
						['Project', 'company', '=', dialog_filters.company],
					]
			};
		};
			
		
		dialog.set_primary_action(__("Make"), function() {
		
			var filters = dialog.get_values();
			
			
			frappe.call({
				args:{
					company:filters.company,
					customer:filters.customer,
					source_name:cur_frm.doc.name,
					project:filters.project,
				},
				method: "erpnext.stock.doctype.delivery_note.delivery_note.make_transfer_dn",
				callback: function(r) {
					dialog.hide();
					console.log(r);
					// frappe.msgprint(__("{0} Result", [r.message]));

				}
			});

		
		});
		dialog.show();
	}, 
	
	
	make_bom_stock_entry: function() {
		frappe.call({
			doc: this.frm.doc,
			method: "submit_to_manufacture",
			callback: function(r) {
				cur_frm.refresh();
			}
		});
	},


	make_delivery_trip: function() {
		frappe.model.open_mapped_doc({
			method: "erpnext.stock.doctype.delivery_note.delivery_note.make_delivery_trip",
			frm: cur_frm
		})
	},

	tc_name: function() {
		this.get_terms();
	},

	items_on_form_rendered: function(doc, grid_row) {
		erpnext.setup_serial_no();
	},

	packed_items_on_form_rendered: function(doc, grid_row) {
		erpnext.setup_serial_no();
	},

	close_delivery_note: function(doc){
		this.update_status("Closed")
	},

	reopen_delivery_note : function() {
		this.update_status("Submitted")
	},

	update_status: function(status) {
		var me = this;
		frappe.ui.form.is_saving = true;
		frappe.call({
			method:"erpnext.stock.doctype.delivery_note.delivery_note.update_delivery_note_status",
			args: {docname: me.frm.doc.name, status: status},
			callback: function(r){
				if(!r.exc)
					me.frm.reload_doc();
			},
			always: function(){
				frappe.ui.form.is_saving = false;
			}
		})
	},

});

$.extend(cur_frm.cscript, new erpnext.stock.DeliveryNoteController({frm: cur_frm}));

frappe.ui.form.on('Delivery Note', {
	setup: function(frm) {
		if(frm.doc.company) {
			frm.trigger("unhide_account_head");
		}
	},

	company: function(frm) {
		frm.trigger("unhide_account_head");
	},

	unhide_account_head: function(frm) {
		// unhide expense_account and cost_center if perpetual inventory is enabled in the company
		var aii_enabled = erpnext.is_perpetual_inventory_enabled(frm.doc.company)
		frm.fields_dict["items"].grid.set_column_disp(["expense_account", "cost_center"], aii_enabled);
	},
});




erpnext.stock.delivery_note.set_print_hide = function(doc, cdt, cdn){
	var dn_fields = frappe.meta.docfield_map['Delivery Note'];
	var dn_item_fields = frappe.meta.docfield_map['Delivery Note Item'];
	var dn_fields_copy = dn_fields;
	var dn_item_fields_copy = dn_item_fields;
	if (doc.print_without_amount) {
		dn_fields['currency'].print_hide = 1;
		dn_item_fields['rate'].print_hide = 1;
		dn_item_fields['discount_percentage'].print_hide = 1;
		dn_item_fields['price_list_rate'].print_hide = 1;
		dn_item_fields['amount'].print_hide = 1;
		dn_item_fields['discount_amount'].print_hide = 1;
		dn_fields['taxes'].print_hide = 1;
	} else {
		if (dn_fields_copy['currency'].print_hide != 1)
			dn_fields['currency'].print_hide = 0;
		if (dn_item_fields_copy['rate'].print_hide != 1)
			dn_item_fields['rate'].print_hide = 0;
		if (dn_item_fields_copy['amount'].print_hide != 1)
			dn_item_fields['amount'].print_hide = 0;
		if (dn_item_fields_copy['discount_amount'].print_hide != 1)
			dn_item_fields['discount_amount'].print_hide = 0;
		if (dn_fields_copy['taxes'].print_hide != 1)
			dn_fields['taxes'].print_hide = 0;
	}
}
