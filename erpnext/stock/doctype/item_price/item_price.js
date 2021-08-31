// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Item Price", {
	onload: function (frm) {
		// Fetch price list details
		frm.add_fetch("price_list", "buying", "buying");
		frm.add_fetch("price_list", "selling", "selling");
		frm.add_fetch("price_list", "currency", "currency");

		// Fetch item details
		frm.add_fetch("item_code", "item_name", "item_name");
		frm.add_fetch("item_code", "description", "item_description");
		frm.add_fetch("item_code", "stock_uom", "stock_uom");
		frm.add_fetch("item_code", "stock_uom", "uom");

		frm.set_df_property("bulk_import_help", "options",
			'<a href="#data-import-tool/Item Price">' + __("Import in Bulk") + '</a>');
	},
	refresh: function(frm){
		if(!frm.doc.uom)
			frm.set_value("uom",frm.doc.stock_uom);
		
		if (!frm.doc.__islocal && frm.doc.docstatus<2) {
			
			frm.add_custom_button(__("Current Item Price"), function() {
				frm.events.add_to_another_pl(frm);
			}, __("Copy"));

			frm.add_custom_button(__("All Prices To New List"), function() {
				frm.events.copy_all_to_another_pl(frm);
			}, __("Copy"));
		}

	},
	price_list: function(frm){

	},
	add_to_another_pl: function(frm){
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Copy This Item Price To Different List"),
			fields: [
				{fieldname:'price_list', fieldtype:'Link', options: 'Price List',label: __('Price List'),reqd:1},
			]
		});
		dialog.set_primary_action(__("Copy"), function() {
		
			var filters = dialog.get_values();
			if(filters.price_list === frm.doc.price_list)
			{
				frappe.throw(__("Same Price List"));
			}
			
			frappe.call({
				method:'erpnext.stock.doctype.item_price.item_price.add_to_another_pl',
				args:{
					item_price_docname: frm.doc.name,
					new_price_list:filters.price_list,
				},
				callback:function (r) {
					
					dialog.hide();
					frappe.set_route("Form", "Item Price", r.message);
						

				},
				freeze:true,
			})
			

		
		});
		dialog.show();
	},
	copy_all_to_another_pl: function(frm){
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Copy All Prices in List To Different List"),
			fields: [
				{fieldname:'price_list', fieldtype:'Link', options: 'Price List',label: __('Price List'),reqd:1},
			]
		});
		dialog.set_primary_action(__("Add"), function() {
		
			var filters = dialog.get_values();
			if(filters.price_list === frm.doc.price_list)
			{
				frappe.throw(__("Same Price List"));
			}
			
			frappe.call({
				method:'erpnext.stock.doctype.item_price.item_price.copy_all_to_another_pl',
				args:{
					original_price_list: frm.doc.price_list,
					new_price_list:filters.price_list,
				},
				callback:function (r) {
					
					dialog.hide();
					// frappe.set_route("Form", "Item Price", r.message);
						

				},
				freeze:true,
				freeze_message: __('Processing')
			})
			

		
		});
		dialog.show();
	},
});
