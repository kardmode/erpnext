// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
var in_progress = false;

frappe.ui.form.on('VAT Return', {
	onload: function (frm) {
		
		
	},
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			frm.set_value('posting_date',frappe.datetime.nowdate());
			
		}
		
		if (!frm.doc.__islocal && frm.doc.docstatus<1) {
			frm.add_custom_button(__("Update VAT Return"), function() {
				frm.events.update_vat_return(frm);
			});
			;

		}
		
	},
	vat_reporting_period: function(frm) {
		frm.trigger("set_start_end_dates");
	},
	start_date: function (frm) {
		if(!in_progress && frm.doc.start_date){
			frm.trigger("set_start_end_dates");
		}else{
			// reset flag
			in_progress = false;
		}
	},
	
	set_start_end_dates: function (frm) {
		var date = frm.doc.start_date || frm.doc.posting_date;
		frappe.call({
			method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.get_start_end_dates',
			args: {
				payroll_frequency: frm.doc.vat_reporting_period,
				start_date: date,
			},
			callback: function (r) {
				if (r.message) {
					console.log(r);
					in_progress = true;
					frm.set_value('start_date', r.message.start_date);
					frm.set_value('end_date', r.message.end_date);
				}
			}
		});
	},

	set_end_date: function(frm){
		frappe.call({
			method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.get_end_date',
			args: {
				frequency: frm.doc.vat_reporting_period,
				start_date: frm.doc.start_date
			},
			callback: function (r) {
				if (r.message) {
					console.log(r);
					frm.set_value('end_date', r.message.end_date);
				}
			}
		});
	},
	
	update_vat_return: function(frm){
		
		frappe.call({	
			doc: frm.doc,
			method: "create_vat_return",
			freeze:true,
			callback: function(r) {
				frm.refresh();
				frm.dirty();
			}
		});
		
		
	},
});
