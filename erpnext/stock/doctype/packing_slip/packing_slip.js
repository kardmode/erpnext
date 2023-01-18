// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt


frappe.ui.form.on('Packing Slip', {
	onload: function(frm) {
		var me = this;
		if(frm.doc.__islocal) {
			frm.set_value("posting_date",frappe.datetime.get_today());
		}
		
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'customer', doctype: 'Customer' }
		
		$.each([
			["customer", "customer"]],
			function(i, opts) {
				if(frm.fields_dict[opts[0]])
					frm.set_query(opts[0], erpnext.queries[opts[1]]);
			});
		
		frm.updating_party_details = false;
		
		//frm.add_fetch('delivery_note', 'company', 'company');
		//frm.add_fetch('delivery_note', 'title', 'title');
		//frm.add_fetch('delivery_note', 'customer', 'customer');
		//frm.add_fetch('delivery_note', 'project', 'project');
		//frm.add_fetch('delivery_note', 'shipping_address', 'shipping_address');
		frm.set_query('contact_person', erpnext.queries.contact_query);
	},
	
	customer: function(frm) {
		erpnext.utils.get_party_details(frm, null, null, function(){});
	},
	shipping_address_name: function(frm) {
		erpnext.utils.get_address_display(frm, "shipping_address_name", "shipping_address");
	},
	customer_address: function(frm) {
		erpnext.utils.get_address_display(frm, "customer_address", "address_display");
	},
	validate_company_and_party() {
		return true;
	}
});

frappe.ui.form.on('Packing Slip Item', {
	item_code: (frm, cdt, cdn) => {
		let row = frappe.get_doc(cdt, cdn);
		if(row.qty == null)
			frappe.model.set_value(cdt, cdn, 'qty', 1);

		
		if (row.item_code) {
			get_item_details(row.item_code).then(data => {
				frappe.model.set_value(cdt, cdn, 'item_name', data.item_name);
				frappe.model.set_value(cdt, cdn, 'description', data.description);
				frappe.model.set_value(cdt, cdn, 'uom', data.uom);
				frappe.model.set_value(cdt, cdn, 'stock_uom', data.stock_uom);
				frappe.model.set_value(cdt, cdn, 'conversion_factor', data.conversion_factor);
				frappe.model.set_value(cdt, cdn, 'net_weight', data.weight_per_unit);
				frappe.model.set_value(cdt, cdn, 'weight_uom', data.weight_uom);
				frappe.model.set_value(cdt, cdn, 'hs_code', data.customs_tariff_number);
			});
		}
	},
	uom: (frm, cdt, cdn) => {
		let row = frappe.get_doc(cdt, cdn);
		if (row.uom) {
			get_item_details(row.item_code, row.uom).then(data => {
				frappe.model.set_value(cdt, cdn, 'conversion_factor', data.conversion_factor);
			});
		}
	},
	qty: (frm, cdt, cdn) => {
		let row = frappe.get_doc(cdt, cdn);
		frappe.model.set_value(cdt, cdn, 'stock_qty', row.qty * row.conversion_factor);
	},
	conversion_factor: (frm, cdt, cdn) => {
		let row = frappe.get_doc(cdt, cdn);
		frappe.model.set_value(cdt, cdn, 'stock_qty', row.qty * row.conversion_factor);
	}
});

function get_item_details(item_code, uom=null) {
	if (item_code) {
		return frappe.xcall('erpnext.stock.doctype.packing_slip.packing_slip.get_item_details', {
			item_code,
			uom
		});
	}
}

cur_frm.fields_dict['delivery_note'].get_query = function(doc, cdt, cdn) {
	return{
		filters:[['docstatus','<','2']]
	}
}


cur_frm.fields_dict['items'].grid.get_field('item_code').get_query = function(doc, cdt, cdn) {
	if(!doc.delivery_note) {
		//frappe.throw(__("Please select a Delivery Note"));
	} else {
		return {
			query: "erpnext.stock.doctype.packing_slip.packing_slip.item_details",
			filters:{ 'delivery_note': doc.delivery_note}
		}
	}
}

cur_frm.cscript.onload_post_render = function(doc, cdt, cdn) {
	if(doc.delivery_note && doc.__islocal) {
		cur_frm.cscript.get_items(doc, cdt, cdn);
	}
}

cur_frm.cscript.get_items = function(doc, cdt, cdn) {
	return this.frm.call({
		doc: this.frm.doc,
		method: "get_items",
		callback: function(r) {
			if(!r.exc) 
			{
				cur_frm.refresh();
				cur_frm.dirty();
			}
			
		}
	});
}

cur_frm.cscript.refresh = function(doc, dt, dn) {
	//cur_frm.toggle_display("misc_details", doc.amended_from);
}

cur_frm.cscript.validate = function(doc, cdt, cdn) {
	cur_frm.cscript.validate_case_nos(doc);
	cur_frm.cscript.validate_calculate_item_details(doc);
}

// To Case No. cannot be less than From Case No.
cur_frm.cscript.validate_case_nos = function(doc) {
	doc = locals[doc.doctype][doc.name];
	if(cint(doc.from_case_no)==0) {
		frappe.msgprint(__("The 'From Package No.' field must neither be empty nor it's value less than 1."));
		frappe.validated = false;
	} else if(!cint(doc.to_case_no)) {
		doc.to_case_no = doc.from_case_no;
		refresh_field('to_case_no');
	} else if(cint(doc.to_case_no) < cint(doc.from_case_no)) {
		frappe.msgprint(__("'To Case No.' cannot be less than 'From Case No.'"));
		frappe.validated = false;
	}
}


cur_frm.cscript.validate_calculate_item_details = function(doc) {
	doc = locals[doc.doctype][doc.name];
	var ps_detail = doc.items || [];

	cur_frm.cscript.validate_duplicate_items(doc, ps_detail);
	cur_frm.cscript.calc_net_total_pkg(doc, ps_detail);
}


// Do not allow duplicate items i.e. items with same item_code
// Also check for 0 qty
cur_frm.cscript.validate_duplicate_items = function(doc, ps_detail) {
	for(var i=0; i<ps_detail.length; i++) {
		for(var j=0; j<ps_detail.length; j++) {
			if(i!=j && ps_detail[i].item_code && ps_detail[i].item_code==ps_detail[j].item_code) {
				frappe.msgprint(__("You have entered duplicate items. Please rectify and try again."));
				frappe.validated = false;
				return;
			}
		}
		if(flt(ps_detail[i].qty)<=0) {
			frappe.msgprint(__("Invalid quantity specified for item {0}. Quantity should be greater than 0.", [ps_detail[i].item_code]));
			frappe.validated = false;
		}
	}
}


// Calculate Net Weight of Package
cur_frm.cscript.calc_net_total_pkg = function(doc, ps_detail) {
	var net_weight_pkg = 0;
	doc.net_weight_uom = (ps_detail && ps_detail.length) ? ps_detail[0].weight_uom : '';
	doc.gross_weight_uom = doc.net_weight_uom;

	for(var i=0; i<ps_detail.length; i++) {
		var item = ps_detail[i];
		if(item.weight_uom != doc.net_weight_uom) {
			frappe.msgprint(__("Different UOM for items will lead to incorrect (Total) Net Weight value. Make sure that Net Weight of each item is in the same UOM."));
			frappe.validated = false;
		}
		net_weight_pkg += flt(item.net_weight) * flt(item.qty);
	}

	doc.net_weight_pkg = roundNumber(net_weight_pkg, 2);
	if(!flt(doc.gross_weight_pkg)) {
		doc.gross_weight_pkg = doc.net_weight_pkg;
	}
	refresh_many(['net_weight_pkg', 'net_weight_uom', 'gross_weight_uom', 'gross_weight_pkg']);
}

// var make_row = function(title,val,bold){
	// var bstart = '<b>'; var bend = '</b>';
	// return '<tr><td class="datalabelcell">'+(bold?bstart:'')+title+(bold?bend:'')+'</td>'
	// +'<td class="datainputcell" style="text-align:left;">'+ val +'</td>'
	// +'</tr>'
// }

// cur_frm.pformat.net_weight_pkg= function(doc){
	// return '<table style="width:100%">' + make_row('Net Weight', doc.net_weight_pkg) + '</table>'
// }

// cur_frm.pformat.gross_weight_pkg= function(doc){
	// return '<table style="width:100%">' + make_row('Gross Weight', doc.gross_weight_pkg) + '</table>'
// }

// TODO: validate gross weight field
