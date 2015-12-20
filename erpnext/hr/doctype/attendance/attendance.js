// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.add_fetch('employee', 'company', 'company');
cur_frm.add_fetch('employee', 'employee_name', 'employee_name');

cur_frm.cscript.onload = function(doc, cdt, cdn) {
	if(doc.__islocal) {
		
		cur_frm.set_value("att_date", get_today());
		doc.arrival = moment(5,"HH").format("HH:mm:ss");
		doc.departure = moment(22,"HH").format("HH:mm:ss");
		doc.shift = 10
		refresh_many(['arrival', 'departure','shift']);
	}
}

// set hours if to_time is updated
frappe.ui.form.on("Attendance", "departure", function(frm) {
	var departure = moment(frm.doc.departure,"hh:mm:ss");
	var arrival = moment(frm.doc.arrival,"hh:mm:ss");
	var shift = moment(frm.doc.shift,"HH");
	var difference = moment(departure).diff(arrival,"minutes") / 60;
	var overtime
	if (difference > frm.doc.shift){
		overtime = flt(difference) - flt(frm.doc.shift);
	}
	else{
		overtime = 0
	}
	cur_frm.set_value("overtime", overtime);
});

// set hours if to_time is updated
frappe.ui.form.on("Attendance", "arrival", function(frm) {
	var departure = moment(frm.doc.departure,"hh:mm:ss");
	var arrival = moment(frm.doc.arrival,"hh:mm:ss");
	var shift = moment(frm.doc.shift,"HH");
	var difference = moment(departure).diff(arrival,"minutes") / 60;
	if (difference > frm.doc.shift){
		overtime = flt(difference) - flt(frm.doc.shift);
	}
	else{
		overtime = 0
	}	
	cur_frm.set_value("overtime", overtime);
	
});


cur_frm.fields_dict.employee.get_query = function(doc,cdt,cdn) {
	return{
		query: "erpnext.controllers.queries.employee_query"
	}	
}
