// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Tax Template', {
	refresh: function(frm) {

	},
	onload: function(frm) {
		
		frm.set_query("account_head", "item_tax_accounts", function() {
			return {
				filters: {
					'account_type': "Tax",
					'is_group':"false"
				}
			};
		});
		
	

	},
});

cur_frm.cscript.account_head = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.account_head){
		frappe.call({
			type:"GET",
			method: "erpnext.controllers.accounts_controller.get_tax_rate",
			args: {"account_head":d.account_head},
			callback: function(r) {
				frappe.model.set_value(cdt, cdn, "rate", r.message.tax_rate || 0);
				frappe.model.set_value(cdt, cdn, "description", r.message.account_name);
			}
		})
		
	}
	
}