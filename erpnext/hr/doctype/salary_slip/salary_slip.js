// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.add_fetch('time_sheet', 'total_hours', 'working_hours');
cur_frm.add_fetch('employee', 'company', 'company');


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
	
	// company: function(frm) {
		// var company = locals[':Company'][frm.doc.company];
		// if(!frm.doc.letter_head && company.default_letter_head) {
			// frm.set_value('letter_head', company.default_letter_head);
		// }
	// },

	refresh: function(frm) {
		frm.trigger("toggle_fields")
		frm.trigger("toggle_reqd_fields")
		salary_detail_fields = ['formula', 'abbr', 'statistical_component']
		cur_frm.fields_dict['earnings'].grid.set_column_disp(salary_detail_fields,false);
		cur_frm.fields_dict['deductions'].grid.set_column_disp(salary_detail_fields,false);
	},	

	salary_slip_based_on_timesheet: function(frm) {
		frm.trigger("toggle_fields")
	},
	
	payroll_frequency: function(frm) {
		frm.trigger("toggle_fields")
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
		calculate_all(frm.doc, dt, dn);
	},
	deductions_remove: function(frm, dt, dn) {
		calculate_all(frm.doc, dt, dn);
	}
})

// On load
// -------------------------------------------------------------------
cur_frm.cscript.onload = function(doc,dt,dn){
	if((cint(doc.__islocal) == 1) && !doc.amended_from){
		doc.payroll_frequency = 'Monthly';
		refresh_many(['payroll_frequency']);
	}
	cur_frm.set_df_property("earnings", "read_only", 1);

}


// Get leave details
//---------------------------------------------------------------------
cur_frm.cscript.start_date = function(doc, dt, dn){
	return frappe.call({
		method: 'get_emp_and_leave_details',
		doc: locals[dt][dn],
		callback: function(r, rt) {
			cur_frm.refresh();
			console.log(doc.end_date);
			calculate_all(doc, dt, dn);
		}
	});
}

cur_frm.cscript.payroll_frequency = cur_frm.cscript.salary_slip_based_on_timesheet = cur_frm.cscript.start_date;
cur_frm.cscript.end_date = cur_frm.cscript.enable_attendance = cur_frm.cscript.start_date;


cur_frm.cscript.employee = function(doc,dt,dn){
	cur_frm.add_fetch('company', 'default_letter_head', 'letter_head');
	doc.salary_structure = ''
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

			if(tbl[i].salary_component == "Basic Salary"){
				
					
				var payment_days = doc.payment_days;
					
				if (doc.payment_days == doc.total_working_days)
					payment_days = 30;
				var total_working_days = 30;
				tbl[i].amount =  Math.round(tbl[i].default_amount)*(flt(payment_days) / 
					cint(total_working_days)*100)/100;
				cur_frm.refresh_field('amount', tbl[i].name, 'earnings');

			}
			else{
				tbl[i].amount =  Math.round(tbl[i].default_amount)*(flt(doc.payment_days) / 
					cint(doc.total_working_days)*100)/100;
				cur_frm.refresh_field('amount', tbl[i].name, 'earnings');

			}


		} else if(reset_amount) {
			tbl[i].amount = tbl[i].default_amount;
			cur_frm.refresh_field('amount', tbl[i].name, 'earnings');
		}
		total_earn += flt(tbl[i].amount);
	}
	doc.gross_pay = total_earn + flt(doc.arrear_amount) + flt(doc.leave_encashment_amount) + flt(doc.gratuity_encashment);

	refresh_many(['amount','gross_pay']);
}

// Calculate deduction total
// ------------------------------------------------------------------------
var calculate_ded_total = function(doc, dt, dn, reset_amount) {
	var tbl = doc.deductions || [];
	var total_ded = 0;
	for(var i = 0; i < tbl.length; i++){
		if(cint(tbl[i].depends_on_lwp) == 1) {
			tbl[i].amount = Math.round(tbl[i].default_amount)*(flt(doc.payment_days)/cint(doc.total_working_days)*100)/100;
			refresh_field('amount', tbl[i].name, 'deductions');
		} else if(reset_amount) {
			tbl[i].amount = tbl[i].default_amount;
			refresh_field('amount', tbl[i].name, 'deductions');

		}
		total_ded += flt(tbl[i].amount);
	}
	doc.total_deduction = total_ded;
	refresh_field('total_deduction');
}

// Calculate net payable amount
// ------------------------------------------------------------------------
var calculate_net_pay = function(doc, dt, dn) {
	doc.net_pay = flt(doc.gross_pay) - flt(doc.total_deduction);
	doc.rounded_total = Math.ceil(doc.net_pay);
	refresh_many(['net_pay', 'rounded_total']);
}

// trigger on arrear
// ------------------------------------------------------------------------
cur_frm.cscript.arrear_amount = function(doc,dt,dn){
	calculate_earning_total(doc, dt, dn);
	calculate_net_pay(doc, dt, dn);
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


// Table modified
// ------------------------------------------------------------------------

frappe.ui.form.on("Salary Slip Earning", "earnings_remove", function(frm,dt,dn){
	calculate_earning_total(frm.doc, dt, dn);
	calculate_net_pay(frm.doc, dt, dn);
})


frappe.ui.form.on("Salary Slip Deduction", "deductions_remove", function(frm,dt,dn){
	calculate_ded_total(frm.doc, dt, dn);
	calculate_net_pay(frm.doc, dt, dn);
})

frappe.ui.form.on("Salary Slip Earning", "salary_component", function(frm,dt,dn){
	calculate_earnings(doc, dt, dn);	
})

frappe.ui.form.on("Salary Slip Deduction", "salary_component", function(frm,dt,dn){
	
	var doc = locals[dt][dn];
	if (doc.salary_component == "Loan Repayment"){
		frappe.msgprint("Do NOT manually place loan deductions. Go to Employee Loans and input it there. Then open the required salary slip and press refresh loan deduction.");
	}
})

// Custom
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
	return $c_obj(doc, 'calculate_earning_total','',function(r, rt) {
	var doc = locals[dt][dn];
	refresh_many(['earnings','encash_leave','leave_calculation','leave_encashment_amount','amount', 'gross_pay']);
	calculate_net_pay(doc, dt, dn);
	});
}

var calculate_deductions = function(doc, dt, dn) {
	return $c_obj(doc, 'calculate_ded_total','',function(r, rt) {
	var doc = locals[dt][dn];
		refresh_many(['deductions','amount','total_deduction']);
		calculate_net_pay(doc, dt, dn);
	});
}
