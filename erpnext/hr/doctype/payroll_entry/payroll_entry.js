// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

cur_frm.cscript.display_activity_log = function(msg) {
	if(!cur_frm.ss_html)
		cur_frm.ss_html = $a(cur_frm.fields_dict['activity_log'].wrapper,'div');
	if(msg) {
		cur_frm.ss_html.innerHTML =
			'<div class="padding"><h4>'+__("Activity Log:")+'</h4>'+msg+'</div>';
	} else {
		cur_frm.ss_html.innerHTML = "";
	}
}

var in_progress = false;

frappe.ui.form.on('Payroll Entry', {
	onload: function (frm) {
		frm.doc.posting_date = frappe.datetime.nowdate();
		frm.toggle_reqd(['payroll_frequency'], !frm.doc.salary_slip_based_on_timesheet);
		
	},

	refresh: function(frm) {
		
		
		
		if (frm.doc.__islocal) {
			frm.trigger("set_start_end_dates");
		}
		if (frm.doc.docstatus == 0 && !frm.doc.__islocal) {
			if (frm.custom_buttons) frm.clear_custom_buttons();
			var slip_status = {'draft':1,'submitted':0};
			// frm.events.add_context_buttons(frm);
			frm.events.add_salary_slip_buttons(frm,slip_status);

		}
		
		
	},

	add_context_buttons: function(frm) {
		frappe.call({
			method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.payroll_entry_has_created_slips',
			args: {
				'name': frm.doc.name
			},
			callback: function(r) {
				if(r.message) {
					frm.events.add_salary_slip_buttons(frm, r.message);
					if(r.message.submitted){
						frm.events.add_bank_entry_button(frm);
					}
				}
			}
		});
	},

	add_salary_slip_buttons: function(frm, slip_status) {
		if (!slip_status.draft && !slip_status.submitted) {
			return;
		} else {
			frm.add_custom_button(__("View Salary Slips"),
				function() {
					frappe.set_route(
						'List', 'Salary Slip', 
						{	
							"start_date": frm.doc.start_date
						}
					);
					
					
				}
			);
			frm.add_custom_button(__("View Attendance Slips"),
				function() {
					frappe.set_route(
						'query-report', 'Attendance%20Slip', ''
					);
				}
			);
		}
		

		// if (slip_status.draft) {
			// frm.add_custom_button(__("Submit Salary Slips"),
				// function() {
					// submit_salary_slip(frm);
				// }
			// ).addClass("btn-primary");
		// }
		
		if (slip_status.draft) {
			frm.add_custom_button(__("Create Salary Slips"),
				function() {
					create_salary_slip(frm);
				}
			).addClass("btn-primary");
		}
		
		if (slip_status.draft) {
			frm.add_custom_button(__("Update Salary Slips"),
				function() {
					update_salary_slip(frm);
				}
			).addClass("btn-primary");
		}
		
		if (slip_status.draft) {
			frm.add_custom_button(__("Salary Slips and Attendance"),
				function() {
					print_salary_slip(frm,"Salary Slip Attendance");
				}, __("Print")
			);
			
			frm.add_custom_button(__("Salary Slips"),
				function() {
					print_salary_slip(frm,"Salary Slip");
				}, __("Print")
			);
		}
		
		
		
		
	},

	add_bank_entry_button: function(frm) {
		frappe.call({
			method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.payroll_entry_has_bank_entries',
			args: {
				'name': frm.doc.name
			},
			callback: function(r) {
				if (r.message && !r.message.submitted) {
					frm.add_custom_button("Bank Entry",
						function() {
							make_bank_entry(frm);
						},
						__('Make')
					);
					frm.page.set_inner_btn_group_as_primary(__('Make'));
				}
			}
		});
	},

	setup: function (frm) {
		frm.set_query("payment_account", function () {
			var account_types = ["Bank", "Cash"];
			return {
				filters: {
					"account_type": ["in", account_types],
					"is_group": 0,
					"company": frm.doc.company
				}
			};
		}),
		frm.set_query("cost_center", function () {
			return {
				filters: {
					"is_group": 0,
					company: frm.doc.company
				}
			};
		}),
		frm.set_query("project", function () {
			return {
				filters: {
					company: frm.doc.company
				}
			};
		});
	},

	payroll_frequency: function (frm) {
		frm.trigger("set_start_end_dates");
		frm.set_value('employees', []);
	},

	company: function (frm) {
		frm.set_value('employees', []);
		frm.set_value('cost_center','Main - '+frappe.get_abbr(frm.doc.company,5))
		
	},

	department: function (frm) {
		frm.set_value('employees', []);
	},

	designation: function (frm) {
		frm.set_value('employees', []);
	},

	branch: function (frm) {
		frm.set_value('employees', []);
	},

	start_date: function (frm) {
		if(!in_progress && frm.doc.start_date){
			frm.trigger("set_end_date");
		}else{
			// reset flag
			in_progress = false;
		}
		frm.set_value('employees', []);
	},

	project: function (frm) {
		frm.set_value('employees', []);
	},

	salary_slip_based_on_timesheet: function (frm) {
		frm.toggle_reqd(['payroll_frequency'], !frm.doc.salary_slip_based_on_timesheet);
	},

	set_start_end_dates: function (frm) {
		if (!frm.doc.salary_slip_based_on_timesheet) {
			frappe.call({
				method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.get_start_end_dates',
				args: {
					payroll_frequency: frm.doc.payroll_frequency,
					start_date: frm.doc.posting_date
				},
				callback: function (r) {
					if (r.message) {
						in_progress = true;
						frm.set_value('start_date', r.message.start_date);
						frm.set_value('end_date', r.message.end_date);
					}
				}
			});
		}
	},

	set_end_date: function(frm){
		frappe.call({
			method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.get_end_date',
			args: {
				frequency: frm.doc.payroll_frequency,
				start_date: frm.doc.start_date
			},
			callback: function (r) {
				if (r.message) {
					frm.set_value('end_date', r.message.end_date);
				}
			}
		});
	},
});

// Submit salary slips

const submit_salary_slip = function (frm) {
	frappe.confirm(__('This will submit Salary Slips and create accrual Journal Entry. Do you want to proceed?'),
		function() {
			frappe.call({
				method: 'submit_salary_slips',
				args: {},
				callback: function() {frm.events.refresh(frm);},
				doc: frm.doc,
				freeze: true,
				freeze_message: 'Submitting Salary Slips and creating Journal Entry...'
			});
		},
		function() {
			if(frappe.dom.freeze_count) {
				frappe.dom.unfreeze();
				frm.events.refresh(frm);
			}
		}
	);
};

cur_frm.cscript.get_employee_details = function (doc) {
	var callback = function (r) {
		if (r.docs[0].employees){
			cur_frm.refresh_field('employees');
		}
	};
	return $c('runserverobj', { 'method': 'fill_employee_details', 'docs': doc }, callback);
};

let make_bank_entry = function (frm) {
	var doc = frm.doc;
	if (doc.company && doc.start_date && doc.end_date) {
		return frappe.call({
			doc: cur_frm.doc,
			method: "make_payment_entry",
			callback: function (r) {
				if (r.message)
					var doc = frappe.model.sync(r.message)[0];
				frappe.set_route("Form", doc.doctype, doc.name);
			}
		});
	} else {
		frappe.msgprint(__("Company, From Date and To Date is mandatory"));
	}
};

// Create salary slip
// -----------------------
const create_salary_slip = function (frm) {
	var doc = frm.doc;
	cur_frm.cscript.display_activity_log("");
	var callback = function(r, rt){
		if (r.message)
			cur_frm.cscript.display_activity_log(r.message);
	}
	return $c('runserverobj', { 'method': 'create_salary_slips', 'docs': doc }, callback);
}

const update_salary_slip = function (frm) {
	var doc = frm.doc;
	cur_frm.cscript.display_activity_log("");
	
		frappe.call({
				doc: cur_frm.doc,
				method: "update_salary_slips",
				args: {
					start_date: doc.start_date,
					end_date: doc.end_date
				},
				freeze: true,
				callback: function(r) {
					if (r.message)
						cur_frm.cscript.display_activity_log(r.message);
				}
			});
}

const print_salary_slip = function (frm,format) {
	
	var doc = frm.doc;
	if(doc.company && doc.start_date && doc.end_date){
		var callback = function(r, rt){

			if (r.message)
			{
				var docname = [];

				r.message.forEach(function (element, index) {
					docname.push(element[0]);
				});
				
				if(docname.length >= 1){
					var json_string = JSON.stringify(docname);								
					var w = window.open("/api/method/frappe.utils.print_format.download_multi_pdf?"
						+"doctype="+encodeURIComponent("Salary Slip")
						+"&name="+encodeURIComponent(json_string)
						+"&format="+encodeURIComponent(format)
						+"&orientation="+encodeURIComponent("Portrait")
						+"&no_letterhead="+"0");
					if(!w) {
						msgprint(__("Please enable pop-ups")); return;
					}
				}
			}
		}

		return $c('runserverobj', args={'method':'print_salary_slips','docs':doc},callback);

		
    } else {
  	  msgprint(__("Company and dates are mandatory"));
    }
};


