// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sub Project', {
	setup: function(frm) {
		
		
		frm.fields_dict['parent_sub_project'].get_query = function(doc) {
			return {
				filters: {
					"company": cur_frm.doc.company,
					'is_group': 1
				}
			}
		}
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
			cur_frm.toggle_enable(['is_group', 'company'], false);
		}
		else if(!frm.doc.is_group){
			frm.add_fetch('company', 'default_inventory_account', 'account');

				
		}

	}
});
