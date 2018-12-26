// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
cur_frm.cscript.onload = function(doc) {
	cur_frm.set_value("company", frappe.defaults.get_default("Company"))
}

// cur_frm.cscript.refresh = function(doc) {
	// cur_frm.disable_save();
// }

cur_frm.add_fetch("reference_name", "project", "project");
cur_frm.add_fetch("reference_name", "title", "reference_title");
// cur_frm.add_fetch("employee", "date_of_joining", "joining_date");

frappe.ui.form.on('Custom Production Order', {
	refresh: function(frm) {
		frm.get_field("get_summary").$input.addClass("btn-primary");
		frm.get_field("make_entries").$input.addClass("btn-primary");
		
		if(!frm.doc.__islocal)
		{
			
			frm.set_query('source_warehouse', 'exploded_items', function(doc, cdt, cdn) {
			
				var item = locals[cdt][cdn];
				if(!item.item_code) {
					
				} else {
					return {
						query : "erpnext.stock.doctype.stock_entry.stock_entry.get_warehouses_with_stock",
						filters: {"item_code":item.item_code,"company":doc.company}
					}
				}
			});
			
			frm.trigger("refresh_summary");
			var df = frappe.meta.get_docfield("BOM Explosion Item", "source_warehouse", cur_frm.doc.name);
			df.read_only = 0;
			//refresh_field("exploded_items");
			
			frm.add_custom_button(__("Manufacture"), function() {
				frm.trigger("make_entries");
			});
			
			frm.add_custom_button(__("Submit Entries"), function() {
				frm.trigger("submit_entries");
			})
			
			frm.add_custom_button(__("Delete Entries"), function() {
				frm.trigger("delete_entries");
			})
		}
		else
		{
			frm.trigger("reference_doctype");
			
		}
		
	},
	onload_post_render: function(frm) {
	 		frm.get_field("items").grid.set_multiple_add("item_code", "qty");
			
			
	 },
	 
	onload: function(frm) {
		
		
	},
	refresh_summary: function(frm) {
		frappe.call({
				doc: cur_frm.doc,
				method: "get_stock_entries",
				freeze: true,
				callback: function(r) {
					refresh_field("summary");
				}
			});
		
	},
	reference_doctype: function(frm) {
		if (frm.doc.reference_doctype == "")
		{
			frm.set_value("reference_name","");
			frm.set_df_property("reference_name", "read_only", 1);
		}
		else if (frm.doc.reference_doctype == "Stock")
		{
			frm.set_value("reference_name","");
			frm.set_df_property("reference_name", "read_only", 1);
		}
		else
		{
			frm.set_value("reference_name","");
			frm.set_df_property("reference_name", "read_only", 0);
		}
		
	},
	
	reference_name: function(frm) {
		if (frm.doc.reference_name)
		{
			frm.trigger("get_items");

		}
		else{
			frm.set_value("items",[]);
			frm.set_value("project","");
			frm.set_value("remarks","");
			frm.set_value("reference_title","");
		}
	},
	
	
	get_items:function(frm) {
		frappe.call({
				doc: cur_frm.doc,
				method: "get_items_from_dn",
				freeze: true,
				callback: function(r) {
					refresh_field("items");
					cur_frm.dirty();
				}
			});
	},
	
	get_summary:function(frm) {
		if(frm.doc.__islocal)
		{
			frappe.msgprint(__("Production Order Must Be Saved"));
			return;
			
		}
		frappe.call({
				doc: cur_frm.doc,
				method: "get_summary",
				freeze: true,
					freeze_message: "Please wait ..",
				callback: function(r) {
					if(r.message)
					{
						cur_frm.save();
						// refresh_field("exploded_items");
						// refresh_field("per_item_summary");
					}
					else 
					{
						frappe.msgprint(__("No items found in BOM"));
					}
				}
			});
	},
	
	
	make_entries:function(frm) {
		if(frm.doc.__islocal)
		{
			frappe.msgprint(__("Production Order Must Be Saved"));
			return;
			
		}
		
		frappe.confirm(
			__('This will create draft stock entries. Start production of items?'),
			function() {
				frappe.call({
					doc: cur_frm.doc,
					method: "make_stock_entries",
					freeze: true,
					freeze_message: "Please wait ..",
					callback: function(r) {
						
						if(r.message)
						{
							cur_frm.save();
						}
						else 
						{
							frappe.msgprint(__("Stock Entry Not Created"));
						}
							

						
					}
				});
			}
		);
		
		
		
	},
	
	submit_entries:function(frm) {
		if(frm.doc.__islocal)
		{
			frappe.msgprint(__("Production Order Must Be Saved"));
			return;
			
		}
		
		frappe.confirm(
			__('This will submit all stock entries. Finish production of items?'),
			function() {
				frappe.call({
			doc: cur_frm.doc,
			method: "submit_entries",
			freeze: true,
			freeze_message: "Please wait ..",
			callback: function(r) {
				
				if(r.message)
				{
					cur_frm.save();
				}
				else 
				{
					frappe.msgprint(__("Stock Entrie Not Submitted"));
				}
					

				
			}
		});
			}
		);
		
		
		
	},
	
	delete_entries:function(frm) {
		if(frm.doc.__islocal)
		{
			frappe.msgprint(__("Production Order Must Be Saved"));
			return;
			
		}
		
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Delete Stock Entris for Production Order"),
			fields: [
							{fieldname:'delete_draft', fieldtype:'Check', label: __('Delete Drafts'),default:0},

				{fieldname:'column', fieldtype:'Column Break'},
								{fieldname:'delete_submitted', fieldtype:'Check', label: __('Delete Submitted'),default:0},

			]
		});
		dialog.set_primary_action(__("Delete"), function() {
		
			var filters = dialog.get_values();
			
			frappe.call({
				doc: cur_frm.doc,
				method: "delete_entries",
				freeze: true,
				freeze_message: "Please wait ..",
				args:{
					delete_submitted:filters.delete_submitted,
					delete_draft: filters.delete_draft
				},
				callback: function(r) {
					if(r.message)
					{
												

						cur_frm.save();
					}
					else 
					{
						frappe.msgprint(__("Stock Entries Not Deleted"));
					}
				}
			});
			dialog.hide();
		
		});
		dialog.show();
	},
});

frappe.ui.form.on("Custom Production Item",{
	bom:function(frm, cdt, cdn) {
	},
	item_code:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.item_code) {
			return frappe.call({
				
				method:'erpnext.manufacturing.doctype.custom_production_order.custom_production_order.get_item_det',
				args: {
					item_code: d.item_code
				},
				callback: function(r) {
					frappe.model.set_value(d.doctype, d.name, "uom", r.message.stock_uom);
					frappe.model.set_value(d.doctype, d.name, "height", r.message.height);
					frappe.model.set_value(d.doctype, d.name, "heightunit", r.message.heightunit);
					frappe.model.set_value(d.doctype, d.name, "width", r.message.width);
					frappe.model.set_value(d.doctype, d.name, "widthunit", r.message.widthunit);
					frappe.model.set_value(d.doctype, d.name, "depth", r.message.depth);
					frappe.model.set_value(d.doctype, d.name, "depthunit", r.message.depthunit);
					frappe.model.set_value(d.doctype, d.name, "bom", r.message.default_bom);
				}
			});
		}
		
	},
});

cur_frm.fields_dict['reference_name'].get_query = function(doc) {
	return {
		filters: {
			'company': cur_frm.doc.company,
			'docstatus': ["<",2],
			'status': ["in",["Draft","Open"]]
		}
	}
}
		
frappe.ui.form.on('BOM Explosion Item', {
	
	source_warehouse:function(frm, cdt, cdn) {
	},
	required_uom:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.required_uom)
		{
			if(d.required_uom !== d.stock_uom)
			{
				frappe.call({
					method:'erpnext.stock.get_item_details.get_conversion_factor',
					args:{
						uom: d.required_uom,
						item_code:d.item_code,
					},
					callback:function (r) {
						
						var conversion_factor = 1;
						
						conversion_factor = r.message.conversion_factor || 1;
						
						var required_qty = d.stock_qty / conversion_factor;
						frappe.model.set_value(d.doctype, d.name, "required_qty", required_qty);
						
							

					}
				})
			}
			else
			{
				frappe.model.set_value(d.doctype, d.name, "required_qty", d.stock_qty);

			}
			
		}
		
		
	},	
	
});

cur_frm.fields_dict['items'].grid.get_field('bom').get_query = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.item_code) {
		return{
		filters:[
			['BOM', 'docstatus', '<', 2],['BOM', 'is_active', '=', 1],
		]
	}
	} else frappe.msgprint(__("Please enter Item first"));
}

