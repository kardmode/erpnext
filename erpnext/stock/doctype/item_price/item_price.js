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

		frm.set_df_property("bulk_import_help", "options",
			'<a href="#data-import-tool/Item Price">' + __("Import in Bulk") + '</a>');
	},
	refresh: function(frm){
		if(!frm.doc.uom)
			frm.set_value("uom",frm.doc.stock_uom);
		
		if(frm.doc.buying){
			frm.set_value("reference_doctype","Supplier");

		}
		else if(frm.doc.selling){
			
			frm.set_value("reference_doctype","Customer");

		}
	},
	price_list: function(frm){
		if(frm.doc.buying){
			frm.set_value("reference_doctype","Supplier");

		}
		else if(frm.doc.selling){
			
			frm.set_value("reference_doctype","Customer");

		}
	}
});
