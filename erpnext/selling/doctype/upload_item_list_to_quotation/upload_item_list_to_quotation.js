// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt


frappe.require("assets/erpnext/js/utils.js");
frappe.provide("erpnext.selling");

erpnext.selling.ItemsControlPanel = frappe.ui.form.Controller.extend({
	onload: function() {

	},

	refresh: function() {
		this.frm.disable_save();
		this.show_upload();
	},

	get_template:function() {
		if(!this.frm.doc.quotation_no) {
			msgprint(__("Quotation No. is mandatory"));
			return;
		}
		window.location.href = repl(frappe.request.url +
			'?cmd=%(cmd)s&quotation_no=%(quotation_no)s', {
				cmd: "erpnext.selling.doctype.upload_item_list_to_quotation.upload_item_list_to_quotation.get_template",
				quotation_no: this.frm.doc.quotation_no,
			});
	},

	show_upload: function() {
		var me = this;
		var $wrapper = $(cur_frm.fields_dict.upload_html.wrapper).empty();

		// upload
		frappe.upload.make({
			parent: $wrapper,
			args: {
				method: 'erpnext.selling.doctype.upload_item_list_to_quotation.upload_item_list_to_quotation.upload'
			},
			callback: function(attachment, r) {
				var $log_wrapper = $(cur_frm.fields_dict.import_log.wrapper).empty();
				console.log(r);
				var messages = r.message.messages
				var error = r.message.error
				if(!r.messages) r.messages = [];
				// replace links if error has occured
				if(error) {
					r.messages = $.map(error, function(v) {
						
						return v;
					});

					r.messages = ["<h4 style='color:red'>"+__("Import Failed!")+"</h4>"]
						.concat(r.messages)
				} else {
					r.messages = ["<h4 style='color:green'>"+__("Import Successful!")+"</h4>"].
						concat(r.message.messages)
				}

				$.each(r.messages, function(i, v) {
					var $p = $('<p>').html(v).appendTo($log_wrapper);
				});
			},
			is_private: false
		});

		// rename button
		$wrapper.find('form input[type="submit"]')
			.attr('value', 'Upload and Import')
	}
	
})

cur_frm.cscript = new erpnext.selling.ItemsControlPanel({frm: cur_frm});
