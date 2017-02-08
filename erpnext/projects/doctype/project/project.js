// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Project", {
	onload: function(frm) {
		var so = frappe.meta.get_docfield("Project", "sales_order");
		so.get_route_options_for_new_doc = function(field) {
			if(frm.is_new()) return;
			return {
				"customer": frm.doc.customer,
				"project_name": frm.doc.name
			}
		}

		frm.set_query('customer', 'erpnext.controllers.queries.customer_query');
		
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
			
			cur_frm.add_custom_button(__("Sales"), function() {
				calculate_sales();
				
				
			}, __("Calculate"), true);
		
		if(frappe.model.can_read("Quotation")) {
			cur_frm.add_custom_button(__("Quotation"), function() {
				print_summary("Quotation");
				
				
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

	
});

frappe.ui.form.on("Project Task", {
	edit_task: function(frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		if(doc.task_id) {
			frappe.set_route("Form", "Task", doc.task_id);
		} else {
			msgprint(__("Save the document first."));
		}
	},
	status: function(frm, doctype, name) {
		frm.trigger('tasks_refresh');
	},
});


calculate_sales = function(){
	var doc = cur_frm.doc;
	return $c_obj(doc, 'calculate_sales','', function(r, rt) {
		
			cur_frm.refresh();
	});
}


print_summary = function(doctype){
		var doc = cur_frm.doc;
		
		var dialog = new frappe.ui.Dialog({
			title: "Print Documents",
			fields: [
				{"fieldtype": "Check", "label": __("With Letterhead"), "fieldname": "with_letterhead"},
				{"fieldtype": "Select", "label": __("Print Format"), "fieldname": "print_sel"},
				{"fieldtype": "Button", "label": __("Print"), "fieldname": "print"},
			]
		});
		
		
		dialog.fields_dict.print.$input.click(function() {
			args = dialog.get_values();
			if(!args) return;
			with_letterhead = args.with_letterhead ? 1 : 0;
			print_format = args.print_sel;
			
			
			return $c_obj(doc, 'print_summary', {"document": doctype}, function(r, rt) {
				if (r.message)
				{
					var docname = [];
					names = r.message[0];
					doctype = r.message[1];
					print_format = doctype;
					names.forEach(function (element, index) {
						docname.push(element[0]);
					});
					
					if(docname.length >= 1){
						var json_string = JSON.stringify(docname);								
						var w = window.open("/api/method/frappe.templates.pages.print.download_multi_pdf?"
							+"doctype="+encodeURIComponent(doctype)
							+"&name="+encodeURIComponent(json_string)
							+"&format="+encodeURIComponent(print_format)
							+"&no_letterhead="+(with_letterhead ? "0" : "1"));
						if(!w) {
							msgprint(__("Please enable pop-ups")); return;
						}
					}
				}
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
					r.message.forEach(function (element, index) {
						print_formats.push(element.name);
					});
					if(print_formats)
					{
						console.log(print_formats);
						dialog.fields_dict.print_sel.$input.empty().add_options(print_formats);
						dialog.show();
					}
				}
			});


	

		
		

		
		
		

		

}


