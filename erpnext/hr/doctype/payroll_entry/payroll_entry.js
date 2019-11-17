// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

cur_frm.cscript.display_activity_log = function(msg,activity) {
	
	
	if(msg) {
		var new_msg = '<p class="padding">'+ frappe.datetime.now_date() +"  " 
			+ frappe.datetime.now_time() + ": " + msg +'</p>';
	
		var final_msg = cur_frm.doc.mrp_activity_log + new_msg;
		cur_frm.set_value("mrp_activity_log",final_msg);
			
	} else {
		// cur_frm.set_value("mrp_activity_log","");
	}
}


/* cur_frm.cscript.display_activity_log = function(msg,activity) {
	var ss_html = $a(cur_frm.fields_dict['activity_log'].wrapper,'div');
	if(msg) {
		ss_html.innerHTML =
			'<div class="padding"><h4>'+ frappe.datetime.now_date() +"  " 
			+ frappe.datetime.now_time() + ": " + activity + '</h4>'+msg+'</div>';
	} else {
		// ss_html.innerHTML = "";
	}
} */

var in_progress = false;

frappe.ui.form.on('Payroll Entry', {
	onload: function (frm) {
		if (!frm.doc.posting_date) {
			frm.doc.posting_date = frappe.datetime.nowdate();
		}
		frm.toggle_reqd(['payroll_frequency'], !frm.doc.salary_slip_based_on_timesheet);
		
		frm.set_query("department", function() {
			return {
				"filters": {
					"company": frm.doc.company,
				}
			};
		});
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

		if (frm.doc.docstatus == 0) {
			if(!frm.is_new()) {
				frm.page.clear_primary_action();
				frm.add_custom_button(__("Get Employees"),
					function() {
						frm.events.get_employee_details(frm);
					}
				).toggleClass('btn-primary', !(frm.doc.employees || []).length);
			}
			if ((frm.doc.employees || []).length) {
				frm.page.set_primary_action(__('Create Salary Slips'), () => {
					frm.save('Submit');
				});
			}
		}
			
		
		
	},
	
	get_employee_details: function (frm) {
		return frappe.call({
			doc: frm.doc,
			method: 'fill_employee_details',
			callback: function(r) {
				if (r.docs[0].employees){
					frm.save();
					frm.refresh();
					if(r.docs[0].validate_attendance){
						render_employee_attendance(frm, r.message);
					}
				}
			}
		})
	},
	
	create_salary_slips: function(frm) {
		check_saved(frm);
		frappe.confirm(__('This will create Salary Slips. Do you want to proceed?'),
			function() {
				frappe.call({
					method: 'create_salary_slips',
					args: {},
					callback: function(r) {
					
					
						// frm.events.refresh(frm);
						if (r.message)
						{	
						
							if(r.message[0] == 0)
							{
								msg = "No Salary Slips Created";
								frappe.msgprint(__(r.message[1])); 
							}
							else
							{
								msg = r.message;
								cur_frm.cscript.display_activity_log(r.message[1],"Created");
								cur_frm.save();
								
							}
								
							
							
						}
						
					},
					doc: frm.doc,
					freeze: true,
					freeze_message: 'Creating Salary Slips...'
				});
			},
			function() {
				if(frappe.dom.freeze_count) {
					frappe.dom.unfreeze();
					frm.events.refresh(frm);
				}
			}
		);
	},
	
	// create_salary_slips: function(frm) {
		// frm.call({
			// doc: frm.doc,
			// method: "create_salary_slips",
			// callback: function(r) {
				// frm.refresh();
				// frm.toolbar.refresh();
			// }
		// })
	// },

	
	update_salary_slips: function(frm) {
		
		check_saved(frm);
		frappe.confirm(__('This will update Salary Slips. Do you want to proceed?'),
			function() {

				frappe.call({
					doc: frm.doc,
					method: "update_salary_slips",
					args: {
					},
					callback: function(r) {
						if (r.message)
						{
							if(r.message[0] == 0)
							{
								msg = "No Salary Slips Updated";
								frappe.msgprint(__(msg)); 
							}
							else
							{
								msg = r.message[1] + " Entries Updated";
								frappe.msgprint(__(msg)); 
								// cur_frm.cscript.display_activity_log(msg,"Updated");
								// cur_frm.save();
								
							}

						}
							
					},
					freeze: true,
					freeze_message: 'Updating Salary Slips...'
				});
			},
			function() {
				if(frappe.dom.freeze_count) {
					frappe.dom.unfreeze();
					frm.events.refresh(frm);
				}
			}
		);
	},
	
	delete_duplicate_salary_slips: function(frm) {
		
		check_saved(frm);
		frappe.confirm(__('This will delete duplicate Salary Slips. Do you want to proceed?'),
			function() {

				frappe.call({
					doc: frm.doc,
					method: "delete_duplicate_salary_slips",
					args: {
					},
					callback: function(r) {
						if (r.message)
						{
							if(r.message[0] == 0)
							{
								msg = "No Salary Slips Deleted";
								frappe.msgprint(__(msg)); 
							}
							else
							{
								msg = r.message[1] + " Entries Deleted";
								frappe.msgprint(__(msg)); 
								// cur_frm.cscript.display_activity_log(msg,"Updated");
								// cur_frm.save();
								
							}

						}
							
					},
					freeze: true,
					freeze_message: 'Deleted Duplicate Salary Slips...'
				});
			},
			function() {
				if(frappe.dom.freeze_count) {
					frappe.dom.unfreeze();
					frm.events.refresh(frm);
				}
			}
		);
	},
	
	
	print_salary_slips: function(frm,format) {
		
		check_saved(frm);
		if(frm.doc.company && frm.doc.start_date && frm.doc.end_date)
		{
			frappe.confirm(__('This will print Salary Slips. Do you want to proceed?'),
				function() {
					
					frappe.call({
						doc: frm.doc,
						method: "print_salary_slips",
						args: {
						},
						callback: function(r){
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
										frappe.msgprint(__("Please enable pop-ups")); return;
									}
								}
							}
						},
						freeze: true,
						freeze_message: 'Printing Salary Slips...'
					});
				},
				function() {
					if(frappe.dom.freeze_count) {
						frappe.dom.unfreeze();
						frm.events.refresh(frm);
					}
				}
			);
			
		} else {
		  frappe.msgprint(__("Company and dates are mandatory"));
		}
	},
	
	add_context_buttons: function(frm) {
		frappe.call({
			method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.payroll_entry_has_created_slips',
			args: {
				'name': frm.doc.name
			},
			callback: function(r) {
				if (r.docs[0].employees){
					frm.save();
					frm.refresh();
					if(r.docs[0].validate_attendance){
						render_employee_attendance(frm, r.message);
					}
				}
			}
		})
	},
	add_salary_slip_buttons: function(frm, slip_status) {
		if (!slip_status.draft && !slip_status.submitted) {
			return;
		} else {
			
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
					frm.events.create_salary_slips(frm);
				}
			).addClass("btn-primary");
		}
		
		if (slip_status.draft) {
			frm.add_custom_button(__("Update"),
				function() {
					frm.events.update_salary_slips(frm);
				}, __("Modify Existing Salaries")
			);
			
			frm.add_custom_button(__("Delete Duplicates"),
				function() {
					frm.events.delete_duplicate_salary_slips(frm);
				}, __("Modify Existing Salaries")
			);
		}
	
		
		if (slip_status.draft) {
			frm.add_custom_button(__("Salary Slip and Attendance"),
				function() {
					frm.events.print_salary_slips(frm,"Salary Slip Attendance");
				}, __("Print")
			);
			
			frm.add_custom_button(__("Salary Slip"),
				function() {
					frm.events.print_salary_slips(frm,"Salary Slip");
				}, __("Print")
			);
			
			
			frm.add_custom_button(__("Salary Slips"),
				function() {
					frappe.set_route(
						'List', 'Salary Slip', 
						{	
							"start_date": frm.doc.start_date,
							"company":frm.doc.company,
						}
					);
					
					
				}, __("View")
			);
			
			
			
			
			frm.add_custom_button(__("Attendance Slips"),
				function() {
					frappe.set_route(
						'query-report', 'Attendance Slip', 
						{	
							"month":["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
				"Dec"][frappe.datetime.str_to_obj(frm.doc.start_date).getMonth()],
							"company":frm.doc.company,
						}
					);
				}, __("View")
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
					frm.add_custom_button("Make Bank Entry", function() {
						make_bank_entry(frm);
					}).addClass("btn-primary");
				}
			}
		});
	},

	setup: function (frm) {
		frm.add_fetch('company', 'cost_center', 'cost_center');

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
		frm.events.clear_employee_table(frm);
	},

	company: function (frm) {
		frm.set_value('employees', []);
		frm.set_value('cost_center','Main - '+frappe.get_abbr(frm.doc.company,5))
		
		// frm.events.clear_employee_table(frm);
	},

	department: function (frm) {
		frm.events.clear_employee_table(frm);
	},

	designation: function (frm) {
		frm.events.clear_employee_table(frm);
	},

	branch: function (frm) {
		frm.events.clear_employee_table(frm);
	},

	start_date: function (frm) {
		if(!in_progress && frm.doc.start_date){
			frm.trigger("set_end_date");
		}else{
			// reset flag
			in_progress = false;
		}
		frm.events.clear_employee_table(frm);
	},

	project: function (frm) {
		frm.events.clear_employee_table(frm);
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

	validate_attendance: function(frm){
		if(frm.doc.validate_attendance && frm.doc.employees){
			frappe.call({
				method: 'validate_employee_attendance',
				args: {},
				callback: function(r) {
					render_employee_attendance(frm, r.message);
				},
				doc: frm.doc,
				freeze: true,
				freeze_message: 'Validating Employee Attendance...'
			});
		}else{
			frm.fields_dict.attendance_detail_html.html("");
		}
	},

	clear_employee_table: function (frm) {
		frm.clear_table('employees');
		frm.refresh();
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

let make_bank_entry = function (frm) {
	var doc = frm.doc;
	if (doc.company && doc.start_date && doc.end_date && doc.payment_account) {
		return frappe.call({
			doc: cur_frm.doc,
			method: "make_payment_entry",
			callback: function() {
				frappe.set_route(
					'List', 'Journal Entry', {"Journal Entry Account.reference_name": frm.doc.name}
				);
			},
			freeze: true,
			freeze_message: __("Creating Payment Entries......")
		});
	} else {
		frappe.msgprint(__("Company, Payment Account, From Date and To Date is mandatory"));
	}
};

const check_saved = function (frm) {
	if (frm.is_dirty())
	{
		 frappe.throw(__("Form Needs To Be Saved."));
	}

};


let render_employee_attendance = function(frm, data) {
	frm.fields_dict.attendance_detail_html.html(
		frappe.render_template('employees_to_mark_attendance', {
			data: data
		})
	);
}
