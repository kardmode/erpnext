// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt


{% include 'selling/sales_common.js' %}

erpnext.selling.QuotationController = erpnext.selling.SellingController.extend({
	validate:function(doc, dt, dn){
		var me = this;
		this._super(doc, dt, dn);
		
		calculate_headers();
		
	},
	
	
	onload: function(doc, dt, dn) {
		var me = this;
		this._super(doc, dt, dn);
		if(doc.customer && !doc.quotation_to)
			doc.quotation_to = "Customer";
		else if(doc.lead && !doc.quotation_to)
			doc.quotation_to = "Lead";

	},
	refresh: function(doc, dt, dn) {
		this._super(doc, dt, dn);

		if(doc.docstatus == 1 && doc.status!=='Lost') {
			cur_frm.add_custom_button(__('Sales Order'),
				cur_frm.cscript['Make Sales Order'], __("Make"));

			if(doc.status!=="Ordered") {
				cur_frm.add_custom_button(__('Lost'),
					cur_frm.cscript['Declare Order Lost'], __("Status"));
			}
			
			cur_frm.page.set_inner_btn_group_as_primary(__("Make"));
		}

		if (this.frm.doc.docstatus===0) {
			cur_frm.add_custom_button(__('Opportunity'),
				function() {
					frappe.model.map_current_doc({
						method: "erpnext.crm.doctype.opportunity.opportunity.make_quotation",
						source_doctype: "Opportunity",
						get_query_filters: {
							status: ["not in", ["Lost", "Closed"]],
							enquiry_type: cur_frm.doc.order_type,
							customer: cur_frm.doc.customer || undefined,
							lead: cur_frm.doc.lead || undefined,
							company: cur_frm.doc.company
						}
					})
				}, __("Get items from"), "btn-default");
			
			cur_frm.add_custom_button(__('CSV'),
				function() {
					var me = this;

					var dialog = new frappe.ui.Dialog({
						title: "Add items from CSV",
						fields: [
							{"fieldtype": "HTML", "label": __(""), "fieldname": "import_html",
								"reqd": 1 },
							{"fieldtype": "HTML", "label": __(""), "fieldname": "import_log",
								"reqd": 1 },
							{"fieldtype": "Check", "label": __("Keep Previous Entries"), "fieldname": "keep_previous"},
							{"fieldtype": "Button", "label": __("Update"), "fieldname": "update"},
						]
					});

					var $wrapper = $(dialog.fields_dict.import_html.wrapper).empty();

					// upload
					frappe.upload.make({
						parent: $wrapper,
						args: {
							method: 'erpnext.selling.doctype.quotation.quotation.upload',
						},
						btn: $(dialog.fields_dict.update.wrapper),
						callback: function(attachment, r) {
							var $log_wrapper = $(dialog.fields_dict.import_log.wrapper).empty();
							var $keep_previous = $(dialog.fields_dict.keep_previous.wrapper).find('input[type="checkbox"]');
				
							var messages = r.message.messages;
							var error = r.message.error;
							if(!r.messages) r.messages = [];
							// replace links if error has occured
							if(error.length) {
								r.messages = $.map(error, function(v) {
									
									return v;
								});

								r.messages = ["<h4 style='color:red'>"+__("Import Failed!")+"</h4>"]
									.concat(r.messages)
								
								$.each(r.messages, function(i, v) {
								var $p = $('<p>').html(v).appendTo($log_wrapper);
							});
							} else {
								if(!$keep_previous.is(":checked")){	
									 cur_frm.doc.items = [];
								}
								$.each(messages, function(i, item) {
									var d = frappe.model.add_child(cur_frm.doc, "Quotation Item", "items");
										d.item_code = item.item_code;
										d.qty = item.qty;
										d.page_break = item.page_break;
										console.log(d);
										cur_frm.script_manager.trigger("item_code", d.doctype, d.name);

									});
								//r.messages = ["<h4 style='color:green'>"+__("Import Successful!")+"</h4>"].concat(r.message.messages)
								dialog.hide();
								refresh_field("items");
							}	
						},
						is_private: false
					});

					
					dialog.show();

					
					
				}, __("Get items from"), "btn-default");
		}
		calculate_headers();

		this.toggle_reqd_lead_customer();
		
	},
	
	

	quotation_to: function() {
		var me = this;
		if (this.frm.doc.quotation_to == "Lead") {
			this.frm.set_value("customer", null);
			this.frm.set_value("contact_person", null);
		} else if (this.frm.doc.quotation_to == "Customer") {
			this.frm.set_value("lead", null);
		}

		this.toggle_reqd_lead_customer();
	},

	toggle_reqd_lead_customer: function() {
		var me = this;

		this.frm.toggle_reqd("lead", this.frm.doc.quotation_to == "Lead");
		this.frm.toggle_reqd("customer", this.frm.doc.quotation_to == "Customer");

		// to overwrite the customer_filter trigger from queries.js
		$.each(["customer_address", "shipping_address_name"],
			function(i, opts) {
				me.frm.set_query(opts, me.frm.doc.quotation_to==="Lead"
					? erpnext.queries["lead_filter"] : erpnext.queries["customer_filter"]);
			}
		);
	},

	tc_name: function() {
		this.get_terms();
	},

	validate_company_and_party: function(party_field) {
		if(!this.frm.doc.quotation_to) {
			msgprint(__("Please select a value for {0} quotation_to {1}", [this.frm.doc.doctype, this.frm.doc.name]));
			return false;
		} else if (this.frm.doc.quotation_to == "Lead") {
			return true;
		} else {
			return this._super(party_field);
		}
	},

	lead: function() {
		var me = this;
		frappe.call({
			method: "erpnext.crm.doctype.lead.lead.get_lead_details",
			args: { "lead": this.frm.doc.lead },
			callback: function(r) {
				if(r.message) {
					me.frm.updating_party_details = true;
					me.frm.set_value(r.message);
					me.frm.refresh();
					me.frm.updating_party_details = false;

				}
			}
		})
	}
});

cur_frm.script_manager.make(erpnext.selling.QuotationController);

cur_frm.fields_dict.lead.get_query = function(doc,cdt,cdn) {
	return{	query: "erpnext.controllers.queries.lead_query" }
}

cur_frm.cscript['Make Sales Order'] = function() {
	frappe.model.open_mapped_doc({
		method: "erpnext.selling.doctype.quotation.quotation.make_sales_order",
		frm: cur_frm
	})
}

cur_frm.cscript['Declare Order Lost'] = function(){
	var dialog = new frappe.ui.Dialog({
		title: "Set as Lost",
		fields: [
			{"fieldtype": "Text", "label": __("Reason for losing"), "fieldname": "reason",
				"reqd": 1 },
			{"fieldtype": "Button", "label": __("Update"), "fieldname": "update"},
		]
	});

	dialog.fields_dict.update.$input.click(function() {
		args = dialog.get_values();
		if(!args) return;
		return cur_frm.call({
			method: "declare_order_lost",
			doc: cur_frm.doc,
			args: args.reason,
			callback: function(r) {
				if(r.exc) {
					msgprint(__("There were errors."));
					return;
				}
				dialog.hide();
				cur_frm.refresh();
			},
			btn: this
		})
	});
	dialog.show();

}

cur_frm.cscript.on_submit = function(doc, cdt, cdn) {
	if(cint(frappe.boot.notification_settings.quotation))
		cur_frm.email_doc(frappe.boot.notification_settings.quotation_message);
}

frappe.ui.form.on("Quotation Item", "items_on_form_rendered", function(frm, cdt, cdn) {
	// enable tax_amount field if Actual
})

// Table modified
// ------------------------------------------------------------------------

frappe.ui.form.on("Quotation Item", "items_remove", function(frm,dt,dn){
	calculate_headers();

})

frappe.ui.form.on("Quotation Item", "qty", function(frm,dt,dn){
})


calculate_headers2 = function(){
				
	return $c_obj(cur_frm.doc, 'calculate_headers','',function(r, rt) {
			var doc = locals[dt][dn];
			cur_frm.refresh();
			console.log(r);
	});

}

calculate_headers = function(){
		var items = cur_frm.doc.items;
		$.each(items, function(i, d) {
			
			//item_group_parent = get_parent_group(d.item_group);
			if (d.item_group == "Header1"){
				var sum = 0;
						
				// next item group equal to current - break
				// next item group is parent of current - break
				// next item group is child of current - return
				for (var j = i+1; j < items.length; ++j) {
					var testitem = items[j];
					//get_child_groups(d.item_group,testitem.item_group);
					if (testitem.item_group == d.item_group)
						break;
					else if (testitem.item_group == "Header2" || testitem.item_group == "Header3") {
						sum = sum;
					} else {
						sum = sum + testitem.amount;
					} 
				}
				d.qty = 0;
				d.rate = sum;
				d.amount = 0;
			} else if (d.item_group == "Header2"){
				var sum = 0;
						
				// next item group equal to current - break
				// next item group is parent of current - break
				// next item group is child of current - return
				for (var j = i+1; j < items.length; ++j) {
					var testitem = items[j];
					//get_child_groups(d.item_group,testitem.item_group);
					if (testitem.item_group == d.item_group)
						break;
					else if (testitem.item_group == "Header1") {
						break;
					} else if (testitem.item_group == "Header3") {
						
					} else {
						sum = sum + testitem.amount;
					} 
				}
				d.qty = 0;
				d.rate = sum;
				d.amount = 0;

			
			} else if (d.item_group == "Header3"){
				var sum = 0;
						
				// next item group equal to current - break
				// next item group is parent of current - break
				// next item group is child of current - return
				for (var j = i+1; j < items.length; ++j) {
					var testitem = items[j];
					//get_child_groups(d.item_group,testitem.item_group);
					if (testitem.item_group == d.item_group)
						break;
					else if (testitem.item_group == "Header1") {
						break;
					} else if (testitem.item_group == "Header2") {
						break;
					} else {
						sum = sum + testitem.amount;
					} 
				}
				d.qty = 0;
				d.rate = sum;
				d.amount = 0;
				
				
			}
		});
		refresh_field("items");
}

	
get_parent_groups = function(name){
	
	frappe.model.with_doc("Item Group", name, function() { 
		var doc = frappe.model.get_doc("Item Group", name);
		
	});
		
	
	
}


get_parent_group = function(parent_group){
	frappe.call({
		method:"erpnext.setup.doctype.item_group.item_group.get_main_parent_group",
		args:{
			item_group_name:parent_group
		},
		callback: function(r) {
			console.log(r);

		}
	});
}

get_parent_group1 = function(parent_group){
	frappe.call({
		method:"erpnext.setup.doctype.item_group.item_group.get_parent_item_groups",
		args:{
			item_group_name:parent_group
		},
		callback: function(r) {
			//console.log(r);
		}
	});
}



get_child_groups = function(parent_group, child_group){
	frappe.call({
		method:"frappe.client.get_list",
		args:{
			doctype:"Item Group",
			filters: [
				["parent_item_group","=", parent_group]
			],
			fields: ["item_group_name"]
		},
		callback: function(r) {
			//console.log(r);
		}
	});
}

cur_frm.add_fetch("item_code", "manufacturer_part_no", "manufacturer_part_no")
