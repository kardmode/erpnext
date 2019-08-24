// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Bank Transfer', {
	setup: function(frm) {
		
		
		frm.fields_dict['project'].get_query = function(doc) {
			return {
				filters: {
					"company": doc.company
				}
			}
		}
		
		frm.fields_dict['reference_name'].get_query = function(doc) {
			return {
				filters: {
					"company": doc.company
				}
			}
		}
		
	},
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			frm.set_value("posting_date",frappe.datetime.get_today());
			
		}
		else{
			if(!frm.doc.posting_date)
				frm.set_value("posting_date",frappe.datetime.get_today());
		}
	},
	reference_doctype: function(frm){
		
	},
	
	reference_name: function(frm){
		if(frm.doc.reference_doctype && frm.doc.reference_name)
		{
			//			if(frappe.meta.has_field(frm.doc.reference_doctype, "project"))

			if(frm.doc.reference_doctype != "Purchase Order"){
									
				frappe.db.get_value(frm.doc.reference_doctype, { 'name' : frm.doc.reference_name }, 'project')
					.then(({ message }) => {
						(frm.set_value("project",message.project));
				});

			}
			else{
				frm.set_value("project","");
			}
		}
		
		

	},
	address: function(frm){
		if(frm.doc.address)
		{
			
			erpnext.utils.get_address_display(frm, 'address', 'address_display');
		}
		
	}
});
