// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.add_fetch('employee', 'company', 'company');
cur_frm.add_fetch('time_sheet', 'total_hours', 'working_hours');


frappe.ui.form.on("Salary Slip", {
	onload:function(frm){
		if((cint(frm.doc.__islocal) == 1) && !frm.doc.amended_from){
			frm.set_value("payroll_frequency",'Monthly')
			frm.trigger("set_start_end_dates");

		}
	},
	setup: function(frm) {
		$.each(["earnings", "deductions"], function(i, table_fieldname) {
			frm.get_field(table_fieldname).grid.editable_fields = [
				{fieldname: 'salary_component', columns: 6},
				{fieldname: 'amount', columns: 4}
			];
		});

		frm.fields_dict["timesheets"].grid.get_field("time_sheet").get_query = function(){
			return {
				filters: {
					employee: frm.doc.employee
				}
			}
		};

		frm.set_query("salary_component", "earnings", function() {
			return {
				filters: {
					type: "earning"
				}
			}
		});

		frm.set_query("salary_component", "deductions", function() {
			return {
				filters: {
					type: "deduction"
				}
			}
		});

		frm.set_query("employee", function() {
			return{
				query: "erpnext.controllers.queries.employee_query"
			}
		});
	},

	
	start_date: function(frm){
		if(frm.doc.start_date){
			frm.trigger("set_end_date");
			// frm.events.get_emp_and_leave_details(frm);
		}
	},
	
	end_date: function(frm) {
		frm.events.get_emp_and_leave_details(frm);
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

	company: function(frm) {
		var company = locals[':Company'][frm.doc.company];
		if(!frm.doc.letter_head && company.default_letter_head) {
			frm.set_value('letter_head', company.default_letter_head);
		}
	},

	refresh: function(frm) {
		frm.trigger("toggle_fields");
		// frm.trigger("toggle_reqd_fields");
		var salary_detail_fields = ['formula', 'abbr', 'statistical_component'];
		cur_frm.fields_dict['earnings'].grid.set_column_disp(salary_detail_fields,false);
		cur_frm.fields_dict['deductions'].grid.set_column_disp(salary_detail_fields,false);
		
	},

	salary_slip_based_on_timesheet: function(frm) {
		frm.trigger("toggle_fields");
		frm.events.get_emp_and_leave_details(frm);
	},

	payroll_frequency: function(frm) {
		frm.trigger("toggle_fields");
		frm.set_value('end_date', '');
	},

	employee: function(frm) {
		frm.events.get_emp_and_leave_details(frm);
	},

	leave_without_pay: function(frm){
		if (frm.doc.employee && frm.doc.start_date && frm.doc.end_date) {
			return frappe.call({
				method: 'process_salary_based_on_leave',
				doc: frm.doc,
				args: {"lwp": frm.doc.leave_without_pay},
				callback: function(r, rt) {
					frm.refresh();
				}
			});
		}
	},

	toggle_fields: function(frm) {
		frm.toggle_display(['hourly_wages', 'timesheets'], cint(frm.doc.salary_slip_based_on_timesheet)===1);

		frm.toggle_display(['payment_days', 'total_working_days', 'leave_without_pay'],
			frm.doc.payroll_frequency!="");
	},
	
	set_start_end_dates: function(frm) {
		if (!frm.doc.salary_slip_based_on_timesheet){
			frappe.call({
				method:'erpnext.hr.doctype.payroll_entry.payroll_entry.get_start_end_dates',
				args:{
					payroll_frequency: frm.doc.payroll_frequency,
					start_date: frm.doc.start_date || frm.doc.posting_date
				},
				callback: function(r){
					if (r.message){
						frm.set_value('start_date', r.message.start_date);
						frm.set_value('end_date', r.message.end_date);
					}
				}
			})
		}
	},
	get_emp_and_leave_details: function(frm) {
		return frappe.call({
			method: 'get_emp_and_leave_details',
			doc: frm.doc,
			callback: function(r, rt) {
				frm.refresh();
			}
		});
	},
	enable_attendance: function(frm) {
		frm.events.get_emp_and_leave_details(frm);
	},
	
	// Leave encashment
	encash_leave: function(frm) {
		frm.events.get_emp_and_leave_details(frm);
	},
	
	// Loan deduction
	refresh_loan_deduction: function(frm) {
		frm.events.get_emp_and_leave_details(frm);
	},
	
	
	// trigger on arrear
	// ------------------------------------------------------------------------
	arrear_amount: function(frm) {
		//calculate_earning_total(doc, dt, dn);
		//calculate_net_pay(doc, dt, dn);
	}


});


frappe.ui.form.on('Salary Slip Timesheet', {
	time_sheet: function(frm, dt, dn) {
		total_work_hours(frm, dt, dn);
	},
	timesheets_remove: function(frm, dt, dn) {
		total_work_hours(frm, dt, dn);
	}
});

// calculate total working hours, earnings based on hourly wages and totals
var total_work_hours = function(frm, dt, dn) {
	var total_working_hours = 0.0;
	$.each(frm.doc["timesheets"] || [], function(i, timesheet) {
		total_working_hours += timesheet.working_hours;
	});
	frm.set_value('total_working_hours', total_working_hours);

	var wages_amount = frm.doc.total_working_hours * frm.doc.hour_rate;

	frappe.db.get_value('Salary Structure', {'name': frm.doc.salary_structure}, 'salary_component', (r) => {
		var gross_pay = 0.0;
		$.each(frm.doc["earnings"], function(i, earning) {
			if (earning.salary_component == r.salary_component) {
				earning.amount = wages_amount;
				frm.refresh_fields('earnings');
			}
			gross_pay += earning.amount;
		});
		frm.set_value('gross_pay', gross_pay);

		frm.doc.net_pay = flt(frm.doc.gross_pay) - flt(frm.doc.total_deduction);
		frm.doc.rounded_total = Math.round(frm.doc.net_pay);
		refresh_many(['net_pay', 'rounded_total']);
	});
}

// Custom added code
frappe.ui.form.on('Salary Detail', {
	earnings_remove: function(frm, dt, dn) {
		calculate_earning_total(frm.doc);
		calculate_net_pay(frm.doc);
	},
	deductions_remove: function(frm, dt, dn) {
		calculate_ded_total(frm.doc);
		calculate_net_pay(frm.doc);
	},
	
	amount: function(frm, dt, dn) {
		var child = locals[dt][dn];
		if(!frm.doc.salary_structure){
			frappe.model.set_value(dt,dn, "default_amount", child.amount)
		}
		calculate_all(frm.doc);
	},
	depends_on_payment_days: function(frm, dt, dn) {
		calculate_earning_total(frm.doc, true);
		calculate_ded_total(frm.doc, true);
		calculate_net_pay(frm.doc);
		refresh_many(['amount','gross_pay', 'rounded_total', 'net_pay', 'loan_repayment']);
	}
	
});

// Calculate net payable amount
// ------------------------------------------------------------------------
var calculate_net_pay = function(doc) {
	doc.net_pay = flt(doc.gross_pay) - flt(doc.total_deduction);
	doc.rounded_total = Math.ceil(doc.net_pay);
	refresh_many(['net_pay', 'rounded_total']);
}

var calculate_all = function(doc) {
	calculate_earning_total(doc);
	calculate_ded_total(doc);
	calculate_net_pay(doc);
}

// Calculate earning total
// ------------------------------------------------------------------------
var calculate_earning_total = function(doc, reset_amount) {
	var tbl = doc.earnings || [];
	var total_earn = 0;
	for(var i = 0; i < tbl.length; i++){
		if(cint(tbl[i].depends_on_payment_days) == 1) {

			var payment_days = doc.payment_days;
			var total_working_days = doc.total_working_days;		
			if (payment_days == total_working_days)
				payment_days = 30;
			total_working_days = 30;
			
			tbl[i].amount =  Math.round(flt(tbl[i].default_amount)*(flt(payment_days) / 
				cint(total_working_days)));



		} else if(reset_amount) {
			tbl[i].amount = tbl[i].default_amount;
		}
		if(!tbl[i].do_not_include_in_total) {
			total_earn += flt(tbl[i].amount);

		}
	}
	doc.gross_pay = total_earn;

	refresh_many(['earnings', 'amount','gross_pay']);

}

// Calculate deduction total
// ------------------------------------------------------------------------
var calculate_ded_total = function(doc,reset_amount) {
	var tbl = doc.deductions || [];
	var total_ded = 0;
	for(var i = 0; i < tbl.length; i++){
		if(cint(tbl[i].depends_on_payment_days) == 1) {
			var payment_days = doc.payment_days;
			var total_working_days = doc.total_working_days;		
			if (payment_days == total_working_days)
				payment_days = 30;
			total_working_days = 30;
			
			tbl[i].amount =  Math.round(flt(tbl[i].default_amount)*(flt(payment_days) / 
				cint(total_working_days)));



		} else if(reset_amount) {
			tbl[i].amount = tbl[i].default_amount;
		}
		if(!tbl[i].do_not_include_in_total) {
			total_ded += flt(tbl[i].amount);
		}
	}
	doc.total_deduction = total_ded;
	refresh_many(['deductions', 'total_deduction']);
}



