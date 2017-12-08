// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project Breakdown', {
	refresh: function(frm) {
		
		cur_frm.add_custom_button(__("Get Details"), function() {
					get_details();
				});
				
				
		frm.add_custom_button(__('Download Summary'), function() {
				var w = window.open(
					frappe.urllib.get_full_url(
						"/api/method/erpnext.projects.doctype.project_breakdown.project_breakdown.download?"
						+"name="+encodeURIComponent(frm.doc.name)));
				if(!w) {
					frappe.msgprint(__("Please enable pop-ups")); return;
				}
			});
			
		
	},
	
	
	
	
});

frappe.ui.form.on('Project Item', {
	sub_project: function(frm,cdt,cdn) {
		var d = locals[cdt][cdn];
		frappe.call({
		method:'erpnext.projects.doctype.project_breakdown.project_breakdown.get_sub_project_details',
		args:{
			sub_project: d.sub_project
		},
		callback: function(r) {
			
			
			var description = ""
			console.log(r);
			if(r.message)
				description = make_sub_project_description(r);
			
			frappe.model.set_value(d.doctype, d.name, "description", description);
			cur_frm.dirty();
		}
		}); 

	},
	
	
	
	
});

get_details = function(){
	var doc = cur_frm.doc;
	frappe.call({
		method:'erpnext.projects.doctype.project_breakdown.project_breakdown.get_details',
		args:{
			project: doc.project
		},
		callback: function(r) {
			
			if(r.message){
				doc.layout = [];
				for (var i=0; i< r.message.length; i++) {
					var row = frappe.model.add_child(cur_frm.doc, cur_frm.fields_dict.layout.df.options, cur_frm.fields_dict.layout.df.fieldname);
					row.sub_project = r.message[i].name;
					cur_frm.script_manager.trigger("sub_project", row.doctype, row.name);

				}
				cur_frm.refresh_field('layout');
				cur_frm.dirty();
				
			}
			
			
		}
	}); 
}

export_summary = function(doc){
}

make_sub_project_description = function(r){
	
	var description = ""
	for (var i=0; i< r.message.length; i++) {
		description += r.message[i].label + ":" + r.message[i].location;
		if(i+1 !== r.message.length)
			description += " - ";
	}
	
	return description;
}
