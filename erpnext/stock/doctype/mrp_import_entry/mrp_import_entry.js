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
						"item_alt":row.item_alt,
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
		
		
		frm.set_query("item_alt", "items", function(doc, cdt, cdn) {
			var row  = locals[cdt][cdn];
			
			return {
				filters: {
					"item_code":row.item_code,
				}
			};
			
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
					
			frm.add_custom_button(__('MRP Production Order'),
					function () {
												frm.trigger("import_from_production_order");

					}, __("Create Entry From"));
					
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
							else if(frm.doc.transaction_type == "MRP Production Order")
								frm.trigger("set_import_bill_for_pr");
						});
		}


						
		
		

	},
	transaction_type: function(frm){
		if(frm.doc.transaction_type == "Addition" || frm.doc.transaction_type == "Deduction")
		{
			frm.set_value("reference_name","");
			frm.set_value("items",[]);
			// frm.set_df_property("reference_name", "read_only", 1);

		}
		else
		{
			// frm.set_df_property("reference_name", "read_only", 0);

		}
		
		

	},
	reference_name: function(frm){
		
		

	},
	customs_entry_total: function(frm){
		/* 
		if(frm.doc.transaction_type == "Purchase Receipt")
		{
			if(frm.doc.reference_name)
			{
				
				
				var dialog = new frappe.ui.Dialog({
					title: __("Create Entry From Purchase Receipt"),
					fields: [
						{fieldname:'import_bill', fieldtype:'Link', options: 'MRP Import Bill',label: __('Import Bill'),reqd:1},
						// {fieldname:'purchase_receipt', fieldtype:'Link', options: 'Purchase Receipt',label: __('Purchase Receipt'),reqd:1},
						{fieldname:'sec1', fieldtype:'Section Break'},
						// {fieldname:'use_customs_total', fieldtype:'Check', label: __('Use Customs Total'),default:'0',reqd:0},
						// {fieldname:'col1', fieldtype:'Column Break'},
						// {fieldname:'customs_entry_total', fieldtype:'Currency', options: 'Currency',label: __('Customs Total AED'),default:'0',reqd:0},
						// {fieldname:'exchange_rate', fieldtype:'Float', label: __('Exchange Rate'),default:1,reqd:1},
						// {fieldname:'additional_fees', fieldtype:'Currency', options: 'Currency',label: __('Additional Fees'),default:'0',reqd:1},
					]
				});
				
				dialog.fields_dict["import_bill"].get_query = function(){
					return {
						filters: [
								['disabled', '=', '0'],
								]
					};
				};
					
				
				dialog.set_primary_action(__("Get"), function() {
				
					var filters = dialog.get_values();
					
					filters["customs_entry_total"] = frm.doc.customs_entry_total;
					filters["purchase_receipt"] = frm.doc.reference_name;
					

			
					
					frappe.call({
						doc: frm.doc,
						args:{
							data:filters,
							document:frm.doc.reference_name,
							purpose:"Purchase Receipt",
						},
						method: "get_items_from",
						callback: function(r) {
							frm.refresh();
							frm.dirty();
							dialog.hide();
						},
						freeze: true,
						freeze_message: "Processing"
					});

				
				});
				dialog.show();
				
				
				
				
				
				
			}
		} */

	},
	
	import_from_purchase_receipt: function(frm) {
		var dialog = new frappe.ui.Dialog({
			title: __("Create Entry From Purchase Receipt"),
			fields: [
				{fieldname:'import_bill', fieldtype:'Link', options: 'MRP Import Bill',label: __('Import Bill'),reqd:1},
				{fieldname:'purchase_receipt', fieldtype:'Link', options: 'Purchase Receipt',label: __('Purchase Receipt'),reqd:1},
				{fieldname:'sec1', fieldtype:'Section Break'},
				// {fieldname:'use_customs_total', fieldtype:'Check', label: __('Use Customs Total'),default:'0',reqd:0},
				// {fieldname:'col1', fieldtype:'Column Break'},
				{fieldname:'customs_entry_total', fieldtype:'Currency', options: 'Currency',label: __('Customs Total AED'),default:'0',reqd:1},
				// {fieldname:'exchange_rate', fieldtype:'Float', label: __('Exchange Rate'),default:1,reqd:1},
				// {fieldname:'additional_fees', fieldtype:'Currency', options: 'Currency',label: __('Additional Fees'),default:'0',reqd:1},
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
		
		dialog.fields_dict["import_bill"].get_query = function(){
			return {
				filters: [
						['disabled', '=', '0'],
				]
			};
		};
			
		
		dialog.set_primary_action(__("Get"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: frm.doc,
				args:{
					data:filters,
					document:filters.purchase_receipt,
					purpose:"Purchase Receipt",
				},
				method: "get_items_from",
				callback: function(r) {
					frm.refresh();
					frm.dirty();
					dialog.hide();
				},
				freeze: true,
				freeze_message: "Processing"
			});

		
		});
		dialog.show();
	},
	
	import_from_delivery_note: function(frm) {
		var dialog = new frappe.ui.Dialog({
			title: __("Create Entry From Delivery Note"),
			fields: [
				{fieldname:'delivery_note', fieldtype:'Link', options: 'Delivery Note',label: __('Delivery Note'),reqd:1},
				{fieldname:'get_manufactured_items', fieldtype:'Check', label: __('Get Production Order Items'),hidden:1},
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
					data:filters.get_manufactured_items,
					document:filters.delivery_note,
					purpose:"Delivery Note",
				},
				method: "get_items_from",
				callback: function(r) {
					frm.refresh();
						frm.dirty();
					dialog.hide();
				
				},
				freeze: true,
				freeze_message: "Processing"
			});

		
		});
		dialog.show();
	},
	
	import_from_production_order: function(frm) {
		var dialog = new frappe.ui.Dialog({
			title: __("Create Entry From MRP Production Order"),
			fields: [
				{fieldname:'mrp_production_order', fieldtype:'Link', options: 'MRP Production Order',label: __('MRP Production Order'),reqd:1},
			]
		});
		
		dialog.fields_dict["mrp_production_order"].get_query = function(){
			return {
				filters: [
						['docstatus', '=', '1'],
						['workflow_state', '=', 'Completed'],
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
				
				},
				freeze: true,
				freeze_message: "Processing"
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
	
	update_exit_rate_for_pr: function(frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Update Exit Rate For All Items"),
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
	calculate_totals: function(frm) {
		frm.doc.items.forEach(d)
		{
			 console.log(d);
		}
	},
});

frappe.ui.form.on("MRP Import Entry Item",{
	item_code:function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.item_code) {
			get_item_details(row.item_code).then(data => {
				frappe.model.set_value(cdt, cdn, 'item_name', data.item_name);
				frappe.model.set_value(cdt, cdn, 'description', data.item_name);
				frappe.model.set_value(cdt, cdn, 'uom', data.stock_uom);
				frappe.model.set_value(cdt, cdn, 'stock_uom', data.stock_uom);
				frappe.model.set_value(cdt, cdn, 'conversion_factor', 1);
				frappe.model.set_value(cdt, cdn, 'rate', data.last_purchase_rate);
				frappe.model.set_value(cdt, cdn, 'base_rate', data.last_purchase_rate);
				frappe.model.set_value(cdt, cdn, 'stock_qty', 1);
				frappe.model.set_value(cdt, cdn, 'qty', 1);
			});
		}
	},
	item_alt:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.item_code && d.import_bill) {
			return frappe.call({
				
				method:'erpnext.stock.doctype.mrp_import_bill.mrp_import_bill.get_total_qty_for_item',
				args: {
					import_bill: d.import_bill,
					item_code: d.item_code,
					item_alt:d.item_alt,
					posting_date:cur_frm.doc.posting_date,
					posting_time:cur_frm.doc.posting_time
				},
				callback: function(r) {

					frappe.model.set_value(d.doctype, d.name, "available_qty", r.message);
					
					if(cur_frm.doc.transaction_type == "Purchase Receipt" || cur_frm.doc.transaction_type == "Addition")
					{
						frappe.model.set_value(d.doctype, d.name, "balance_qty", d.available_qty + d.stock_qty);
					}
					else
					{
						frappe.model.set_value(d.doctype, d.name, "balance_qty", d.available_qty - d.stock_qty);
					}
					

				}
			});
		}

	},
	uom:function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.uom) {
			get_item_details(row.item_code, row.uom).then(data => {
				frappe.model.set_value(cdt, cdn, 'conversion_factor', data.conversion_factor);
				// change rate
			});
		}
	},
	qty:function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		frappe.model.set_value(cdt, cdn, 'stock_qty', row.qty * row.conversion_factor);
	},
	conversion_factor:function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		frappe.model.set_value(cdt, cdn, 'stock_qty', row.qty * row.conversion_factor);
	},
	import_bill:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.item_code && d.import_bill) {
			return frappe.call({
				
				method:'erpnext.stock.doctype.mrp_import_bill.mrp_import_bill.get_total_qty_for_item',
				args: {
					import_bill: d.import_bill,
					item_code: d.item_code,
					item_alt:d.item_alt,
					posting_date:cur_frm.doc.posting_date,
					posting_time:cur_frm.doc.posting_time
				},
				callback: function(r) {

					frappe.model.set_value(d.doctype, d.name, "available_qty", r.message);
					
					if(cur_frm.doc.transaction_type == "Purchase Receipt" || cur_frm.doc.transaction_type == "Addition")
					{
						frappe.model.set_value(d.doctype, d.name, "balance_qty", d.available_qty + d.stock_qty);
					}
					else
					{
						frappe.model.set_value(d.doctype, d.name, "balance_qty", d.available_qty - d.stock_qty);
					}
					

				}
			});
		}
	},
	customs_exit_rate:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		var transaction_type = cur_frm.doc.transaction_type;
		if(["Addition","Deduction"].includes(transaction_type))
		{
			frappe.model.set_value(cdt, cdn, 'rate', d.customs_exit_rate);
			frappe.model.set_value(cdt, cdn, 'base_rate', d.customs_exit_rate);
			frappe.model.set_value(cdt, cdn, 'amount', d.qty * d.customs_exit_rate);
		}
	}
});


function get_item_details(item_code, uom=null) {
	if (item_code) {
		return frappe.xcall('erpnext.stock.doctype.mrp_import_entry.mrp_import_entry.get_item_det', {
			item_code,
			uom
		});
	}
}
