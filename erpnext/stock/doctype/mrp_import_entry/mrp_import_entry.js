// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Import Entry', {
	onload: function(frm) {
		if (frm.doc.__islocal) {
					frm.set_value("posting_date", frappe.datetime.nowdate());

					frm.set_value("posting_time", frappe.datetime.now_time());
					//frm.set_value("posting_date", frappe.datetime.get_today()+frappe.datetime.now_time());
					// frm.set_df_property("reference_name", "read_only", 1);
		}
		else
		{
		
		}
	},
	setup: function(frm) {
		
		frm.fields_dict["reference_name"].get_query = function(){
				
				var filters = {
					filters: [
							['docstatus', '=', '1'],
							['company', '=', frm.doc.company],
						]
				};
				
				
				// if(frappe.meta.has_field(frm.doc.transaction_type, 'status'))
					// filters["filters"].push(['status', '!=', 'Closed']);
				
				if (frm.doc.transaction_type != "MRP Production Order")
					filters["filters"].push(['status', '!=', 'Closed']);

				
				
				return filters;
			};
			
		
		frm.set_query("import_bill", "items", function(doc, cdt, cdn) {
			var row  = locals[cdt][cdn];
			
			if((cur_frm.doc.transaction_type == "MRP Production Order" || cur_frm.doc.transaction_type == "Delivery Note" || cur_frm.doc.transaction_type == "Deduction") && row.item_code){
				return {
					query: "erpnext.stock.doctype.mrp_import_bill.mrp_import_bill.import_bill_query",
					filters: {
						"item_code":row.item_code,
						"company":cur_frm.doc.company,
						"posting_date":cur_frm.doc.posting_date,
						"posting_time":cur_frm.doc.posting_time
					}
				};
			}
			else
			{
				return {
					filters: {
						"disabled":0,
						"company":cur_frm.doc.company
					}
				};
				
			}
			
		});
		
		
	},
	refresh: function(frm) {
		
		if(frm.doc.docstatus == 0)
		{
			
				frm.add_custom_button(__('Purchase Receipt'),
					function () {
						frm.trigger("import_from_purchase_receipt");
					}, __("Create Entry From"));
					
					
			frm.add_custom_button(__('Delivery Note'),
					function () {
												frm.trigger("import_from_delivery_note");

					}, __("Create Entry From"));
					
			// frm.add_custom_button(__('Production Order'),
					// function () {
												// frm.trigger("import_from_production_order");

					// }, __("Create Entry From"));
					
			frm.add_custom_button(__('Set Import Bill'),
						function () {
							if(frm.doc.transaction_type == "Purchase Receipt")
								frm.trigger("set_import_bill_for_pr");
							else if(frm.doc.transaction_type == "Addition")
								frm.trigger("set_import_bill_for_pr");
							else if(frm.doc.transaction_type == "Delivery Note")
								frm.trigger("set_import_bill_for_dn");
							else if(frm.doc.transaction_type == "Deduction")
								frm.trigger("set_import_bill_for_dn");
							// else if(frm.doc.transaction_type == "MRP Production Order")
								// frm.trigger("set_import_bill_for_pr");
						});
		}


						
		
		

	},
	transaction_type: function(frm){
		if(frm.doc.transaction_type == "Addition" || frm.doc.transaction_type == "Deduction")
		{
			frm.set_value("reference_name","");
			// frm.set_df_property("reference_name", "read_only", 1);

		}
		else
		{
			// frm.set_df_property("reference_name", "read_only", 0);

		}
		
		

	},
	reference_name: function(frm){
		
		

	},
	
	import_from_purchase_receipt: function(frm) {
		var dialog = new frappe.ui.Dialog({
			title: __("Create Entry From Purchase Receipt"),
			fields: [
				{fieldname:'import_bill', fieldtype:'Link', options: 'MRP Import Bill',label: __('Import Bill'),reqd:1},
				{fieldname:'purchase_receipt', fieldtype:'Link', options: 'Purchase Receipt',label: __('Purchase Receipt'),reqd:1},
			]
		});
		
		dialog.fields_dict["purchase_receipt"].get_query = function(){
			return {
				filters: [
						['docstatus', '=', '1'],
						['status', '!=', 'Closed'],
						['company', '=', frm.doc.company],
					]
					
				
			};
		};
			
		
		dialog.set_primary_action(__("Get"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: frm.doc,
				args:{
					data:filters.import_bill,
					document:filters.purchase_receipt,
					purpose:"Purchase Receipt",
				},
				method: "get_items_from",
				callback: function(r) {
					frm.refresh();
					frm.dirty();
					dialog.hide();
				}
			});

		
		});
		dialog.show();
	},
	
	import_from_delivery_note: function(frm) {
		var dialog = new frappe.ui.Dialog({
			title: __("Create Entry From Delivery Note"),
			fields: [
				{fieldname:'delivery_note', fieldtype:'Link', options: 'Delivery Note',label: __('Delivery Note'),reqd:1},
			]
		});
		
		dialog.fields_dict["delivery_note"].get_query = function(){
			return {
				filters: [
						['docstatus', '=', '1'],
						['status', '!=', 'Closed'],
						['company', '=', frm.doc.company],
					]
					
				
			};
		};
			
		
		dialog.set_primary_action(__("Get"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: frm.doc,
				args:{
					data:null,
					document:filters.delivery_note,
					purpose:"Delivery Note",
				},
				method: "get_items_from",
				callback: function(r) {
					frm.refresh();
						frm.dirty();
					dialog.hide();
				
				}
			});

		
		});
		dialog.show();
	},
	
	import_from_production_order: function(frm) {
		var dialog = new frappe.ui.Dialog({
			title: __("Create Entry From Production Order"),
			fields: [
				{fieldname:'mrp_production_order', fieldtype:'Link', options: 'MRP Production Order',label: __('MRP Production Order'),reqd:1},
			]
		});
		
		dialog.fields_dict["mrp_production_order"].get_query = function(){
			return {
				filters: [
						['docstatus', '=', '1'],
						['status', '=', 'Completed'],
						['company', '=', frm.doc.company],
					]
					
				
			};
		};
			
		
		dialog.set_primary_action(__("Get"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: frm.doc,
				args:{
					data:null,
					document:filters.mrp_production_order,
					purpose:"MRP Production Order",
				},
				method: "get_items_from",
				callback: function(r) {
					frm.refresh();
						frm.dirty();
					dialog.hide();
				
				}
			});

		
		});
		dialog.show();
	},
	
	
	set_import_bill_for_dn: function(frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Set Import Bill For All Items"),
			fields: [
				{fieldname:'description', fieldtype:'ReadOnly', default: 'Picks the best import bill with quantities'},
			]
		});
		dialog.set_primary_action(__("Set"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: frm.doc,
				args:{
					data:null,
					purpose:"Delivery Note",
				},
				method: "set_import_bill_for",
				callback: function(r) {
					dialog.hide();
					
				}
			});

		
		});
		dialog.show();
	},
	
	
	set_import_bill_for_pr: function(frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Set Import Bill For All Items"),
			fields: [
				{fieldname:'import_bill', fieldtype:'Link', options: 'MRP Import Bill',label: __('Import Bill'),reqd:1},
			]
		});
		
		
		dialog.fields_dict["import_bill"].get_query = function(){
			return {
					filters: [
						['disabled', '=', '0'],
						['company', '=', cur_frm.doc.company],
					]
			};
		};
		
		dialog.set_primary_action(__("Set"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: frm.doc,
				args:{
					data:filters.import_bill,
					purpose:"Purchase Receipt",
				},
				method: "set_import_bill_for",
				callback: function(r) {
					dialog.hide();
					
				}
			});

		
		});
		dialog.show();
	},
	
});

frappe.ui.form.on("MRP Import Entry Item",{

	item_code:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.item_code) {
			return frappe.call({
				
				method:'erpnext.manufacturing.doctype.mrp_production_order.mrp_production_order.get_item_det',
				args: {
					item_code: d.item_code
				},
				callback: function(r) {
					frappe.model.set_value(d.doctype, d.name, "stock_uom", r.message.stock_uom);
					frappe.model.set_value(d.doctype, d.name, "item_name", r.message.item_name);
					frappe.model.set_value(d.doctype, d.name, "stock_qty", 1);

				}
			});
		}
		
	},
	import_bill:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.item_code && d.import_bill) {
			return frappe.call({
				
				method:'erpnext.stock.doctype.mrp_import_bill.mrp_import_bill.get_total_qty_for_item',
				args: {
					import_bill: d.import_bill,
					item_code: d.item_code
				},
				callback: function(r) {

					frappe.model.set_value(d.doctype, d.name, "available_qty", r.message);
					
					if(cur_frm.doc.transaction_type == "Purchase Receipt" || cur_frm.doc.transaction_type == "Addition")
					{
						// var balance_qty = d.available_qty + d.stock_qty;
						// frappe.model.set_value(d.doctype, d.name, "balance_qty", balance_qty);
					}
					else
					{
						
					}
					

				}
			});
		}
	},
});
