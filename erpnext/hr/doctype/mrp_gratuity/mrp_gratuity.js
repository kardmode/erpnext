// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

cur_frm.add_fetch("employee", "employee_name", "employee_name");
cur_frm.add_fetch("employee", "company", "company");
cur_frm.add_fetch("employee", "date_of_joining", "joining_date");
cur_frm.add_fetch("employee", "relieving_date", "relieving_date");

frappe.ui.form.on('MRP Gratuity', {
	refresh: function(frm) {
		
		if(cint(frm.doc.__islocal) == 1){
			frm.set_value("posting_date",frappe.datetime.get_today());

		}
		
		if (!frm.doc.__islocal && frm.doc.docstatus<2) {
	
			
			frm.add_custom_button(__("Calculate"), function() {
				frm.trigger("calculate_gratuity");
			});

		}
		
		// frm.set_value("gratuity",0);
		// frm.set_value("summary","");
		// frm.set_value("joining_date","");
		// frm.set_value("leave_encashment_amount",0);
		// frm.set_value("company","");
		// frm.set_value("employee","");
		// frm.set_value("employee_name","");
		// frm.set_value("salary_per_day","");
	},
	employee: function(frm) {
		if (!frm.doc.employee)
		{
			frm.set_value("gratuity",0);
			frm.set_value("summary","");
			frm.set_value("joining_date","");
			frm.set_value("leave_encashment_amount",0);
			frm.set_value("company","");
			frm.set_value("employee_name","");
					frm.set_value("salary_per_day","");

		}
		else
		{
			frm.trigger("calculate_gratuity");
		}
		
	},
	relieving_date: function(frm) {
		frm.trigger("calculate_gratuity");
	},
	calculate_gratuity: function(frm) {
		
		if (frm.doc.relieving_date && frm.doc.employee && frm.doc.joining_date)
		{
			frappe.call({
				doc: frm.doc,
				method: "test_calculate_gratuity",
				callback: function(r) {
					cur_frm.dirty();
					cur_frm.refresh();
				}
			});
			
		}
		else
		{
			//frappe.msgprint("Information Missing");
		}
		
	},
	
});

cur_frm.fields_dict['employee'].get_query = function(doc) {
	return {
		filters: {
			"status": 'Active'
		}
	}
}