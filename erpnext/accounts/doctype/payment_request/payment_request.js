cur_frm.add_fetch("payment_gateway_account", "payment_account", "payment_account")
cur_frm.add_fetch("payment_gateway_account", "payment_gateway", "payment_gateway")
cur_frm.add_fetch("payment_gateway_account", "message", "message")

frappe.ui.form.on("Payment Request", {
	setup: function(frm) {
		
		frm.set_query("party_type", function() {
			return {
				query: "erpnext.setup.doctype.party_type.party_type.get_party_type",
			};
		});
	
		frm.set_query('project', function(doc) {
			var filters = {"company":doc.company};
			if(doc.party_type == "Customer")
			{
				filters["customer"] = frm.doc.party;
			}
			return {
				query: "erpnext.controllers.queries.get_project_name",
				filters:filters
			}
		})
	
	},
	refresh: function(frm) {
		if(!frm.doc.mode_of_payment)
		{
			frm.set_value("mode_of_payment", "Wire Transfer");
		}
		if (!frm.doc.posting_date) {
			frm.set_value("posting_date", get_today());
			frm.set_value("transaction_date", get_today());
		}
		if (!frm.doc.transaction_date) {
			frm.set_value("transaction_date", frm.doc.posting_date);
		}
		
		if(frm.doc.customer)
		{
			if (!frm.doc.party_type) {
				frm.set_value("party_type", "Customer");
			}
			if (!frm.doc.party) {
				frm.set_value("party", frm.doc.customer);
			}
		}
		
		
		
		if(!frm.doc.__islocal && frm.doc.docstatus < 2)
		{
			if (frm.doc.party_type == "Customer" && frm.doc.party)
			{
				frm.add_custom_button(__("Get Invoices"), function() {
					frm.events.get_invoices_from_project(frm);
				});
			}
			frm.trigger("calculate_total_payment_requests");
		}	
		
		
		
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
		
		frm.trigger("calculate_grand_total_payment_requests");
		
    },
	calculate_grand_total_payment_requests: function(frm) {
		var grand_total_requested = 0;
		grand_total_requested = frm.doc.advance_required + frm.doc.vat - frm.doc.additional_discount_amount;
		frm.set_value("grand_total_requested",grand_total_requested);
    },
	get_invoices_from_project: function(frm) {
		
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Get Invoices From Project"),
			fields: [
				{fieldname:'project', fieldtype:'Link', options: 'Project',reqd:1, label: __('Project'),
					get_query: function() {
						return {
							filters: [["Project", 'company', '=', cur_frm.doc.company],
							["Project", 'customer', '=', cur_frm.doc.party]]
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
	
	party_type: function(frm) {
		update_queries(frm);	
	
	},
	party: function(frm) {
		frappe.call({
			method: 'erpnext.accounts.party.get_party_details',
			args: {
				party: frm.doc.party,
				party_type: frm.doc.party_type,
			},
			callback: function(r) {
				if(!r.exc) {
					frm.set_value("customer_address",r.message.customer_address || r.message.supplier_address)
					frm.set_value("contact_person",r.message.contact_person)
				}
			}
		});
		
		
		
	},
	customer_address: function(frm) {
		erpnext.utils.get_address_display(me.frm, "customer_address","address_display");
	},
	
	contact_person: function(frm) {
		erpnext.utils.get_contact_details(frm);
	},
		
	tc_name: function(frm) {
		frm.trigger('get_terms');
	},
		
	get_terms: function(frm) {
		var me = this;
		if(frm.doc.tc_name) {
			return frappe.call({
				method: 'erpnext.setup.doctype.terms_and_conditions.terms_and_conditions.get_terms_and_conditions',
				args: {
					template_name: frm.doc.tc_name,
					doc: frm.doc
				},
				callback: function(r) {
					if(!r.exc) {
						frm.set_value("terms", r.message);
					}
				}
			});
		}
	},
	
	vat: function(frm) {
		frm.trigger("calculate_grand_total_payment_requests");
	},
		
	additional_discount_amount: function(frm) {
		frm.trigger("calculate_grand_total_payment_requests");

	},
		
	enable_vat: function(frm) {
		var vat = 0;
		if(frm.doc.enable_vat === 1)
			vat = frm.doc.advance_required * 0.05;
		else
			vat = 0;
		frm.set_value("vat",vat);
				frm.trigger("calculate_grand_total_payment_requests");

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
	update_queries(frm);
})

frappe.ui.form.on("Payment Request", "refresh", function(frm) {

	if(frm.doc.payment_request_type == 'Inward' &&
		!in_list(["Initiated", "Paid"], frm.doc.status) && !frm.doc.__islocal && frm.doc.docstatus==1){
		// frm.add_custom_button(__('Resend Payment Email'), function(){
			// frappe.call({
				// method: "erpnext.accounts.doctype.payment_request.payment_request.resend_payment_email",
				// args: {"docname": frm.doc.name},
				// freeze: true,
				// freeze_message: __("Sending"),
				// callback: function(r){
					// if(!r.exc) {
						// frappe.msgprint(__("Message Sent"));
					// }
				// }
			// });
		// }); 
	}

	if(!frm.doc.payment_gateway_account && frm.doc.status == "Initiated") {
		frm.add_custom_button(__('Create Payment Entry'), function(){
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



frappe.ui.form.on("Payment Request", "is_a_subscription", function(frm) {
	frm.toggle_reqd("payment_gateway_account", frm.doc.is_a_subscription);
	frm.toggle_reqd("subscription_plans", frm.doc.is_a_subscription);

	if (frm.doc.is_a_subscription && frm.doc.reference_doctype && frm.doc.reference_name) {
		frappe.call({
			method: "erpnext.accounts.doctype.payment_request.payment_request.get_subscription_details",
			args: {"reference_doctype": frm.doc.reference_doctype, "reference_name": frm.doc.reference_name},
			freeze: true,
			callback: function(data){
				if(!data.exc) {
					$.each(data.message || [], function(i, v){
						var d = frappe.model.add_child(frm.doc, "Subscription Plan Detail", "subscription_plans");
						d.qty = v.qty;
						d.plan = v.plan;
					});
					frm.refresh_field("subscription_plans");
				}
			}
		});
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
	var vat = 0;
		
	for(var i=0;i<invoices.length;i++) {
		if(projects.indexOf(invoices[i].project)<0)
		{
			projects.push(invoices[i].project);
		}
		grand_total = grand_total + flt(invoices[i].total_amount);
		outstanding_amount = outstanding_amount + flt(invoices[i].outstanding_amount);

	}
	total_advance = flt(grand_total)-flt(outstanding_amount);
		if(frm.doc.enable_vat === 1)
				vat = frm.doc.advance_required * 0.05;
			else
				vat = 0;
				
	var subject = projects.join(', ');
	
	frm.set_value("grand_total",grand_total);
	frm.set_value("outstanding_amount",outstanding_amount);
	frm.set_value("total_advance",total_advance);
	frm.set_value("subject",subject);
	frm.set_value("vat",vat);

	cur_frm.dirty();
}

var update_queries = function(frm)
{
	/* var filter_type = frm.doc.party_type.toLowerCase() + "_filter";
	
	$.each([["customer_address", filter_type],
			["contact_person", filter_type]],
			function(i, opts) {
				if(me.frm.fields_dict[opts[0]])
					me.frm.set_query(opts[0], erpnext.queries[opts[1]]);
	});	 */
}