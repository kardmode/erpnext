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
		if (frm.doc.reference_doctype == "Project"){
			frm.set_query('reference_name', function(doc) {
				return {
					filters: { 'docstatus': 0, 'customer':doc.customer,'company':doc.company}
				}
			});
		}else{
			frm.set_query('reference_name', function(doc) {
				return {
					filters: { 'docstatus': 0 , 'customer':doc.customer,'company':doc.company}
				}
			});
			
		}
		
		if (!frm.doc.company)
			frm.set_value("company",frappe.defaults.get_default('company') ? frappe.defaults.get_default('company'): "");
		
	},
	refresh: function(frm) {
		frm.add_custom_button(__("Get Invoices"), function() {
				frm.events.get_invoice(frm);
			});
       frm.trigger("calculate_total_payment_requests");
    },

	calculate_total_payment_requests: function(frm) {
		var total_payment_requests = 0;
		$.each(frm.doc.payment_requests, function(i, d) {
				total_payment_requests += flt(d.amount);
			});
		if (total_payment_requests > flt(frm.doc.grand_total)){
			// frappe.msgprint("Total Payment Request is greater than project total");
			frm.set_value("advance_required",total_payment_requests);
		} else{
			frm.set_value("advance_required",total_payment_requests);
		}
    },
	reference_doctype: function(frm) {
		if (frm.doc.reference_name){
			frm.set_value("reference_name","");
		}
		
		if (frm.doc.reference_doctype == "Project"){
			frm.set_query('reference_name', function(doc) {
				return {
					filters: { 'docstatus': 0, 'customer':doc.customer,'company':doc.company}
				}
			});
		}else{
			frm.set_query('reference_name', function(doc) {
				return {
					filters: { 'docstatus': 0, 'customer':doc.customer,'company':doc.company}
				}
			});
			
		}
		
	},
	get_invoice: function(frm) {
		
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Get Invoices From Project"),
			fields: [
				{fieldname:'project', fieldtype:'Link', options: 'Project', label: __('Project'),
				get_query: function() {
					return {
						filters: [["Project", 'company', '=', cur_frm.doc.company],
						["Project", 'customer', '=', cur_frm.doc.customer]]
					};
				},
				},
				{fieldname:'clear_invoices', fieldtype:'Check', label: __('Clear Previous Invoices')},
				// {fieldname:'base_variable', fieldtype:'Section Break'},
			]
		});
		dialog.set_primary_action(__("Add"), function() {
		
			var filters = dialog.get_values();
			if (filters.clear_invoices){
					frm.set_value("invoices",[]);
				}
			if (filters.project){
				
				frappe.call({
					doc: frm.doc,
					args: {"doctype": "Project","docname": filters.project},
					method: "get_doc_info",
					callback:function(r){
						frm.refresh();
						cur_frm.dirty();
						dialog.hide();
					}
				});
			}
			else{
				dialog.hide();
			}
		});
		dialog.show();
		
		
	},
	
	get_invoices: function(frm) {
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
	
	// company: function(frm) {
		// var company = locals[':Company'][frm.doc.company];
		// if(!frm.doc.letter_head && company.default_letter_head) {
			// frm.set_value('letter_head', company.default_letter_head);
		// }
	// },
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

frappe.ui.form.on("PR Invoice", {
	sales_invoice: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if (d.sales_invoice){
			frappe.call({
				doc: cur_frm.doc,
				args: {"doctype": "Sales Invoice","docname": d.sales_invoice},
				method: "get_invoice_info",
				callback:function(r){
					if(r.message[0]){
						var invoice = r.message[0]
					
						frappe.model.set_value(d.doctype, d.name, "project", invoice.project);
						frappe.model.set_value(d.doctype, d.name, "posting_date", invoice.posting_date);
						frappe.model.set_value(d.doctype, d.name, "total_amount", invoice.total_amount);
						frappe.model.set_value(d.doctype, d.name, "outstanding_amount", invoice.outstanding_amount);
						frappe.model.set_value(d.doctype, d.name, "title", invoice.title);
					}
					if(d.sales_invoice)
						calculate_totals(frm,cdt,cdn);
					
				}
			});
		}
		
	},
	
	invoices_add:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		
		if(d.sales_invoice)
			calculate_totals(frm,cdt,cdn);
	},
	
	invoices_remove:function(frm, cdt, cdn) {
		calculate_totals(frm,cdt,cdn);
			
		
	},
});

frappe.ui.form.on("Payment Requests", {
    percent: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if (d.percent)
		{
			amount = flt(frm.doc.grand_total) * flt(d.percent / 100);
			d.amount = amount;
			refresh_field("payment_requests");
			frm.trigger("calculate_total_payment_requests");
			
		}
		
    },
	amount: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if (d.amount)
		{
			percent = flt(d.amount * 100) / flt(frm.doc.grand_total) || 0;
			d.percent = percent;
			refresh_field("payment_requests");
			frm.trigger("calculate_total_payment_requests");
		}
    },
})

cur_frm.fields_dict['invoices'].grid.get_field('sales_invoice').get_query = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if(cur_frm.doc.customer){
		
		return{
			filters: {
				'customer': cur_frm.doc.customer,
				'company':cur_frm.doc.company
			}
		}
	}
	
	
}

var calculate_totals = function(frm, cdt, cdn) {
	var invoices = frm.doc.invoices;
	var grand_total = 0;
	var outstanding_amount = 0;
	var total_advance = 0;
	var projects = [];
	for(var i=0;i<invoices.length;i++) {
		if(projects.indexOf(invoices[i].project)<0)
		{
			projects.push(invoices[i].project);
		}
		grand_total = grand_total + flt(invoices[i].total_amount);
		outstanding_amount = outstanding_amount + flt(invoices[i].outstanding_amount);

	}
	total_advance = flt(grand_total)-flt(outstanding_amount);
	
	var subject = projects.join(', ');
	
	frm.set_value("grand_total",grand_total);
	frm.set_value("outstanding_amount",outstanding_amount);
	frm.set_value("total_advance",total_advance);
	frm.set_value("subject",subject);
	cur_frm.dirty();
}

