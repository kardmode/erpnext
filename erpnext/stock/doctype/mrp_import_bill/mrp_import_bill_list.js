frappe.listview_settings['MRP Import Bill'] = {
	// add_fields: ["status", "branch", "department", "designation","image"],
	onload: function(listview) {
		if (!frappe.route_options){ //remove this condition if not required
			frappe.route_options = {
				"disabled": ["=", "0"]
			};
		}
	},
	// filters: [["disabled","=", "0"]],
	/* get_indicator: function(doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = {"Active": "green", "Left": "darkgrey"}[doc.status];
		return indicator;
	} */
};

