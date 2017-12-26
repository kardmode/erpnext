// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.add_fetch('employee', 'company', 'company');
cur_frm.add_fetch('time_sheet', 'total_hours', 'working_hours');


frappe.ui.form.on("Salary Slip", {
	setup: function(frm) {
		frm.fields_dict["timesheets"].grid.get_field("time_sheet").get_query = function(){
			return {
				filters: {
					employee: frm.doc.employee
				}
			}
		}
		frm.set_query("salary_component", "earnings", function() {
			return {
				filters: {
					type: "earning"
				}
			}
		})
		frm.set_query("salary_component", "deductions", function() {
			return {
				filters: {
					type: "deduction"
				}
			}
		})
	},


	/* start_date: function(frm){
		if(frm.doc.start_date){
			frm.trigger("set_end_date");
		}
	},

	set_end_date: function(frm){
		frappe.call({
			method: 'erpnext.hr.doctype.process_payroll.process_payroll.get_end_date',
			args: {
				frequency: frm.doc.payroll_frequency,
				start_date: frm.doc.start_date
			},
			callback: function (r) {
				if (r.message) {
					frm.set_value('end_date', r.message.end_date);
				}
			}
		})
	}, */

	company: function(frm) {
		var company = locals[':Company'][frm.doc.company];
		if(!frm.doc.letter_head && company.default_letter_head) {
			frm.set_value('letter_head', company.default_letter_head);
		}
	},

	refresh: function(frm) {
		frm.trigger("toggle_fields");
		frm.trigger("toggle_reqd_fields");
		// var salary_detail_fields = ['formula', 'abbr', 'statistical_component'];
		// cur_frm.fields_dict['earnings'].grid.set_column_disp(salary_detail_fields,false);
		// cur_frm.fields_dict['deductions'].grid.set_column_disp(salary_detail_fields,false);
	},	

	salary_slip_based_on_timesheet: function(frm) {
		frm.trigger("toggle_fields");
		// frm.set_value('start_date', '');
	},
	
	payroll_frequency: function(frm) {
		frm.trigger("toggle_fields");
		// frm.set_value('start_date', '');
	},

	toggle_fields: function(frm) {
		frm.toggle_display(['hourly_wages', 'timesheets'],
			cint(frm.doc.salary_slip_based_on_timesheet)==1);

		frm.toggle_display(['payment_days', 'total_working_days', 'leave_without_pay'],
			frm.doc.payroll_frequency!="");
	},
	
	set_start_end_dates: function(frm) {
		if (!frm.doc.salary_slip_based_on_timesheet){
			frappe.call({
				method:'erpnext.hr.doctype.process_payroll.process_payroll.get_start_end_dates',
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
	
})

frappe.ui.form.on('Salary Detail', {
	earnings_remove: function(frm, dt, dn) {
		calculate_earning_total(frm.doc, dt, dn);
		calculate_net_pay(frm.doc, dt, dn);
	},
	deductions_remove: function(frm, dt, dn) {
		calculate_ded_total(frm.doc, dt, dn);
		calculate_net_pay(frm.doc, dt, dn);
	},
	
	// salary_component:function(frm, dt, dn) {
		// calculate_all(frm.doc, dt, dn);
	// },
	
})

// On load
// -------------------------------------------------------------------
cur_frm.cscript.onload = function(doc,dt,dn){
	if((cint(doc.__islocal) == 1) && !doc.amended_from){
		doc.payroll_frequency = 'Monthly';
		
		cur_frm.trigger("set_start_end_dates");
		
		refresh_many(['payroll_frequency']);
	}
	// cur_frm.set_df_property("earnings", "read_only", 1);

}





// Get leave details
//---------------------------------------------------------------------
cur_frm.cscript.start_date = function(doc, dt, dn){
	if(doc.start_date){
		return frappe.call({
			method: 'get_emp_and_leave_details',
			doc: locals[dt][dn],
			callback: function(r, rt) {
				cur_frm.refresh();
				calculate_all(doc, dt, dn);
			}
		});
	}
}

cur_frm.cscript.payroll_frequency = cur_frm.cscript.salary_slip_based_on_timesheet = cur_frm.cscript.start_date;
cur_frm.cscript.end_date = cur_frm.cscript.enable_attendance = cur_frm.cscript.start_date;

cur_frm.cscript.employee = function(doc,dt,dn){
	// doc.salary_structure = '';
	cur_frm.cscript.start_date(doc, dt, dn)
}

cur_frm.cscript.leave_without_pay = function(doc,dt,dn){
	if (doc.employee && doc.start_date && doc.end_date) {
		return $c_obj(doc, 'get_leave_details', {"lwp": doc.leave_without_pay}, function(r, rt) {
			var doc = locals[dt][dn];
			cur_frm.refresh();
			calculate_all(doc, dt, dn);
		});
	}
}

var calculate_all = function(doc, dt, dn) {
	calculate_earning_total(doc, dt, dn);
	calculate_ded_total(doc, dt, dn);
	calculate_net_pay(doc, dt, dn);
}

cur_frm.cscript.amount = function(doc,dt,dn){
	var child = locals[dt][dn];
	if(!doc.salary_structure){
		frappe.model.set_value(dt,dn, "default_amount", child.amount)
	}
	calculate_all(doc, dt, dn);
}

cur_frm.cscript.depends_on_lwp = function(doc,dt,dn){
	calculate_earning_total(doc, dt, dn, true);
	calculate_ded_total(doc, dt, dn, true);
	calculate_net_pay(doc, dt, dn);
	refresh_many(['amount','gross_pay', 'rounded_total', 'net_pay', 'loan_repayment']);
};

// Calculate earning total
// ------------------------------------------------------------------------
var calculate_earning_total = function(doc, dt, dn, reset_amount) {
	
	
	var tbl = doc.earnings || [];
	var total_earn = 0;
	for(var i = 0; i < tbl.length; i++){
		if(cint(tbl[i].depends_on_lwp) == 1) {

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
var calculate_ded_total = function(doc, dt, dn, reset_amount) {
	var tbl = doc.deductions || [];
	var total_ded = 0;
	for(var i = 0; i < tbl.length; i++){
		if(cint(tbl[i].depends_on_lwp) == 1) {
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

// Calculate net payable amount
// ------------------------------------------------------------------------
var calculate_net_pay = function(doc, dt, dn) {
	doc.net_pay = flt(doc.gross_pay) - flt(doc.total_deduction);
	doc.rounded_total = Math.ceil(doc.net_pay);
	refresh_many(['net_pay', 'rounded_total']);
}


// validate
// ------------------------------------------------------------------------
cur_frm.cscript.validate = function(doc, dt, dn) {
	calculate_all(doc, dt, dn);
}

cur_frm.fields_dict.employee.get_query = function(doc,cdt,cdn) {
	return{
		query: "erpnext.controllers.queries.employee_query"
	}
}





// Custom

// trigger on arrear
// ------------------------------------------------------------------------
cur_frm.cscript.arrear_amount = function(doc,dt,dn){
	calculate_earning_total(doc, dt, dn);
	calculate_net_pay(doc, dt, dn);
}

// Leave encashment
cur_frm.cscript.encash_leave = function(doc,dt,dn){
	calculate_earnings(doc, dt, dn);	
}

// Loan deduction
cur_frm.cscript.refresh_loan_deduction = function(doc,dt,dn){
	calculate_deductions(doc, dt, dn);
}


// ----------------------------------
var calculate_earnings = function(doc, dt, dn) {
	frappe.call({
			doc: doc,
			method: "sum_components",
			args: {
				component_type:'earnings',
				total_field: 'gross_pay'
			},
			callback: function(r) {
				var doc = locals[dt][dn];
				refresh_many(['earnings','encash_leave','leave_calculation','leave_encashment_amount','amount', 'gross_pay']);
				calculate_net_pay(doc, dt, dn);
			}
		});

	
}

var calculate_deductions = function(doc, dt, dn) {
	
	frappe.call({
			doc: doc,
			method: "sum_components",
			args: {
				component_type:'deductions',
				total_field: 'total_deduction'
			},
			callback: function(r) {
				var doc = locals[dt][dn];
				refresh_many(['deductions','amount','total_deduction']);
				calculate_net_pay(doc, dt, dn);
			}
		});

}
