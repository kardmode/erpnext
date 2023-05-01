// Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Product Bundle", {
	refresh: function (frm) {
		frm.toggle_enable("new_item_code", frm.is_new());
		frm.set_query("new_item_code", () => {
			return {
				query: "erpnext.selling.doctype.product_bundle.product_bundle.get_new_item_code",
			};
		});
	},
});


frappe.ui.form.on("Product Bundle Item", {
	item_code(frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		

		if (child.bom_no) {
			child.bom_no = '';
		}

		get_bom_material_detail(cur_frm.doc, cdt, cdn);
	},
	
	
});


var get_bom_material_detail = function(doc, cdt, cdn) {
	if (!doc.company) {
		frappe.throw({message: __("Please select a Company first."), title: __("Mandatory")});
	}

	var d = locals[cdt][cdn];
	if (d.item_code) {
		return frappe.call({
			doc: doc,
			method: "get_bom_material_detail",
			args: {
				"company": doc.company,
				"item_code": d.item_code,
				"bom_no": d.bom_no != null ? d.bom_no: '',
				"qty": d.qty,
				"stock_qty": d.stock_qty,
				// "include_item_in_manufacturing": d.include_item_in_manufacturing,
				"uom": d.uom,
				"stock_uom": d.stock_uom,
				"conversion_factor": d.conversion_factor,
				// "sourced_by_supplier": d.sourced_by_supplier,
				// "do_not_explode": d.do_not_explode
			},
			callback: function(r) {
				d = locals[cdt][cdn];

				$.extend(d, r.message);
				
				refresh_field("items");
				
				doc = locals[doc.doctype][doc.name];
				calculate_rm_cost(doc);
			},
			freeze: true
		});
	}
};

// rm : raw material
var calculate_rm_cost = function(doc) {
	var rm = doc.items || [];
	var total_rm_cost = 0;
	var base_total_rm_cost = 0;
	for(var i=0;i<rm.length;i++) {
		var amount = flt(rm[i].rate) * flt(rm[i].qty);
		// var base_amount = amount * flt(doc.conversion_rate);

		// TODO FIX BY ME
		/* frappe.model.set_value('Product Bundle Item', rm[i].name, 'base_stock_rate',
			flt(rm[i].stock_rate) * flt(doc.conversion_rate)); */

		frappe.model.set_value('Product Bundle Item', rm[i].name, 'amount', amount);

		/* frappe.model.set_value('BOM Item', rm[i].name, 'base_rate',
			flt(rm[i].rate) * flt(doc.conversion_rate));
		frappe.model.set_value('BOM Item', rm[i].name, 'base_amount', base_amount);
		frappe.model.set_value('BOM Item', rm[i].name,
			'qty_consumed_per_unit', flt(rm[i].stock_qty)/flt(doc.quantity)); */

		total_rm_cost += amount;
		// base_total_rm_cost += base_amount;
	}
	cur_frm.set_value("total", total_rm_cost);
};