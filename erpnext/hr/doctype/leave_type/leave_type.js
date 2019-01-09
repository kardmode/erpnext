frappe.ui.form.on("Leave Type", {
	refresh: function(frm) {
		frm.add_custom_button(__("Allocations"), function() {
			frappe.set_route("List", "Leave Allocation",
			{"leave_type": frm.doc.name});
		});
		
		if(frm.doc.is_lwp===1)
		{
			frm.set_df_property("is_paid_in_advance", 'read_only', 1);
			frm.set_df_property("is_present_during_period", 'read_only', 1);
		}
	},
	is_lwp: function(frm) {
		if(frm.doc.is_lwp===1)
		{
			frm.set_df_property("is_paid_in_advance", 'read_only', 1);
			frm.set_df_property("is_present_during_period", 'read_only', 1);
			frm.set_value("is_paid_in_advance",0);
			frm.set_value("is_present_during_period",0);
			
			
		}
		else
		{
			frm.set_df_property("is_paid_in_advance", 'read_only', 0);
			frm.set_df_property("is_present_during_period", 'read_only', 0);
			frm.set_value("is_paid_in_advance",0);
			frm.set_value("is_present_during_period",0);
		}
	},
});
