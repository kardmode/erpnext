cur_frm.add_fetch("payment_gateway", "payment_account", "payment_account")
cur_frm.add_fetch("payment_gateway", "payment_gateway", "payment_gateway")
cur_frm.add_fetch("payment_gateway", "message", "message")
cur_frm.add_fetch("payment_gateway", "payment_url_message", "payment_url_message")

frappe.ui.form.on("Payment Request", {
	setup: function(frm) {
		

		/* frm.set_query('project', function(doc) {
			return {
				query: "erpnext.controllers.queries.get_project_name",
				filters: {
					'customer': doc.customer
				}
			}
		}) */
		
		

		
	},
	reference_doctype: function(frm) {
		if (frm.doc.reference_name){
			frm.set_value("reference_name","");
		}
		
		if (frm.doc.reference_doctype == "Project"){
			frm.set_query('reference_name', function(doc) {
				return {
					filters: { 'docstatus': 0 }
				}
			});
		}else{
			frm.set_query('reference_name', function(doc) {
				return {
					filters: { 'docstatus': 1 }
				}
			});
			
		}
		
	},
	
	reference_name: function(frm) {
		if (frm.doc.reference_name){
			frappe.call({
				doc: frm.doc,
				args: {"doctype": frm.doc.reference_doctype,"docname": frm.doc.reference_name},
				method: "get_doc_info",
				callback:function(r){
					frm.refresh();
					cur_frm.dirty();
				}
			});
		}
	},
	
	company: function(frm) {
		var company = locals[':Company'][frm.doc.company];
		if(!frm.doc.letter_head && company.default_letter_head) {
			frm.set_value('letter_head', company.default_letter_head);
		}
	},
	customer: function() {
		erpnext.utils.get_party_details(me.frm, null, null, function(){});
	},
	customer_address: function() {
		erpnext.utils.get_address_display(me.frm, "customer_address");
	},

	shipping_address_name: function() {
		erpnext.utils.get_address_display(me.frm, "shipping_address_name", "shipping_address");
	},
	
	contact_person: function() {
		erpnext.utils.get_contact_details(me.frm);
		},
		
	tc_name: function() {
			cur_frm.trigger('get_terms');
		},
		
	get_terms: function() {
		var me = this;
		if(cur_frm.doc.tc_name) {
			return frappe.call({
				method: 'erpnext.setup.doctype.terms_and_conditions.terms_and_conditions.get_terms_and_conditions',
				args: {
					template_name: cur_frm.doc.tc_name,
					doc: cur_frm.doc
				},
				callback: function(r) {
					if(!r.exc) {
						cur_frm.set_value("terms", r.message);
					}
				}
			});
		}
	},

});

frappe.ui.form.on("Payment Request", "onload", function(frm, dt, dn){
	if (frm.doc.reference_doctype) {
		frappe.call({
			method:"erpnext.accounts.doctype.payment_request.payment_request.get_print_format_list",
			args: {"ref_doctype": frm.doc.reference_doctype},
			callback:function(r){
				set_field_options("print_format", r.message["print_format"])
			}
		})
	}
	
	if (!frm.doc.posting_date) {
				frm.set_value("posting_date", get_today());
			}
	$.each([["customer_address", "customer_filter"],
			["shipping_address_name", "customer_filter"],
			["contact_person", "customer_filter"],
			["customer", "customer"]],
			function(i, opts) {
				if(me.frm.fields_dict[opts[0]])
					me.frm.set_query(opts[0], erpnext.queries[opts[1]]);
			});
	
})

frappe.ui.form.on("Payment Request", "refresh", function(frm) {
	if(!in_list(["Initiated", "Paid"], frm.doc.status) && !frm.doc.__islocal && frm.doc.docstatus==1){
		/* frm.add_custom_button(__('Resend Payment Email'), function(){
			frappe.call({
				method: "erpnext.accounts.doctype.payment_request.payment_request.resend_payment_email",
				args: {"docname": frm.doc.name},
				freeze: true,
				freeze_message: __("Sending"),
				callback: function(r){
					if(!r.exc) {
						frappe.msgprint(__("Message Sent"));
					}
				}
			});
		}); */
	}
	
	if(!frm.doc.payment_gateway_account && frm.doc.status == "Initiated") {
		frm.add_custom_button(__('Make Payment Entry'), function(){
			frappe.call({
				method: "erpnext.accounts.doctype.payment_request.payment_request.make_payment_entry",
				args: {"docname": frm.doc.name},
				freeze: true,
				callback: function(r){
					if(!r.exc) {
						var doc = frappe.model.sync(r.message);
						frappe.set_route("Form", r.message.doctype, r.message.name);
					}
				}
			});
		}).addClass("btn-primary");
	}
});

