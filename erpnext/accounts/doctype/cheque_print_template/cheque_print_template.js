// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("erpnext.cheque_print");

frappe.ui.form.on('Cheque Print Template', {
	refresh: function(frm) {
		if(!frm.doc.__islocal) {
			frm.add_custom_button(frm.doc.has_print_format?__("Update Print Format"):__("Create Print Format"),
				function() {
					erpnext.cheque_print.view_cheque_print(frm);
				}).addClass("btn-primary");
				
			erpnext.cheque_print.refresh_print_preview(frm);
		}
	},
	is_account_payable: function(frm) {
		erpnext.cheque_print.refresh_print_preview(frm);
	},
	show_account_no: function(frm) {
		erpnext.cheque_print.refresh_print_preview(frm);
	},
	show_signatory: function(frm) {
		erpnext.cheque_print.refresh_print_preview(frm);
	},
	
});


erpnext.cheque_print.refresh_print_preview  = function(frm) {
		$(frm.fields_dict.cheque_print_preview.wrapper).empty()
			
			var signatory = '';
			if(frm.doc.show_signatory){
				signatory = '<span style="top: {{ signatory_from_top_edge }}cm;\
						left: {{ signatory_from_left_edge }}cm;\
						position: absolute;"> Signatory Name </span>\
						';
			}
			var acc_no = '';
			if(frm.doc.show_account_no){
				acc_no = '<span style="top: {{ acc_no_dist_from_top_edge }}cm;\
						left: {{ acc_no_dist_from_left_edge }}cm;\
						position: absolute;"> Acc. No. </span>';
			}
			
			var test_amount =frm.doc.test_amount;
			var symbol = frm.doc.symbol_to_add || '';
			
			frappe.call({
				method: "erpnext.accounts.doctype.cheque_print_template.cheque_print_template.get_total_in_words",
				args:{
					"amount":test_amount
				},
				callback: function(r) {
					if (!r.exe) {
						var amount_in_words = symbol + r.message[1] + symbol;
						var fmt_amount = symbol + r.message[0] + symbol;
						var pay_to = symbol + "Pay To Name" + symbol;
						var template = '<div style="position: relative; overflow-x: scroll;">\
				<div id="cheque_preview" style="width: {{ cheque_width }}cm; \
					height: {{ cheque_height }}cm;\
					background-repeat: no-repeat;\
					background-size: cover;font-size:{{ font_size }}px !important;font-weight:{{ font_weight }};">\
					<span style="top: {{ acc_pay_dist_from_top_edge }}cm;\
						left: {{ acc_pay_dist_from_left_edge }}cm;\
						border-bottom: solid 1px;border-top:solid 1px;\
						position: absolute;"> {{ message_to_show || __("A/C PAYEE ONLY") }} </span>\
					<span style="top: {{ date_dist_from_top_edge }}cm;\
						left: {{ date_dist_from_left_edge }}cm;\
						position: absolute;"> {{ frappe.datetime.obj_to_user() }} </span>'
					+ acc_no +
					'<span style="top: {{ payer_name_from_top_edge }}cm;\
						left: {{ payer_name_from_left_edge }}cm;\
						position: absolute;">'+pay_to+'</span>\
					<span style="top: {{ bearer_dist_from_top_edge }}cm;\
						left: {{ bearer_dist_from_left_edge }}cm;\
						position: absolute;">{{ bearer_symbol  || ""}}</span>\
					<span style="top:{{ amt_in_words_from_top_edge }}cm;\
						left: {{ amt_in_words_from_left_edge }}cm;\
						position: absolute;\
						display: block;\
						width: {{ amt_in_word_width }}cm;\
						line-height: {{ amt_in_words_line_spacing }}cm;\
						text-indent: {{ amt_in_words_indent }}cm;\
						word-wrap: break-word;">\
						'+amount_in_words+'</span>\
					<span style="top: {{ amt_in_figures_from_top_edge }}cm;\
						left: {{ amt_in_figures_from_left_edge }}cm;\
						position: absolute;">'+fmt_amount+'</span>'
					+signatory+'</div>\</div>';
			
						$(frappe.render(template, frm.doc)).appendTo(frm.fields_dict.cheque_print_preview.wrapper)
						
						if (frm.doc.scanned_cheque) {
							$(frm.fields_dict.cheque_print_preview.wrapper).find("#cheque_preview").css('background-image', 'url(' + frm.doc.scanned_cheque + ')');
						}
						
					}
				}
			})
				
			

}
erpnext.cheque_print.view_cheque_print = function(frm) {
	frappe.call({
		method: "erpnext.accounts.doctype.cheque_print_template.cheque_print_template.create_or_update_cheque_print_format",
		args:{
			"template_name": frm.doc.name
		},
		callback: function(r) {
			if (!r.exe && !frm.doc.has_print_format) {
				var doc = frappe.model.sync(r.message);
				frappe.set_route("Form", r.message.doctype, r.message.name);
			}
			else {
				frappe.msgprint(__("Print settings updated in respective print format"))
			}
		}
	})
}
