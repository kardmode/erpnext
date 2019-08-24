// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Job Order', {
	
	setup: function(frm) {
		/* frm.set_query('project', function(doc) {
			return {
				filters: [
						['Project', 'status', 'in', ['Open']],
						['Project', 'company', '=', doc.company],
					]
			}
		}); */
		
		erpnext.queries.setup_project_query(frm);
	},
	refresh: function(frm) {
		
		
		if (frm.doc.__islocal) {
			frm.set_value("posting_date",frappe.datetime.get_today());
			
		}
		else{
			if(!frm.doc.posting_date)
				frm.set_value("posting_date",frappe.datetime.get_today());
		}

	}
});


frappe.ui.form.on("MRP Job Order Item",{

	item_code:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.item_code) {
			return frappe.call({
				
				method:'erpnext.manufacturing.doctype.mrp_production_order.mrp_production_order.get_item_det',
				args: {
					item_code: d.item_code
				},
				callback: function(r) {
					frappe.model.set_value(d.doctype, d.name, "uom", r.message.stock_uom);
					frappe.model.set_value(d.doctype, d.name, "stock_uom", r.message.stock_uom);
					frappe.model.set_value(d.doctype, d.name, "item_name", r.message.item_name);
					frappe.model.set_value(d.doctype, d.name, "qty", 1);
					frappe.model.set_value(d.doctype, d.name, "stock_qty", 1);

				}
			});
		}
		
	},
});
