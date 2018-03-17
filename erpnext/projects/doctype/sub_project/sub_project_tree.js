frappe.treeview_settings['Sub Project'] = {
	get_tree_nodes: "erpnext.projects.doctype.sub_project.sub_project.get_children",
	add_tree_node: "erpnext.projects.doctype.sub_project.sub_project.add_node",
	get_tree_root: false,
	root_label: "Sub Projects",
	filters: [{
		fieldname: "company",
		fieldtype:"Select",
		options: $.map(locals[':Company'], function(c) { return c.name; }).sort(),
		label: __("Company"),
		default: frappe.defaults.get_default('company') ? frappe.defaults.get_default('company'): ""
	},
	{
		fieldname: "project",
		fieldtype:"Link",
		options: "Project",
		label: __("Project"),
	}
	
	],
	fields:[
		{fieldtype:'Data', fieldname: 'sub_project_name',
			label:__('New Sub Project Name'), reqd:true},
		{fieldtype:'Check', fieldname:'is_group', label:__('Is Group'),
			description: __("Child nodes can be only created under 'Group' type nodes")}
	],
	ignore_fields:["parent_sub_project"],
	onrender: function(node) {
		if (node.data && node.data.balance!==undefined) {
			$('<span class="balance-area pull-right text-muted small">'
			+ format_currency(Math.abs(node.data.balance), node.data.company_currency)
			+ '</span>').insertBefore(node.$ul);
		}
	}
}