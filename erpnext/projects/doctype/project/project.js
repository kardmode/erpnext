// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
frappe.ui.form.on("Project", {
	setup(frm) {
		frm.make_methods = {
			Timesheet: () => {
				open_form(frm, "Timesheet", "Timesheet Detail", "time_logs");
			},
			"Purchase Order": () => {
				open_form(frm, "Purchase Order", "Purchase Order Item", "items");
			},
			"Purchase Receipt": () => {
				open_form(frm, "Purchase Receipt", "Purchase Receipt Item", "items");
			},
			"Purchase Invoice": () => {
				open_form(frm, "Purchase Invoice", "Purchase Invoice Item", "items");
			},
			'Purchase Order': () => {
				open_form(frm, "Purchase Order", "Purchase Order Item", "items");
			},
			'Purchase Receipt': () => {
				open_form(frm, "Purchase Receipt", "Purchase Receipt Item", "items");
			},
			'Purchase Invoice': () => {
				open_form(frm, "Purchase Invoice", "Purchase Invoice Item", "items");
			},
		}
		
		frm.fields_dict['parent_project'].get_query = function(doc) {
			return {
				filters: {
					"company": cur_frm.doc.company,
					'is_group': 1
				}
			}
		}

	},
	onload: function (frm) {
		const so = frm.get_docfield("sales_order");
		so.get_route_options_for_new_doc = () => {
			if (frm.is_new()) return;
			return {
				customer: frm.doc.customer,
				project_name: frm.doc.name,
			};
		};

		frappe.dynamic_link = { doc: frm.doc, fieldname: 'customer', doctype: 'Customer' }
		
		$.each([["customer_address", "address_query"],
			["shipping_address_name", "address_query"],
			["contact_person", "contact_query"],
			["customer", "customer"]],
			function(i, opts) {
				if(me.frm.fields_dict[opts[0]])
					me.frm.set_query(opts[0], erpnext.queries[opts[1]]);
			});
		
		frm.updating_party_details = false;
		
		frm.set_query("user", "users", function () {
			return {
				query: "erpnext.projects.doctype.project.project.get_users_for_project",
			};
		});

		frm.set_query("department", function (doc) {
			return {
				filters: {
					company: doc.company,
				},
			};
		});

		// sales order
		frm.set_query("sales_order", function () {
			var filters = {
				project: ["in", frm.doc.__islocal ? [""] : [frm.doc.name, ""]],
				company: frm.doc.company,
			};
			
			if (frm.doc.customer) {
				filters["customer"] = frm.doc.customer;
			}

			return {
				filters: filters,
			};
		});

		frm.set_query("cost_center", () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			};
		});
	},


	refresh: function(frm) {
		
		if (cint(frm.doc.is_group) == 1) {
			frm.add_custom_button(__('Group to Non-Group'),

				function() { convert_to_group_or_ledger(frm); }, 'fa fa-retweet', 'btn-default')
		} else if (cint(frm.doc.is_group) == 0) {
			

			frm.add_custom_button(__('Non-Group to Group'),
				function() { convert_to_group_or_ledger(frm); }, 'fa fa-retweet', 'btn-default')
		}
		
		
		if (!frm.doc.__islocal) {
			// cur_frm.toggle_enable(['is_group', 'company'], false);
			cur_frm.toggle_enable(['is_group'], false);
		}
		else if(!frm.doc.is_group){
			// frm.add_fetch('company', 'default_inventory_account', 'account');

				
		}
		
		if(frm.doc.__islocal) {
			frm.web_link && frm.web_link.remove();
		} else {
			frm.add_web_link("/projects?project=" + encodeURIComponent(frm.doc.name));
			
			cur_frm.add_custom_button(__("Project Summary"), function() {
					window.location.href = 'desk#query-report/Project%20Summary';
				}, __("Reports"), "btn-default");
			

			frm.trigger("show_dashboard");
		}
		frm.trigger("set_custom_buttons");
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
	set_custom_buttons: function (frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Duplicate Project with Tasks"),
				() => {
					frm.events.create_duplicate(frm);
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Update Total Purchase Cost"),
				() => {
					frm.events.update_total_purchase_cost(frm);
				},
				__("Actions")
			);

			frm.trigger("set_project_status_button");

			if (frappe.model.can_read("Task")) {
				frm.add_custom_button(
					__("Gantt Chart"),
					function () {
						frappe.route_options = {
							project: frm.doc.name,
						};
						frappe.set_route("List", "Task", "Gantt");
					},
					__("View")
				);

				frm.add_custom_button(
					__("Kanban Board"),
					() => {
						frappe
							.call(
								"erpnext.projects.doctype.project.project.create_kanban_board_if_not_exists",
								{
									project: frm.doc.name,
								}
							)
							.then(() => {
								frappe.set_route("List", "Task", "Kanban", frm.doc.project_name);
							});
					},
					__("View")
				);
			}
		}
	},

	update_total_purchase_cost: function (frm) {
		frappe.call({
			method: "erpnext.projects.doctype.project.project.recalculate_project_total_purchase_cost",
			args: { project: frm.doc.name },
			freeze: true,
			freeze_message: __("Recalculating Purchase Cost against this Project..."),
			callback: function (r) {
				if (r && !r.exc) {
					frappe.msgprint(__("Total Purchase Cost has been updated"));
					frm.refresh();
				}
			},
		});
	},

	set_project_status_button: function (frm) {
		frm.add_custom_button(
			__("Set Project Status"),
			() => {
				let d = new frappe.ui.Dialog({
					title: __("Set Project Status"),
					fields: [
						{
							fieldname: "status",
							fieldtype: "Select",
							label: "Status",
							reqd: 1,
							options: "Completed\nCancelled",
						},
					],
					primary_action: function () {
						frm.events.set_status(frm, d.get_values().status);
						d.hide();
					},
					primary_action_label: __("Set Project Status"),
				}).show();
			},
			__("Actions")
		);
	},

	create_duplicate: function (frm) {
		return new Promise((resolve) => {
			frappe.prompt("Project Name", (data) => {
				frappe
					.xcall("erpnext.projects.doctype.project.project.create_duplicate_project", {
						prev_doc: frm.doc,
						project_name: data.value,
					})
					.then(() => {
						frappe.set_route("Form", "Project", data.value);
						frappe.show_alert(__("Duplicate project has been created"));
					});
				resolve();
			});
		});
	},

	set_status: function (frm, status) {
		frappe.confirm(__("Set Project and all Tasks to status {0}?", [__(status).bold()]), () => {
			frappe
				.xcall("erpnext.projects.doctype.project.project.set_project_status", {
					project: frm.doc.name,
					status: status,
				})
				.then(() => {
					frm.reload_doc();
				});
		});
	},
});

function open_form(frm, doctype, child_doctype, parentfield) {
	frappe.model.with_doctype(doctype, () => {
		let new_doc = frappe.model.get_new_doc(doctype);

		// add a new row and set the project
		let new_child_doc = frappe.model.get_new_doc(child_doctype);
		new_child_doc.project = frm.doc.name;
		new_child_doc.parent = new_doc.name;
		new_child_doc.parentfield = parentfield;
		new_child_doc.parenttype = doctype;
		new_doc[parentfield] = [new_child_doc];
		new_doc.project = frm.doc.name;

		frappe.ui.form.make_quick_entry(doctype, null, null, new_doc);
	});
}

var calculate_sales = function(frm,doctype){
	frappe.call({
		doc: doc,
		method:"calculate_sales",
		args: {
			doctype: doctype,
		},
		callback: function(){
			frm.refresh();
		}
		
	})
}


function convert_to_group_or_ledger(frm){
	frappe.call({
		method:"erpnext.projects.doctype.project.project.convert_to_group_or_ledger",
		args: {
			docname: frm.doc.name,
			is_group: frm.doc.is_group
		},
		callback: function(){
			frm.refresh();
		}
		
	})
}
