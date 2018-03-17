// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt



frappe.provide("erpnext.hr");

erpnext.hr.AttendanceControlPanel = frappe.ui.form.Controller.extend({
	onload: function() {
		this.frm.set_value("att_fr_date", frappe.datetime.get_today());
		this.frm.set_value("att_to_date", frappe.datetime.get_today());
		this.frm.set_value("import_settings", "default");

	},

	refresh: function() {
		this.frm.disable_save();
		this.show_upload();
	},

	get_template:function() {
		if(!this.frm.doc.att_fr_date || !this.frm.doc.att_to_date) {
			frappe.msgprint(__("Attendance From Date and Attendance To Date is mandatory"));
			return;
		}
		window.location.href = repl(frappe.request.url +
			'?cmd=%(cmd)s&from_date=%(from_date)s&to_date=%(to_date)s', {
				cmd: "erpnext.hr.doctype.upload_attendance.upload_attendance.get_template",
				from_date: this.frm.doc.att_fr_date,
				to_date: this.frm.doc.att_to_date,
			});
	},

	show_upload: function() {
		var me = this;
		var $wrapper = $(cur_frm.fields_dict.upload_html.wrapper).empty();
		
		
		// upload
		frappe.upload.make({
			parent: $wrapper,
			get_params: function() {
				return {
					import_settings: cur_frm.doc.import_settings
				}
			},
			args: {
				method: 'erpnext.hr.doctype.upload_attendance.upload_attendance.upload'
			},
			no_socketio: true,
			sample_url: "e.g. http://example.com/somefile.csv",
			callback: function(attachment, r) {
				var $log_wrapper = $(cur_frm.fields_dict.import_log.wrapper).empty();
				if(!r.messages) r.messages = [];
				
				r.messages = $.map(r.message.messages, function(v) {
						var msg = v.replace("Inserted", "Valid")
							.replace("Updated", "Valid").split("<");
						if (msg.length > 1) {
							v = msg[0] + (msg[1].split(">").slice(-1)[0]);
						} else {
							v = msg[0];
						}
						return v;
					});
				
				// replace links if error has occured
				if(r.exc || r.error || r.message.error) {
					var $p = $('<p>').html(["<h4 style='color:red'>"+__("Import Failed! Scroll Down To Find Error")+"</h4>"]).appendTo($log_wrapper);
					$p = $('<p>').html(["<h4 style='color:red'>"+r.message.messages.length+__(" Records")+"</h4>"]).appendTo($log_wrapper);
				}
				else {
					var $p = $('<p>').html(["<h4 style='color:green'>"+__("Import Details!")+"</h4>"]).appendTo($log_wrapper);
					$p = $('<p>').html(["<h4 style='color:green'>"+r.message.messages.length+__(" Records")+"</h4>"]).appendTo($log_wrapper);
				}
				
				
				
				$.each(r.messages, function(i, v) {
				var $p = $('<p>').html(v).appendTo($log_wrapper);
					if(v.substr(0,5)=='Error') {
						$p.css('color', 'red');
					} else if(v.substr(0,8)=='Inserted') {
						$p.css('color', 'green');
					} else if(v.substr(0,7)=='Updated') {
						$p.css('color', 'green');
					} else if(v.substr(0,5)=='Valid') {
						$p.css('color', '#777');
					}
				});
					
					
				

				
			},
			is_private: true
		});
		
		// rename button
		
		$wrapper.find(".attach-btn").html('Upload and Import');

	}
})

cur_frm.cscript = new erpnext.hr.AttendanceControlPanel({frm: cur_frm});
