// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Project", {
	setup: function(frm) {
		frm.set_indicator_formatter('title',
			function(doc) {
				let indicator = 'orange';
				if (doc.status == 'Overdue') {
					indicator = 'red';
				}
				else if (doc.status == 'Cancelled') {
					indicator = 'dark grey';
				}
				else if (doc.status == 'Closed') {
					indicator = 'green';
				}
				return indicator;
			}
		);
		
		frm.fields_dict['parent_project'].get_query = function(doc) {
			return {
				filters: {
					"company": cur_frm.doc.company,
					'is_group': 1
				}
			}
		}
	},

	onload: function(frm) {
		var so = frappe.meta.get_docfield("Project", "sales_order");
		so.get_route_options_for_new_doc = function(field) {
			if(frm.is_new()) return;
			return {
				"customer": frm.doc.customer,
				"project_name": frm.doc.name
			}
		}

		
		$.each([["customer_address", "customer_filter"],
			["shipping_address_name", "customer_filter"],
			["contact_person", "customer_filter"],
			["customer", "customer"]],
			function(i, opts) {
				if(me.frm.fields_dict[opts[0]])
					me.frm.set_query(opts[0], erpnext.queries[opts[1]]);
			});
		
		frm.updating_party_details = false;
		
		frm.set_query("user", "users", function() {
			return {
				query:"erpnext.projects.doctype.project.project.get_users_for_project"
			}
		});

		// sales order
		frm.set_query('sales_order', function() {
			var filters = {
				'project': ["in", frm.doc.__islocal ? [""] : [frm.doc.name, ""]]
			};
			
			if (frm.doc.customer) {
				filters["customer"] = frm.doc.customer;
			}

			return {
				filters: filters
			}
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

			if(frappe.model.can_read("Task")) {
				frm.add_custom_button(__("Gantt Chart"), function() {
					frappe.route_options = {"project": frm.doc.name};
					frappe.set_route("List", "Task", "Gantt");
				});
			}
			
			cur_frm.add_custom_button(__("Project Summary"), function() {
					window.location.href = 'desk#query-report/Project%20Summary';
				}, __("Reports"), "btn-default");
			
			/* cur_frm.add_custom_button(__("Quotation"), function() {
				calculate_sales("Quotation");
				
				
			}, __("Get Summary"), true);
			
			cur_frm.add_custom_button(__("Sales Order"), function() {
				calculate_sales("Sales Order");
				
				
			}, __("Get Summary"), true);
			cur_frm.add_custom_button(__("Sales Invoice"), function() {
				calculate_sales("Sales Invoice");
				
				
			}, __("Get Summary"), true);
			cur_frm.add_custom_button(__("Delivery Note"), function() {
				calculate_sales("Delivery Note");
				
				
			}, __("Get Summary"), true); */

		
		if(frappe.model.can_read("Quotation")) {
			cur_frm.add_custom_button(__("Quotation"), function() {
				print_summary("Quotation");
				
				
			}, __("Print"), true);
			cur_frm.add_custom_button(__("Sales Order"), function() {
				print_summary("Sales Order");
				
				
			}, __("Print"), true);
			cur_frm.add_custom_button(__("Sales Invoice"), function() {
				print_summary("Sales Invoice");
				
				
			}, __("Print"), true);
			cur_frm.add_custom_button(__("Delivery Note"), function() {
				print_summary("Delivery Note");
				
				
			}, __("Print"), true);
		}

			frm.trigger('show_dashboard');
		}
	},
	tasks_refresh: function(frm) {
		var grid = frm.get_field('tasks').grid;
		grid.wrapper.find('select[data-fieldname="status"]').each(function() {
			if($(this).val()==='Open') {
				$(this).addClass('input-indicator-open');
			} else {
				$(this).removeClass('input-indicator-open');
			}
		});
	},
	show_dashboard: function(frm) {
		if(frm.doc.__onload.activity_summary.length) {
			var hours = $.map(frm.doc.__onload.activity_summary, function(d) { return d.total_hours });
			var max_count = Math.max.apply(null, hours);
			var sum = hours.reduce(function(a, b) { return a + b; }, 0);
			var section = frm.dashboard.add_section(
				frappe.render_template('project_dashboard',
					{
						data: frm.doc.__onload.activity_summary,
						max_count: max_count,
						sum: sum
					}));

			section.on('click', '.time-sheet-link', function() {
				var activity_type = $(this).attr('data-activity_type');
				frappe.set_route('List', 'Timesheet',
					{'activity_type': activity_type, 'project': frm.doc.name, 'status': ["!=", "Cancelled"]});
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

frappe.ui.form.on("Project Task", {
	edit_task: function(frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		if(doc.task_id) {
			frappe.set_route("Form", "Task", doc.task_id);
		} else {
			frappe.msgprint(__("Save the document first."));
		}
	},
	edit_timesheet: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		frappe.route_options = {"project": frm.doc.project_name, "task": child.task_id};
		frappe.set_route("List", "Timesheet");
	},

	make_timesheet: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		frappe.model.with_doctype('Timesheet', function() {
				var doc = frappe.model.get_new_doc('Timesheet');
				var row = frappe.model.add_child(doc, 'time_logs');
				row.project = frm.doc.project_name;
				row.task = child.task_id;
				frappe.set_route('Form', doc.doctype, doc.name);
			})
	},

	status: function(frm, doctype, name) {
		frm.trigger('tasks_refresh');
	},
});


calculate_sales = function(doctype){
	var doc = cur_frm.doc;
	
	return $c_obj(doc, 'calculate_sales', {"doctype": doctype}, function(r, rt) {

			cur_frm.refresh();
	});
}


print_summary = function(doctype){
		var doc = cur_frm.doc;
		
		var dialog = new frappe.ui.Dialog({
			title: "Print Documents",
			fields: [
				{"fieldtype": "Select", "label": __("Print Format"), "fieldname": "print_sel"},
				{"fieldtype": "Select", "label": __("Orientation"), "options":"Landscape\nPortrait","default": "Portrait", "fieldname": "orientation"},
				{"fieldtype": "Select", "label": __("Letterhead"), "fieldname": "letterhead_sel"},
			]
		});
		
		dialog.set_primary_action(__("Print"), function() {
			args = dialog.get_values();
			if(!args) return;
			var with_letterhead = 1;
			var print_format = args.print_sel;
			var orientation = args.orientation;
			
			var letterhead = args.project_print_sel;

			
			return $c_obj(doc, 'print_summary', {"doctype": doctype}, function(r, rt) {
				if (r.message)
				{
					var docname = [];
					names = r.message[0];
					doctype = r.message[1];

					names.forEach(function (element, index) {
						docname.push(element[0]);
					});
					if(docname.length >= 1){
						var json_string = JSON.stringify(docname);								
						var w = window.open("/api/method/frappe.utils.print_format.download_multi_pdf?"
							+"doctype="+encodeURIComponent(doctype)
							+"&name="+encodeURIComponent(json_string)
							+"&format="+encodeURIComponent(print_format)
							// +"&cover_doctype="+encodeURIComponent(cur_frm.doctype)
							// +"&cover_name="+encodeURIComponent(cur_frm.docname)
							// +"&cover_format="+encodeURIComponent(cover_format)
							+"&no_letterhead="+(with_letterhead ? "0" : "1"))
							+"&letterhead="+encodeURIComponent(letterhead)
							+"&orientation="+encodeURIComponent(orientation);
						if(!w) {
							msgprint(__("Please enable pop-ups")); return;
						}
					}

				}
								dialog.hide();

			});
		});
		
		frappe.call({
				doc: doc,
				method: "get_print_formats",
				args: {
				"doctype" : doctype
				},
				callback: function(r) {
					
					var print_formats = [];
					var letterheads = [];

					var default_letter_head = locals[":Company"] ? locals[":Company"][frappe.defaults.get_default('company')]["default_letter_head"] : '';
					
					
					r.message[0].forEach(function (element, index) {
						print_formats.push(element.name);
					});
					
					if(print_formats)
					{
						dialog.fields_dict.print_sel.$input.empty().add_options(print_formats);
						dialog.fields_dict.letterhead_sel.$input.empty().add_options(["Default"]);
						dialog.fields_dict.letterhead_sel.$input.add_options($.map(frappe.boot.letter_heads, function(i,d){ return d }));

		
						dialog.show();
					}
				}
			});

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
