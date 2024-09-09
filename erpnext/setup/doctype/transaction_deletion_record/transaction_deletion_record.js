// Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Transaction Deletion Record", {
	onload: function (frm) {
		if (frm.doc.docstatus == 0) {
			let doctypes_to_be_ignored_array;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.get_doctypes_to_be_ignored",
				callback: function (r) {
					doctypes_to_be_ignored_array = r.message;
					populate_doctypes_to_be_ignored(doctypes_to_be_ignored_array, frm);
					frm.refresh_field("doctypes_to_be_ignored");
				},
			});
		}
		frm.get_field('doctypes_to_be_ignored').grid.cannot_add_rows =false;
		frm.fields_dict['doctypes_to_be_ignored'].grid.set_column_disp('no_of_docs', false);
		frm.refresh_field('doctypes_to_be_ignored');
	},

	refresh: function(frm) {
		if (frm.doc.docstatus == 1 && ["Queued", "Failed"].find((x) => x == frm.doc.status)) {
			let execute_btn = frm.doc.status == "Queued" ? __("Start Deletion") : __("Retry");

			frm.add_custom_button(execute_btn, () => {
				// Entry point for chain of events
				frm.call({
					method: "start_deletion_tasks",
					doc: frm.doc,
				});
			});
		}

		/* frm.add_custom_button(__('Run'), () => {
			frm.trigger("mrp_run");
		}); */
		
		frm.add_custom_button(__('1. Delete Bins'), () => {
			frappe.call({
				doc: frm.doc,
				method: "delete_bins",
				freeze:true,
				callback: function(r) {
					cur_frm.dirty();
				}
			});
		}, __("Steps"));
		
		frm.add_custom_button(__('2. Delete Leads/Company Values/Notifications'), () => {
			frappe.call({
				doc: frm.doc,
				method: "second_step",
				freeze:true,
				callback: function(r) {
					cur_frm.dirty();
				}
			});
		}, __("Steps"));
		
		frm.add_custom_button(__('3. Update Deleted Naming Series'), () => {
			frappe.call({
				doc: frm.doc,
				method: "update_naming_series_custom",
				freeze:true,
				callback: function(r) {
					cur_frm.dirty();
				}
			});
		}, __("Steps"));
		
		frm.add_custom_button(__('4. Delete Transactions'), () => {
			frappe.call({
				doc: frm.doc,
				method: "delete_company_transactions",
				freeze:true,
				callback: function(r) {
					cur_frm.dirty();
				}
			});
		}, __("Steps"));
		
		frm.add_custom_button(__('5. Recalculate Bins'), () => {
			frappe.call({
				doc: frm.doc,
				method: "mrp_recalculate_bin_qty",
				freeze:true,
				callback: function(r) {
					cur_frm.dirty();
				}
			});
		}, __("Steps"));
		
		frm.add_custom_button(__('6. Delete Communications and Comments By Date'), () => {
			frappe.call({
				doc: frm.doc,
				method: "mrp_delete_connections",
				freeze:true,
				callback: function(r) {
					cur_frm.dirty();
				}
			});
		}, __("Steps"));
			
		frm.add_custom_button(__('7. Delete Comments of type Deleted'), () => {
			frappe.call({
				doc: frm.doc,
				method: "mrp_delete_comments",
				freeze:true,
				callback: function(r) {
					cur_frm.dirty();
				}
			});
		}, __("Steps"));
			
		frm.add_custom_button(__('Re-open Docs'), () => {
			
			frm.trigger("reopen_pos");
		}, __("Tools"));
		
		frm.add_custom_button(__('find_receipts'), () => {
			
			frm.trigger("find_receipts");
		}, __("Tools"));
		
		/*
		frm.add_custom_button(__('Cancel Reposts'), () => {
			frm.trigger("cancel_repos");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel PEs'), () => {
			frm.trigger("cancel_pes");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel PIs'), () => {
			frm.trigger("cancel_pis");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel PRs'), () => {
			frm.trigger("cancel_prs");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel IMPs'), () => {
			frm.trigger("cancel_imps");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel PROs'), () => {
			frm.trigger("cancel_pros");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel STRs'), () => {
			frm.trigger("cancel_strs");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel SEs'), () => {
			frm.trigger("cancel_ses");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel DNs'), () => {
			frm.trigger("cancel_dns");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel SIs'), () => {
			frm.trigger("cancel_sis");
		}, __("Tools"));
		
		frm.add_custom_button(__('Cancel JEs'), () => {
			frm.trigger("cancel_jes");
		}, __("Tools")); */
		
		frm.add_custom_button(__('Enable Warehouses'), () => {
			frm.trigger("enable_warehouses");
		}, __("Tools"));
		
		frm.add_custom_button(__('Disable Warehouses'), () => {
			frm.trigger("disable_warehouses");
		}, __("Tools"));
		
		frm.add_custom_button(__('Delete Warehouses'), () => {
			frm.trigger("delete_warehouses");
		}, __("Tools"));
		
	},
	mrp_run: function(frm){
		frappe.call({
			doc: frm.doc,
			method: "mrp_run",
			freeze:true,
			callback: function(r) {
				cur_frm.refresh_field('custom_mrp_summary');
				cur_frm.refresh_field('doctypes');
				cur_frm.dirty();
			}
		});
	},
	find_receipts: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Find PI'),
			fields: [
				{
					fieldname: "date",
					fieldtype: "Date",
					label:"Before Date",
					reqd: 1,
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Find'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.get_receipts_without_invoice",
				args: {
				},
				callback: function(r) {
					// console.log(r)
					d.hide();
					frappe.msgprint(r.message.docs_updated.join("<br>"));

					/* if(r.message && r.message.receipts.length > 0) {
						var receiptsInfo = r.message.receipts.map(function(receipt) {
							return `${receipt.receipt_name} - ${receipt.title}, ${receipt.posting_date}, ${receipt.status}`;
						}).join("<br>");

						frappe.msgprint(receiptsInfo);
					} else {
						frappe.msgprint("No receipts found without linked invoices.");
					} */
				}
			});
		})
		
		d.show();
	},
	reopen_pos: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Re-open Docs'),
			fields: [
				{
					fieldname: "doctype",
					fieldtype: "Link",
					options:"DocType",
					label:"DocType",
					reqd: 1,
				},
				{
					fieldname: "date",
					fieldtype: "Date",
					label:"Before Date",
					reqd: 1,
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Reopen'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.reopen_docs",
				args: {
					doctype: data.doctype,
					date: data.date,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					// console.log(r)
					d.hide();
					frappe.msgprint(r.message.docs_updated.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_pes: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel PEs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_pes",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_pis: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel PIs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_pis",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_prs: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel PRs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_prs",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_ses: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel SEs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_ses",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_dns: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel DNs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_dns",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_sis: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel SIs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_sis",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_jes: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel JEs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_jes",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_imps: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel IMPs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_imps",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_pros: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel PROs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_pros",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_strs: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel STRs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_strs",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	cancel_repos: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Cancel REPOs'),
			fields: [
				{
					fieldname: "year",
					fieldtype: "Int",
					label:"Year",
					reqd: 1,
					default:2017
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Cancel'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.cancel_repos",
				args: {
					year: data.year,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	enable_warehouses: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Enable Warehouses'),
			fields: [
				{
					fieldname: "parent_warehouse",
					fieldtype: "Link",
					options: "Warehouse",
					label:"Parent Warehouse",
					reqd: 1
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Enable'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.enable_warehouses",
				args: {
					parent_warehouse: data.parent_warehouse,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	disable_warehouses: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Disable Warehouses'),
			fields: [
				{
					fieldname: "parent_warehouse",
					fieldtype: "Link",
					options: "Warehouse",
					label:"Parent Warehouse",
					reqd: 1
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Disable'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.disable_warehouses",
				args: {
					parent_warehouse: data.parent_warehouse,
					limit: data.limit,
					submit: cint(data.submit)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
	delete_warehouses: function(){
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Delete Warehouses'),
			fields: [
				{
					fieldname: "parent_warehouse",
					fieldtype: "Link",
					options: "Warehouse",
					label:"Parent Warehouse",
					reqd: 1
				},
				{
					fieldname: "limit",
					fieldtype: "Int",
					label:"Limit",
					reqd: 1,
					default:1
				},
				{
					fieldname: "force",
					fieldtype: "Check",
					label:"Force"
				},
				{
					fieldname: "submit",
					fieldtype: "Check",
					label:"Submit"
				}
			],
		});
		
		d.set_primary_action(__('Delete'), function() {
			var data = d.get_values();
			if(!data) return;
			frappe.call({
				method: "erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record.delete_warehouses",
				args: {
					parent_warehouse: data.parent_warehouse,
					limit: data.limit,
					submit: cint(data.submit),
					force: cint(data.force)
				},
				callback: function(r) {
					if(!r.exc) {
					}
					console.log(r)
					d.hide();
					frappe.msgprint(r.message.join("<br>"));
				}
			});
		})
		
		d.show();
	},
});

function populate_doctypes_to_be_ignored(doctypes_to_be_ignored_array, frm) {
	if (frm.doc.doctypes_to_be_ignored.length === 0) {
		var i;
		for (i = 0; i < doctypes_to_be_ignored_array.length; i++) {
			frm.add_child("doctypes_to_be_ignored", {
				doctype_name: doctypes_to_be_ignored_array[i],
			});
		}
	}
}
