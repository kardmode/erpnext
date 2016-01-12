// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.add_fetch('employee', 'company', 'company');
cur_frm.add_fetch('employee', 'employee_name', 'employee_name');

cur_frm.cscript.onload = function(doc, cdt, cdn) {
	if(doc.__islocal) {
		doc.att_date = get_today();
		doc.arrival_time = "05:30:00";
		doc.departure_time = "23:30:00";
		refresh_many(['att_date','arrival_time','departure_time']);
		calculate_all(doc,cdt,cdn);
	}
}

// set hours if to_time is updated
frappe.ui.form.on("Attendance", "att_date", function(frm) {
	calculate_all(frm.doc,frm.dt,frm.dn);
});

// set hours if to_time is updated
frappe.ui.form.on("Attendance", "arrival_time", function(frm) {
	calculate_all(frm.doc,frm.dt,frm.dn);
});
// set hours if to_time is updated
frappe.ui.form.on("Attendance", "departure_time", function(frm) {
	calculate_all(frm.doc,frm.dt,frm.dn);
});

var calculate_all = function(doc, dt, dn) {
	return $c_obj(doc, 'calculate_total_hours','',function(r, rt) {
		refresh_many(['working_time','normal_time','overtime','overtime_fridays','overtime_holidays','status']);
	});
}

cur_frm.fields_dict.employee.get_query = function(doc,cdt,cdn) {
	return{
		query: "erpnext.controllers.queries.employee_query"
	}	
}
