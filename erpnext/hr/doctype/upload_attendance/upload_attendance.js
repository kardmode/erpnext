// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt



frappe.provide("erpnext.hr");

erpnext.hr.AttendanceControlPanel = frappe.ui.form.Controller.extend({
	onload: function() {
		this.frm.set_value("att_fr_date", frappe.datetime.get_today());
		this.frm.set_value("att_to_date", frappe.datetime.get_today());
		this.frm.set_value("import_settings", "default");
		this.frm.set_value("only_show_errors", 1);
		this.frm.trigger("set_start_end_dates");
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
	
	update_attendance: function() {
		var me = this;
		frappe.call({
				method: "erpnext.hr.doctype.upload_attendance.upload_attendance.update_attendance",
				args: {
					start_date: me.frm.doc.start_date,
					end_date: me.frm.doc.end_date
				},
				freeze: true,
				freeze_message: "Please wait ..",
				callback: function(r) {
					var msg = "";
					if(r.message)
						msg = r.message;
					else
						msg = "0 Attendance Records Updated";
					
					
					cur_frm.set_value("update_log",msg);
					frappe.hide_msgprint();
				}
			});
		
		
	},
	
	start_date: function(){
		var me = this;
		if(me.frm.doc.start_date){
			me.frm.trigger("set_end_date");
		}
	},

	set_end_date: function(){
		var me = this;
		frappe.call({
			method: 'erpnext.hr.doctype.payroll_entry.payroll_entry.get_end_date',
			args: {
				frequency: "Monthly",
				start_date: me.frm.doc.start_date
			},
			callback: function (r) {
				if (r.message) {
					me.frm.set_value('end_date', r.message.end_date);
				}
			}
		})
	},
	
	set_start_end_dates: function() {
		var me = this;
		frappe.call({
				method:'erpnext.hr.doctype.payroll_entry.payroll_entry.get_start_end_dates',
				args:{
					payroll_frequency: "Monthly",
					start_date: me.frm.doc.start_date || frappe.datetime.get_today()
				},
				callback: function(r){
					if (r.message){
						me.frm.doc.start_date =  r.message.start_date;
						me.frm.refresh_field("start_date");
						me.frm.set_value('end_date', r.message.end_date);
					}
				}
			})
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
				
				if(r.exc || r.error || r.message.error) {
					r.messages = $.map(r.message.messages, function(v) {
						if(cur_frm.doc.only_show_errors === 1)
						{
							if(v.search(/error/i) > -1)
							{
								return v;
							}
						}
						else{
							var msg = v.replace("Inserted", "Valid").replace("Updated","Valid");
							

							return msg;
						}
						
					});
				
				}
				else{
					r.messages = r.message.messages;
					
				}
				
					
								
				
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
