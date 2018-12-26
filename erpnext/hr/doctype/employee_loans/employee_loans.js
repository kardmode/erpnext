// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.add_fetch('employee', 'employee_name', 'employee_name');
cur_frm.add_fetch('employee', 'company', 'company');

// On load
// -------------------------------------------------------------------
cur_frm.cscript.onload = function(doc,dt,dn){
	if((cint(doc.__islocal) == 1) && !doc.amended_from){

	}
}

// Get employee details
//---------------------------------------------------------------------
cur_frm.cscript.employee = function(doc,dt,dn){
	if (doc.employee) {
	}
}


cur_frm.cscript.transaction_amount = function(doc,dt,dn){
	// calculate_earning_total(doc, dt, dn);
}

// cur_frm.cscript.transaction_type = cur_frm.cscript.transaction_amount;





// Calculate earning total
// ------------------------------------------------------------------------
var calculate_earning_total = function(doc, dt, dn) {
	var tbl = doc.e_loan_transaction || [];

	var total_earn = 0;
	for(var i = 0; i < tbl.length; i++){
		if(tbl[i].transaction_type == "Deduction"){
			total_earn -= flt(tbl[i].transaction_amount);
		}else {
			total_earn += flt(tbl[i].transaction_amount);
		}
	}
	doc.net_balance = total_earn;
	refresh_many(['net_balance']);
}

frappe.ui.form.on("Loan Transaction", "e_loan_transaction_remove", function(frm,dt,dn){
	// calculate_earning_total(frm.doc, dt, dn);
})

frappe.ui.form.on("Loan Transaction", "transaction_date", function(frm,dt,dn){
	// frappe.msgprint("Is the Transaction Date correct? Is it the same month as the salary slip?")
})


cur_frm.fields_dict.employee.get_query = function(doc,cdt,cdn) {
	return{
		query: "erpnext.controllers.queries.employee_query"
	}		
}

