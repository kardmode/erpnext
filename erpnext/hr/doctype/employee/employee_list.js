frappe.listview_settings['Employee'] = {
	add_fields: ["status", "branch", "department", "designation","image"],
	onload: function(listview) {
		if (!frappe.route_options){ //remove this condition if not required
			frappe.route_options = {
				"status": ["=", "Active"]
			};
		}
	},
	filters: [["status","=", "Active"]],
	get_indicator: function(doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = {"Active": "green", "Temporary Leave": "red", "Left": "darkgrey"}[doc.status];
		return indicator;
	}
};
