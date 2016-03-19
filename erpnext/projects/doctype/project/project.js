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
	}
});

frappe.ui.form.on("Project Task", "edit_task", function(frm, doctype, name) {
	var doc = frappe.get_doc(doctype, name);
	if(doc.task_id) {
		frappe.set_route("Form", "Task", doc.task_id);
	} else {
		msgprint(__("Save the document first."));
	}
})

// show tasks
cur_frm.cscript.refresh = function(doc) {
	if(!doc.__islocal) {
		if(frappe.model.can_read("Task")) {
			cur_frm.add_custom_button(__("Gantt Chart"), function() {
				frappe.route_options = {"project": doc.name, "start": doc.expected_start_date, "end": doc.expected_end_date};
				frappe.set_route("Gantt", "Task");
			}, __("View"), true);
			cur_frm.add_custom_button(__("Tasks"), function() {
				frappe.route_options = {"project": doc.name}
				frappe.set_route("List", "Task");
			}, __("View"), true);
		}
		if(frappe.model.can_read("Time Log")) {
			cur_frm.add_custom_button(__("Time Logs"), function() {
				frappe.route_options = {"project": doc.name}
				frappe.set_route("List", "Time Log");
			}, __("View"), true);
		}

		if(frappe.model.can_read("Expense Claim")) {
			cur_frm.add_custom_button(__("Expense Claims"), function() {
				frappe.route_options = {"project": doc.name}
				frappe.set_route("List", "Expense Claim");
			}, __("View"), true);
		}
		
		/* if(frappe.model.can_read("Quotation")) {
			cur_frm.add_custom_button(__("Quotation"), function() {
				print_summary("Quotation");
				
				
			}, __("Print"), true);
			cur_frm.add_custom_button(__("Sales Invoice"), function() {
				print_summary("Sales Invoice");
				
				
			}, __("Print"), true);
			cur_frm.add_custom_button(__("Delivery Note"), function() {
				print_summary("Delivery Note");
				
				
			}, __("Print"), true);
		} */
		
	}
}

cur_frm.fields_dict.customer.get_query = function(doc,cdt,cdn) {
	return{
		query: "erpnext.controllers.queries.customer_query"
	}
}

cur_frm.fields_dict['sales_order'].get_query = function(doc) {
	var filters = {
		'project': ["in", doc.__islocal ? [""] : [doc.name, ""]]
	};

	if (doc.customer) {
		filters["customer"] = doc.customer;
	}

	return {
		filters: filters
	}
}

print_summary = function(doctype){
		var doc = cur_frm.doc;
		
		var dialog = new frappe.ui.Dialog({
			title: "Print Documents",
			fields: [
				{"fieldtype": "Check", "label": __("Print Letterhead"), "fieldname": "print_letterhead"},
				{"fieldtype": "Select", "label": __("Print Format"), "fieldname": "print_sel"},
				{"fieldtype": "Button", "label": __("Print"), "fieldname": "print"},
			]
		});

		print_formats = frappe.meta.get_print_formats("Project");
		dialog.fields_dict.print_sel.$input.empty().add_options(print_formats);
		
		

		dialog.fields_dict.print.$input.click(function() {
			args = dialog.get_values();
			if(!args) return;
			var default_print_format = locals.DocType["Project"].default_print_format;
			with_letterhead = args.print_letterhead ? 1 : 0;
			print_format = args.print_sel ? args.print_sel:default_print_format;
			
			
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
		dialog.show();
		

		

}

