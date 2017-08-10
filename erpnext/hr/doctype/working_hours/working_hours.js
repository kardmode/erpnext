// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Working Hours', {
	refresh: function(frm) {
	},
	
});

// additional validation on dates
frappe.ui.form.on("Working Hours", "validate", function(frm) {
    if (frm.doc.to_date < frm.doc.from_date) {
        msgprint("To date cannot be before From Date");
        validated = false;
    }

 if (frm.doc.working_hours <= 0 || frm.doc.working_hours > 23.5) {
        msgprint("Working Hours is either too low or too high");
        validated = false;
    }

});

frappe.ui.form.on("Working Hours", {
    working_hours: function(frm) {
var seconds = frm.doc.working_hours*60*60;
var date = new Date(null);
    date.setSeconds(seconds); // specify value for SECONDS here
   var time = date.toISOString().substr(11, 8);

        frm.set_value("working_hours_time",time);
    }
});

//frappe.ui.form.on("Working Hours", {
//    working_hours_time: function(frm) {
//var timefloat = timeStringToFloat(frm.doc.working_hours_time);
//        frm.set_value("working_hours",timefloat);
 //   }
//});

function timeStringToFloat(time) {
  var hoursMinutes = time.split(/[.:]/);
  var hours = parseInt(hoursMinutes[0], 10);
  var minutes = hoursMinutes[1] ? parseInt(hoursMinutes[1], 10) : 0;
  return hours + minutes / 60;
}

function secondsToTime(hrs)
{
	var secs = flt(hrs) * 60 * 60;
    secs = Math.round(secs);
    var hours = Math.floor(secs / (60 * 60));

    var divisor_for_minutes = secs % (60 * 60);
    var minutes = Math.floor(divisor_for_minutes / 60);

    var divisor_for_seconds = divisor_for_minutes % 60;
    var seconds = Math.ceil(divisor_for_seconds);

    var obj = {
        "h": hours,
        "m": minutes,
        "s": seconds
    };
    return obj;
}
