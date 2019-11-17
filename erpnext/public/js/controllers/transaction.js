// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

erpnext.TransactionController = erpnext.taxes_and_totals.extend({
	setup: function() {
		this._super();
		frappe.flags.hide_serial_batch_dialog = false;
		frappe.ui.form.on(this.frm.doctype + " Item", "rate", function(frm, cdt, cdn) {
			var item = frappe.get_doc(cdt, cdn);
			var has_margin_field = frappe.meta.has_field(cdt, 'margin_type');

			frappe.model.round_floats_in(item, ["rate", "price_list_rate"]);

			if(item.price_list_rate) {
				if(item.rate > item.price_list_rate && has_margin_field) {
					// if rate is greater than price_list_rate, set margin
					// or set discount
					item.discount_percentage = 0;
					item.margin_type = 'Amount';
					item.margin_rate_or_amount = flt(item.rate - item.price_list_rate,
						precision("margin_rate_or_amount", item));
					item.rate_with_margin = item.rate;
				} else {
					item.discount_percentage = flt((1 - item.rate / item.price_list_rate) * 100.0,
						precision("discount_percentage", item));
					item.margin_type = '';
					item.margin_rate_or_amount = 0;
					item.rate_with_margin = 0;
				}
			} else {
				item.discount_percentage = 0.0;
				item.margin_type = '';
				item.margin_rate_or_amount = 0;
				item.rate_with_margin = 0;
			}
			item.base_rate_with_margin = item.rate_with_margin * flt(frm.doc.conversion_rate);

			cur_frm.cscript.set_gross_profit(item);
			cur_frm.cscript.calculate_taxes_and_totals();

		});



		frappe.ui.form.on(this.frm.cscript.tax_table, "rate", function(frm, cdt, cdn) {
			cur_frm.cscript.calculate_taxes_and_totals();
		});

		frappe.ui.form.on(this.frm.cscript.tax_table, "tax_amount", function(frm, cdt, cdn) {
			cur_frm.cscript.calculate_taxes_and_totals();
		});

		frappe.ui.form.on(this.frm.cscript.tax_table, "row_id", function(frm, cdt, cdn) {
			cur_frm.cscript.calculate_taxes_and_totals();
		});

		frappe.ui.form.on(this.frm.cscript.tax_table, "included_in_print_rate", function(frm, cdt, cdn) {
			cur_frm.cscript.set_dynamic_labels();
			cur_frm.cscript.calculate_taxes_and_totals();
		});

		frappe.ui.form.on(this.frm.doctype, "apply_discount_on", function(frm) {
			if(frm.doc.additional_discount_percentage) {
				frm.trigger("additional_discount_percentage");
			} else {
				cur_frm.cscript.calculate_taxes_and_totals();
			}
		});

		frappe.ui.form.on(this.frm.doctype, "additional_discount_percentage", function(frm) {
			if(!frm.doc.apply_discount_on) {
				frappe.msgprint(__("Please set 'Apply Additional Discount On'"));
				return;
			}

			frm.via_discount_percentage = true;

			if(frm.doc.additional_discount_percentage && frm.doc.discount_amount) {
				// Reset discount amount and net / grand total
				frm.doc.discount_amount = 0;
				frm.cscript.calculate_taxes_and_totals();
			}

			var total = flt(frm.doc[frappe.model.scrub(frm.doc.apply_discount_on)]);
			var discount_amount = flt(total*flt(frm.doc.additional_discount_percentage) / 100,
				precision("discount_amount"));

			frm.set_value("discount_amount", discount_amount)
				.then(() => delete frm.via_discount_percentage);
		});

		frappe.ui.form.on(this.frm.doctype, "discount_amount", function(frm) {
			frm.cscript.set_dynamic_labels();

			if (!frm.via_discount_percentage) {
				frm.doc.additional_discount_percentage = 0;
			}

			frm.cscript.calculate_taxes_and_totals();
		});

		frappe.ui.form.on(this.frm.doctype + " Item", {
			items_add: function(frm, cdt, cdn) {
				var item = frappe.get_doc(cdt, cdn);
				if(!item.warehouse && frm.doc.set_warehouse) {
					item.warehouse = frm.doc.set_warehouse;
				}
			}
		});

		var me = this;
		if(this.frm.fields_dict["items"].grid.get_field('batch_no')) {
			this.frm.set_query("batch_no", "items", function(doc, cdt, cdn) {
				return me.set_query_for_batch(doc, cdt, cdn);
			});
		}
		

		if(
			this.frm.docstatus < 2
			&& this.frm.fields_dict["payment_terms_template"]
			&& this.frm.fields_dict["payment_schedule"]
			&& this.frm.doc.payment_terms_template
			&& !this.frm.doc.payment_schedule.length
		){
			this.frm.trigger("payment_terms_template");
		}

		if(this.frm.fields_dict["taxes"]) {
			this["taxes_remove"] = this.calculate_taxes_and_totals;
		}

		if(this.frm.fields_dict["items"]) {
			this["items_remove"] = this.calculate_net_weight;
		}

		if(this.frm.fields_dict["recurring_print_format"]) {
			this.frm.set_query("recurring_print_format", function(doc) {
				return{
					filters: [
						['Print Format', 'doc_type', '=', cur_frm.doctype],
					]
				};
			});
		}

		if(this.frm.fields_dict["return_against"]) {
			this.frm.set_query("return_against", function(doc) {
				var filters = {
					"docstatus": 1,
					"is_return": 0,
					"company": doc.company
				};
				if (me.frm.fields_dict["customer"] && doc.customer) filters["customer"] = doc.customer;
				if (me.frm.fields_dict["supplier"] && doc.supplier) filters["supplier"] = doc.supplier;

				return {
					filters: filters
				};
			});
		}
		
		erpnext.queries.setup_project_query(this.frm);
		
		
		
	},
	onload: function() {
		var me = this;

		if(this.frm.doc.__islocal) {
			var currency = frappe.defaults.get_user_default("currency");

			let set_value = (fieldname, value) => {
				if(me.frm.fields_dict[fieldname] && !me.frm.doc[fieldname]) {
					return me.frm.set_value(fieldname, value);
				}
			};

			return frappe.run_serially([
				() => set_value('currency', currency),
				() => set_value('price_list_currency', currency),
				() => set_value('status', 'Draft'),
				() => set_value('is_subcontracted', 'No'),
				() => {
					if(this.frm.doc.company && !this.frm.doc.amended_from) {
						this.frm.trigger("company");
					}
				}
			]);
		}
	},

	is_return: function() {
		if(!this.frm.doc.is_return && this.frm.doc.return_against) {
			this.frm.set_value('return_against', '');
		}
	},

	setup_quality_inspection: function() {
		if(!in_list(["Delivery Note", "Sales Invoice", "Purchase Receipt", "Purchase Invoice"], this.frm.doc.doctype)) {
			return;
		}
		var me = this;
		var inspection_type = in_list(["Purchase Receipt", "Purchase Invoice"], this.frm.doc.doctype)
			? "Incoming" : "Outgoing";

		var quality_inspection_field = this.frm.get_docfield("items", "quality_inspection");
		quality_inspection_field.get_route_options_for_new_doc = function(row) {
			if(me.frm.is_new()) return;
			return {
				"inspection_type": inspection_type,
				"reference_type": me.frm.doc.doctype,
				"reference_name": me.frm.doc.name,
				"item_code": row.doc.item_code,
				"description": row.doc.description,
				"item_serial_no": row.doc.serial_no ? row.doc.serial_no.split("\n")[0] : null,
				"batch_no": row.doc.batch_no
			}
		}

		this.frm.set_query("quality_inspection", "items", function(doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: {
					docstatus: 1,
					inspection_type: inspection_type,
					reference_name: doc.name,
					item_code: d.item_code
				}
			}
		});
	},

	make_payment_request: function() {
		var me = this;
		const payment_request_type = (in_list(['Sales Order', 'Sales Invoice'], this.frm.doc.doctype))
			? "Inward" : "Outward";

		frappe.call({
			method:"erpnext.accounts.doctype.payment_request.payment_request.make_payment_request",
			args: {
				dt: me.frm.doc.doctype,
				dn: me.frm.doc.name,
				recipient_id: me.frm.doc.contact_email,
				payment_request_type: payment_request_type,
				party_type: payment_request_type == 'Outward' ? "Supplier" : "Customer",
				party: payment_request_type == 'Outward' ? me.frm.doc.supplier : me.frm.doc.customer
			},
			callback: function(r) {
				if(!r.exc){
					var doc = frappe.model.sync(r.message);
					frappe.set_route("Form", r.message.doctype, r.message.name);
				}
			}
		})
	},

	onload_post_render: function() {
		if(this.frm.doc.__islocal && !(this.frm.doc.taxes || []).length
			&& !(this.frm.doc.__onload ? this.frm.doc.__onload.load_after_mapping : false)) {
			frappe.after_ajax(() => this.apply_default_taxes());
		} else if(this.frm.doc.__islocal && this.frm.doc.company && this.frm.doc["items"]
			&& !this.frm.doc.is_pos) {
			frappe.after_ajax(() => this.calculate_taxes_and_totals());
		}
		if(frappe.meta.get_docfield(this.frm.doc.doctype + " Item", "item_code")) {
			this.setup_item_selector();
			this.frm.get_field("items").grid.set_multiple_add("item_code", "qty");
		}
	},

	refresh: function() {
		erpnext.toggle_naming_series();
		erpnext.hide_company();

		
		this.set_dynamic_labels();
		
		if (this.frm.doc.docstatus==0) {
			cur_frm.add_custom_button(__('CSV'),
			function() {
				var me = this;

				var dialog = new frappe.ui.Dialog({
					title: "Add items from CSV",
					fields: [
						{"fieldtype": "HTML", "label": __(""), "fieldname": "import_html",
							"reqd": 1 },
						{"fieldtype": "HTML", "label": __(""), "fieldname": "import_log",
							"reqd": 1 },
						{"fieldtype": "Check", "label": __("Keep Previous Entries"), "fieldname": "keep_previous"},
						{"fieldtype": "Button", "label": __("Update"), "fieldname": "update"},
					]
				});

				var $wrapper = $(dialog.fields_dict.import_html.wrapper).empty();

				// upload
				frappe.upload.make({
					parent: $wrapper,
					args: {
						method: 'erpnext.controllers.queries.get_items_from_csv',
					},
					btn: $(dialog.fields_dict.update.wrapper),
					callback: function(attachment, r) {
						var $log_wrapper = $(dialog.fields_dict.import_log.wrapper).empty();
						var $keep_previous = $(dialog.fields_dict.keep_previous.wrapper).find('input[type="checkbox"]');
						
						var items = r.message.items;
						var messages = r.message.messages;
						var error = r.message.error;
						if(!r.messages) r.messages = [];

						r.messages = $.map(messages, function(v) {
							return v;
						});
						
						if (error){
							r.messages = ["<h4 style='color:red'>"+__("Import Failed")+"</h4>"]
								.concat(r.messages)

						} else {
							r.messages = ["<h4 style='color:green'>"+__("Import Succeeded")+"</h4>"]
								.concat(r.messages)
							
							if(!$keep_previous.is(":checked")){	
								 cur_frm.doc.items = [];
							}
							$.each(items, function(i, item) {
								var d = frappe.model.add_child(cur_frm.doc, cur_frm.doctype + " Item", "items");
									d.item_code = item.item_code;
									d.qty = item.qty;
									d.page_break = item.page_break;
									console.log(d);
									cur_frm.script_manager.trigger("item_code", d.doctype, d.name);
									
								});
						
							cur_frm.refresh_field('items');
							me.calculate_taxes_and_totals();

						}
						
						$.each(r.messages, function(i, v) {
							var $p = $('<p>').html(v).appendTo($log_wrapper);
							if(v.substr(0,5)=='Error') {
								$p.css('color', 'red');
							}else if(v.substr(0,6)=='Header') {
								$p.css('color', 'green');
							} else if(v.substr(0,7)=='Updated') {
								$p.css('color', 'green');
							}
						});
					},
					is_private: false
				});

				
				dialog.show();

				
				
			}, __("Get items from"), "btn-default");
	
			
			cur_frm.add_custom_button(__('Document'),
				function() {
					/* erpnext.utils.map_current_doc({
						method: "erpnext.selling.doctype.quotation.quotation.make_quotation",
						source_doctype: "Product Bundle",
						get_query_filters: {
						}
					}) */
					cur_frm.trigger('get_items_from');
					
				}, __("Copy Items From"), "btn-default");
			
			cur_frm.add_custom_button(__('Room Quantity'),
				function() {
					/* erpnext.utils.map_current_doc({
						method: "erpnext.selling.doctype.quotation.quotation.make_quotation",
						source_doctype: "Product Bundle",
						get_query_filters: {
						}
					}) */
					cur_frm.trigger('multiply_room');
					
				}, __("Modify"), "btn-default");
				
			cur_frm.add_custom_button(__('Items Quantity'),
				function() {
					/* erpnext.utils.map_current_doc({
						method: "erpnext.selling.doctype.quotation.quotation.make_quotation",
						source_doctype: "Product Bundle",
						get_query_filters: {
						}
					}) */
					cur_frm.trigger('multiply_items');
					
				}, __("Modify"), "btn-default");
			cur_frm.add_custom_button(__('Items Rate'),
				function() {

					cur_frm.trigger('multiply_rate');
					
				}, __("Modify"), "btn-default");
			
			cur_frm.add_custom_button(__('Pro Bata'),
				function() {

					cur_frm.trigger('pro_rata');
					
				}, __("Modify"), "btn-default");
			
		}
		
		
		// this.setup_sms();
		this.setup_quality_inspection();
		this.frm.fields_dict["scan_barcode"] && this.frm.fields_dict["scan_barcode"].set_value("");
		this.frm.fields_dict["scan_barcode"] && this.frm.fields_dict["scan_barcode"].set_new_description("");
	},

	scan_barcode: function() {
		let scan_barcode_field = this.frm.fields_dict["scan_barcode"];

		let show_description = function(idx, exist = null) {
			if (exist) {
				scan_barcode_field.set_new_description(__('Row #{0}: Qty increased by 1', [idx]));
			} else {
				scan_barcode_field.set_new_description(__('Row #{0}: Item added', [idx]));
			}
		}

		if(this.frm.doc.scan_barcode) {
			frappe.call({
				method: "erpnext.selling.page.point_of_sale.point_of_sale.search_serial_or_batch_or_barcode_number",
				args: { search_value: this.frm.doc.scan_barcode }
			}).then(r => {
				const data = r && r.message;
				if (!data || Object.keys(data).length === 0) {
					scan_barcode_field.set_new_description(__('Cannot find Item with this barcode'));
					return;
				}

				let cur_grid = this.frm.fields_dict.items.grid;

				let row_to_modify = null;
				const existing_item_row = this.frm.doc.items.find(d => d.item_code === data.item_code);
				const blank_item_row = this.frm.doc.items.find(d => !d.item_code);

				if (existing_item_row) {
					row_to_modify = existing_item_row;
				} else if (blank_item_row) {
					row_to_modify = blank_item_row;
				}

				if (!row_to_modify) {
					// add new row
					row_to_modify = frappe.model.add_child(this.frm.doc, cur_grid.doctype, 'items');
				}

				show_description(row_to_modify.idx, row_to_modify.item_code);

				this.frm.from_barcode = true;
				frappe.model.set_value(row_to_modify.doctype, row_to_modify.name, {
					item_code: data.item_code,
					qty: (row_to_modify.qty || 0) + 1
				});

				['serial_no', 'batch_no', 'barcode'].forEach(field => {
					if (data[field] && frappe.meta.has_field(row_to_modify.doctype, field)) {
						frappe.model.set_value(row_to_modify.doctype,
							row_to_modify.name, field, data[field]);
					}
				});

				scan_barcode_field.set_value('');
			});
		}
		return false;
	},

	apply_default_taxes: function() {
		var me = this;
		var taxes_and_charges_field = frappe.meta.get_docfield(me.frm.doc.doctype, "taxes_and_charges",
			me.frm.doc.name);

		if (!this.frm.doc.taxes_and_charges && this.frm.doc.taxes) {
			return;
		}

		if (taxes_and_charges_field) {
			return frappe.call({
				method: "erpnext.controllers.accounts_controller.get_default_taxes_and_charges",
				args: {
					"master_doctype": taxes_and_charges_field.options,
					"tax_template": me.frm.doc.taxes_and_charges,
					"company": me.frm.doc.company
				},
				callback: function(r) {
					if(!r.exc && r.message) {
						frappe.run_serially([
							() => {
								// directly set in doc, so as not to call triggers
								if(r.message.taxes_and_charges) {
									me.frm.doc.taxes_and_charges = r.message.taxes_and_charges;
								}

								// set taxes table
								if(r.message.taxes) {
									me.frm.set_value("taxes", r.message.taxes);
								}
							},
							() => me.set_dynamic_labels(),
							() => me.calculate_taxes_and_totals()
						]);
					}
				}
			});
		}
	},

	setup_sms: function() {
		var me = this;
		if(this.frm.doc.docstatus===1 && !in_list(["Lost", "Stopped", "Closed"], this.frm.doc.status)
			&& this.frm.doctype != "Purchase Invoice") {
			this.frm.page.add_menu_item(__('Send SMS'), function() { me.send_sms(); });
		}
	},

	send_sms: function() {
		var sms_man = new erpnext.SMSManager(this.frm.doc);
	},

	barcode: function(doc, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.barcode=="" || d.barcode==null) {
			// barcode cleared, remove item
			d.item_code = "";
		}

		this.frm.from_barcode = true;
		this.item_code(doc, cdt, cdn);
	},

	item_code: function(doc, cdt, cdn) {
		var me = this;
		var item = frappe.get_doc(cdt, cdn);
		var update_stock = 0, show_batch_dialog = 0;
		if(['Sales Invoice'].includes(this.frm.doc.doctype)) {
			update_stock = cint(me.frm.doc.update_stock);
			show_batch_dialog = update_stock;

		} else if((this.frm.doc.doctype === 'Purchase Receipt' && me.frm.doc.is_return) ||
			this.frm.doc.doctype === 'Delivery Note') {
			show_batch_dialog = 1;
		}
		// clear barcode if setting item (else barcode will take priority)
		if(!this.frm.from_barcode) {
			item.barcode = null;
		}

		this.frm.from_barcode = false;
		if(item.item_code || item.barcode || item.serial_no) {
			if(!this.validate_company_and_party()) {
				this.frm.fields_dict["items"].grid.grid_rows[item.idx - 1].remove();
			} else {
				return this.frm.call({
					method: "erpnext.stock.get_item_details.get_item_details",
					child: item,
					args: {
						args: {
							item_code: item.item_code,
							barcode: item.barcode,
							serial_no: item.serial_no,
							set_warehouse: me.frm.doc.set_warehouse,
							warehouse: item.warehouse,
							customer: me.frm.doc.customer || me.frm.doc.party_name,
							quotation_to: me.frm.doc.quotation_to,
							supplier: me.frm.doc.supplier,
							currency: me.frm.doc.currency,
							update_stock: update_stock,
							conversion_rate: me.frm.doc.conversion_rate,
							price_list: me.frm.doc.selling_price_list || me.frm.doc.buying_price_list,
							price_list_currency: me.frm.doc.price_list_currency,
							plc_conversion_rate: me.frm.doc.plc_conversion_rate,
							company: me.frm.doc.company,
							order_type: me.frm.doc.order_type,
							is_pos: cint(me.frm.doc.is_pos),
							is_subcontracted: me.frm.doc.is_subcontracted,
							transaction_date: me.frm.doc.transaction_date || me.frm.doc.posting_date,
							ignore_pricing_rule: me.frm.doc.ignore_pricing_rule,
							doctype: me.frm.doc.doctype,
							name: me.frm.doc.name,
							project: item.project || me.frm.doc.project,
							qty: item.qty || 1,
							stock_qty: item.stock_qty,
							conversion_factor: item.conversion_factor,
							weight_per_unit: item.weight_per_unit,
							weight_uom: item.weight_uom,
							uom : item.uom,
							stock_uom: item.stock_uom,
							pos_profile: me.frm.doc.doctype == 'Sales Invoice' ? me.frm.doc.pos_profile : '',
							cost_center: item.cost_center
						}
					},

					callback: function(r) {
						if(!r.exc) {
							frappe.run_serially([
								() => me.frm.script_manager.trigger("price_list_rate", cdt, cdn),
								() => me.toggle_conversion_factor(item),
								() => {
									if(show_batch_dialog && !frappe.flags.hide_serial_batch_dialog) {
										var d = locals[cdt][cdn];
										$.each(r.message, function(k, v) {
											if(!d[k]) d[k] = v;
										});

										erpnext.show_serial_batch_selector(me.frm, d, (item) => {
											me.frm.script_manager.trigger('qty', item.doctype, item.name);
										});
									}
								},
								() => me.conversion_factor(doc, cdt, cdn, true)
							]);
						}
					}
				});
			}
		}
	},

	serial_no: function(doc, cdt, cdn) {
		var me = this;
		var item = frappe.get_doc(cdt, cdn);

		if (item && item.serial_no) {
			if (!item.item_code) {
				this.frm.trigger("item_code", cdt, cdn);
			}
			else {
				var valid_serial_nos = [];

				// Replacing all occurences of comma with carriage return
				var serial_nos = item.serial_no.trim().replace(/,/g, '\n');

				serial_nos = serial_nos.trim().split('\n');

				// Trim each string and push unique string to new list
				for (var x=0; x<=serial_nos.length - 1; x++) {
					if (serial_nos[x].trim() != "" && valid_serial_nos.indexOf(serial_nos[x].trim()) == -1) {
						valid_serial_nos.push(serial_nos[x].trim());
					}
				}

				// Add the new list to the serial no. field in grid with each in new line
				item.serial_no = valid_serial_nos.join('\n');

				refresh_field("serial_no", item.name, item.parentfield);
				if(!doc.is_return && cint(user_defaults.set_qty_in_transactions_based_on_serial_no_input)) {
					frappe.model.set_value(item.doctype, item.name,
						"qty", valid_serial_nos.length / item.conversion_factor);
					frappe.model.set_value(item.doctype, item.name, "stock_qty", valid_serial_nos.length);
				}
			}
		}
	},

	validate: function() {
		this.calculate_taxes_and_totals(false);
	},

	company: function() {
		var me = this;
		var set_pricing = function() {
			if(me.frm.doc.company && me.frm.fields_dict.currency) {
				var company_currency = me.get_company_currency();
				var company_doc = frappe.get_doc(":Company", me.frm.doc.company);

				if (!me.frm.doc.currency) {
					me.frm.set_value("currency", company_currency);
				}

				if (me.frm.doc.currency == company_currency) {
					me.frm.set_value("conversion_rate", 1.0);
				}
				if (me.frm.doc.price_list_currency == company_currency) {
					me.frm.set_value('plc_conversion_rate', 1.0);
				}
				if (company_doc.default_letter_head) {
					if(me.frm.fields_dict.letter_head) {
						me.frm.set_value("letter_head", company_doc.default_letter_head);
					}
				}
				if (company_doc.default_terms && me.frm.doc.doctype != "Purchase Invoice" && frappe.meta.has_field(me.frm.doc.doctype, "tc_name")) {
					me.frm.set_value("tc_name", company_doc.default_terms);
				}

				frappe.run_serially([
					() => me.frm.script_manager.trigger("currency"),
					() => me.apply_default_taxes(),
					() => me.apply_pricing_rule()
				]);
			}
		}

		var set_party_account = function(set_pricing) {
			if (in_list(["Sales Invoice", "Purchase Invoice"], me.frm.doc.doctype)) {
				if(me.frm.doc.doctype=="Sales Invoice") {
					var party_type = "Customer";
					var party_account_field = 'debit_to';
				} else {
					var party_type = "Supplier";
					var party_account_field = 'credit_to';
				}

				var party = me.frm.doc[frappe.model.scrub(party_type)];
				if(party && me.frm.doc.company) {
					return frappe.call({
						method: "erpnext.accounts.party.get_party_account",
						args: {
							company: me.frm.doc.company,
							party_type: party_type,
							party: party
						},
						callback: function(r) {
							if(!r.exc && r.message) {
								me.frm.set_value(party_account_field, r.message);
								set_pricing();
							}
						}
					});
				} else {
					set_pricing();
				}
			} else {
				set_pricing();
			}

		}

		if (this.frm.doc.posting_date) var date = this.frm.doc.posting_date;
		else var date = this.frm.doc.transaction_date;

		if (frappe.meta.get_docfield(this.frm.doctype, "shipping_address") &&
			in_list(['Purchase Order', 'Purchase Receipt', 'Purchase Invoice'], this.frm.doctype)){
			erpnext.utils.get_shipping_address(this.frm, function(){
				set_party_account(set_pricing);
			})
		} else {
			set_party_account(set_pricing);
		}

		if(this.frm.doc.company) {
			erpnext.last_selected_company = this.frm.doc.company;
		}
	},

	transaction_date: function() {
		if (this.frm.doc.transaction_date) {
			this.frm.transaction_date = this.frm.doc.transaction_date;
			frappe.ui.form.trigger(this.frm.doc.doctype, "currency");
		}
	},

	posting_date: function() {
		var me = this;
		if (this.frm.doc.posting_date) {
			this.frm.posting_date = this.frm.doc.posting_date;

			if ((this.frm.doc.doctype == "Sales Invoice" && this.frm.doc.customer) ||
				(this.frm.doc.doctype == "Purchase Invoice" && this.frm.doc.supplier)) {
				return frappe.call({
					method: "erpnext.accounts.party.get_due_date",
					args: {
						"posting_date": me.frm.doc.posting_date,
						"party_type": me.frm.doc.doctype == "Sales Invoice" ? "Customer" : "Supplier",
						"bill_date": me.frm.doc.bill_date,
						"party": me.frm.doc.doctype == "Sales Invoice" ? me.frm.doc.customer : me.frm.doc.supplier,
						"company": me.frm.doc.company
					},
					callback: function(r, rt) {
						if(r.message) {
							me.frm.doc.due_date = r.message;
							refresh_field("due_date");
							frappe.ui.form.trigger(me.frm.doc.doctype, "currency");
							me.recalculate_terms();
						}
					}
				})
			} else {
				frappe.ui.form.trigger(me.frm.doc.doctype, "currency");
			}
		}
	},
	
	due_date: function() {
		// due_date is to be changed, payment terms template and/or payment schedule must
		// be removed as due_date is automatically changed based on payment terms
		if (this.frm.doc.due_date && !this.frm.updating_party_details && !this.frm.doc.is_pos) {
			if (this.frm.doc.payment_terms_template ||
				(this.frm.doc.payment_schedule && this.frm.doc.payment_schedule.length)) {
				var message1 = "";
				var message2 = "";
				var final_message = "Please clear the ";

				if (this.frm.doc.payment_terms_template) {
					message1 = "selected Payment Terms Template";
					final_message = final_message + message1;
				}
				else if((this.frm.doc.payment_schedule || []).length) 
				{
					this.frm.doc.payment_schedule = [];
					return;
				}

				if ((this.frm.doc.payment_schedule || []).length) {
					message2 = "Payment Schedule Table";
					if (message1.length !== 0) message2 = " and " + message2;
					final_message = final_message + message2;
				}
				frappe.msgprint(final_message);
			}
		}
	},


	due_date: function() {
		// due_date is to be changed, payment terms template and/or payment schedule must
		// be removed as due_date is automatically changed based on payment terms
		if (this.frm.doc.due_date && !this.frm.updating_party_details && !this.frm.doc.is_pos) {
			if (this.frm.doc.payment_terms_template ||
				(this.frm.doc.payment_schedule && this.frm.doc.payment_schedule.length)) {
				var message1 = "";
				var message2 = "";
				var final_message = "Please clear the ";

				if (this.frm.doc.payment_terms_template) {
					message1 = "selected Payment Terms Template";
					final_message = final_message + message1;
				}

				if ((this.frm.doc.payment_schedule || []).length) {
					message2 = "Payment Schedule Table";
					if (message1.length !== 0) message2 = " and " + message2;
					final_message = final_message + message2;
				}
				frappe.msgprint(final_message);
			}
		}
	},

	bill_date: function() {
		this.posting_date();
	},

	recalculate_terms: function() {
		const doc = this.frm.doc;
		if (doc.payment_terms_template) {
			this.payment_terms_template();
		} else if (doc.payment_schedule) {
			const me = this;
			doc.payment_schedule.forEach(
				function(term) {
					if (term.payment_term) {
						me.payment_term(doc, term.doctype, term.name);
					} else {
						frappe.model.set_value(
							term.doctype, term.name, 'due_date',
							doc.posting_date || doc.transaction_date
						);
					}
				}
			);
		}
	},

	get_company_currency: function() {
		return erpnext.get_currency(this.frm.doc.company);
	},

	contact_person: function() {
		erpnext.utils.get_contact_details(this.frm);
	},

	currency: function() {
		/* manqala 19/09/2016: let the translation date be whichever of the transaction_date or posting_date is available */
		var transaction_date = this.frm.doc.transaction_date || this.frm.doc.posting_date;
		/* end manqala */
		var me = this;
		this.set_dynamic_labels();
		var company_currency = this.get_company_currency();
		
		/* frappe.call({
			method:'erpnext.stock.doctype.price_list.price_list.get_price_list_with_currency',
			args:{
				currency: this.frm.doc.currency,
				doctype: this.frm.doctype
			},
			callback:function (r) {
				console.log(r);
				if (r.message){
					
					if(me.frm.doctype === "Purchase Order")
						me.frm.set_value("buying_price_list",r.message.name);
				}
					
			}
		}) */

		// Added `ignore_pricing_rule` to determine if document is loading after mapping from another doc
		if(this.frm.doc.currency && this.frm.doc.currency !== company_currency
				&& !this.frm.doc.ignore_pricing_rule) {

			this.get_exchange_rate(transaction_date, this.frm.doc.currency, company_currency,
				function(exchange_rate) {
					me.frm.set_value("conversion_rate", exchange_rate);
				});
		} else {
			this.conversion_rate();
		}
	},

	conversion_rate: function() {
		const me = this.frm;
		if(this.frm.doc.currency === this.get_company_currency()) {
			this.frm.set_value("conversion_rate", 1.0);
		}
		if(this.frm.doc.currency === this.frm.doc.price_list_currency &&
			this.frm.doc.plc_conversion_rate !== this.frm.doc.conversion_rate) {
			this.frm.set_value("plc_conversion_rate", this.frm.doc.conversion_rate);
		}

		if(flt(this.frm.doc.conversion_rate)>0.0) {
			if(this.frm.doc.ignore_pricing_rule) {
				this.calculate_taxes_and_totals();
			} else if (!this.in_apply_price_list){
				this.set_actual_charges_based_on_currency();
				this.apply_price_list();
			}

		}
		// Make read only if Accounts Settings doesn't allow stale rates
		this.frm.set_df_property("conversion_rate", "read_only", erpnext.stale_rate_allowed() ? 0 : 1);
	},

	shipping_rule: function() {
		var me = this;
		if(this.frm.doc.shipping_rule) {
			return this.frm.call({
				doc: this.frm.doc,
				method: "apply_shipping_rule",
				callback: function(r) {
					if(!r.exc) {
						me.calculate_taxes_and_totals();
					}
				}
			}).fail(() => this.frm.set_value('shipping_rule', ''));
		}
		else {
			me.calculate_taxes_and_totals();
		}
	},

	set_actual_charges_based_on_currency: function() {
		var me = this;
		$.each(this.frm.doc.taxes || [], function(i, d) {
			if(d.charge_type == "Actual") {
				frappe.model.set_value(d.doctype, d.name, "tax_amount",
					flt(d.tax_amount) / flt(me.frm.doc.conversion_rate));
			}
		});
	},

	get_exchange_rate: function(transaction_date, from_currency, to_currency, callback) {
		var args;
		if (["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"].includes(this.frm.doctype)) {
			args = "for_selling";
		}
		else if (["Purchase Order", "Purchase Receipt", "Purchase Invoice"].includes(this.frm.doctype)) {
			args = "for_buying";
		}

		if (!transaction_date || !from_currency || !to_currency) return;
		return frappe.call({
			method: "erpnext.setup.utils.get_exchange_rate",
			args: {
				transaction_date: transaction_date,
				from_currency: from_currency,
				to_currency: to_currency,
				args: args
			},
			callback: function(r) {
				callback(flt(r.message));
			}
		});
	},

	price_list_currency: function() {
		var me=this;
		this.set_dynamic_labels();

		var company_currency = this.get_company_currency();
		// Added `ignore_pricing_rule` to determine if document is loading after mapping from another doc
		if(this.frm.doc.price_list_currency !== company_currency  && !this.frm.doc.ignore_pricing_rule) {
			this.get_exchange_rate(this.frm.doc.posting_date, this.frm.doc.price_list_currency, company_currency,
				function(exchange_rate) {
					me.frm.set_value("plc_conversion_rate", exchange_rate);
				});
		} else {
			this.plc_conversion_rate();
		}
	},

	plc_conversion_rate: function() {
		if(this.frm.doc.price_list_currency === this.get_company_currency()) {
			this.frm.set_value("plc_conversion_rate", 1.0);
		} else if(this.frm.doc.price_list_currency === this.frm.doc.currency
			&& this.frm.doc.plc_conversion_rate && cint(this.frm.doc.plc_conversion_rate) != 1 &&
			cint(this.frm.doc.plc_conversion_rate) != cint(this.frm.doc.conversion_rate)) {
			this.frm.set_value("conversion_rate", this.frm.doc.plc_conversion_rate);
		}

		if(!this.in_apply_price_list) {
			this.apply_price_list(null, true);
		}
	},

	uom: function(doc, cdt, cdn) {
		var me = this;
		var item = frappe.get_doc(cdt, cdn);
		if(item.item_code && item.uom) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_conversion_factor",
				child: item,
				args: {
					item_code: item.item_code,
					uom: item.uom
				},
				callback: function(r) {
					if(!r.exc) {
						me.conversion_factor(me.frm.doc, cdt, cdn);
					}
				}
			});
		}
	},

	conversion_factor: function(doc, cdt, cdn, dont_fetch_price_list_rate) {
		if(doc.doctype != 'Material Request' && frappe.meta.get_docfield(cdt, "stock_qty", cdn)) {
			var item = frappe.get_doc(cdt, cdn);
			frappe.model.round_floats_in(item, ["qty", "conversion_factor"]);
			item.stock_qty = flt(item.qty * item.conversion_factor, precision("stock_qty", item));
			item.total_weight = flt(item.stock_qty * item.weight_per_unit);
			refresh_field("stock_qty", item.name, item.parentfield);
			refresh_field("total_weight", item.name, item.parentfield);
			this.toggle_conversion_factor(item);
			this.calculate_net_weight();
			if (!dont_fetch_price_list_rate &&
				frappe.meta.has_field(doc.doctype, "price_list_currency")) {
				this.apply_price_list(item, true);
			}
		}
	},

	toggle_conversion_factor: function(item) {
		// toggle read only property for conversion factor field if the uom and stock uom are same
		if(this.frm.get_field('items').grid.fields_map.conversion_factor) {
			this.frm.fields_dict.items.grid.toggle_enable("conversion_factor",
				((item.uom != item.stock_uom) && !frappe.meta.get_docfield(cur_frm.fields_dict.items.grid.doctype, "conversion_factor").read_only)? true: false);
		}

	},

	qty: function(doc, cdt, cdn) {
		this.conversion_factor(doc, cdt, cdn, true);
		this.apply_pricing_rule(frappe.get_doc(cdt, cdn), true);
	},

	service_stop_date: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];

		if(child.service_stop_date) {
			let start_date = Date.parse(child.service_start_date);
			let end_date = Date.parse(child.service_end_date);
			let stop_date = Date.parse(child.service_stop_date);

			if(stop_date < start_date) {
				frappe.model.set_value(cdt, cdn, "service_stop_date", "");
				frappe.throw(__("Service Stop Date cannot be before Service Start Date"));
			} else if (stop_date > end_date) {
				frappe.model.set_value(cdt, cdn, "service_stop_date", "");
				frappe.throw(__("Service Stop Date cannot be after Service End Date"));
			}
		}
	},

	service_start_date: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];

		if(child.service_start_date) {
			frappe.call({
				"method": "erpnext.stock.get_item_details.calculate_service_end_date",
				args: {"args": child},
				callback: function(r) {
					frappe.model.set_value(cdt, cdn, "service_end_date", r.message.service_end_date);
				}
			})
		}
	},

	calculate_net_weight: function(){
		
		/* Calculate Total Net Weight then further applied shipping rule to calculate shipping charges.*/
		var me = this;
		var total = 0;
		var base_weight_uom = "Kg";
		
		if (cur_frm.get_field('net_weight_uom'))
		{
			if (this.frm.doc.net_weight_uom != null)
			{
				base_weight_uom = cur_frm.doc.net_weight_uom;
			}
			else
			{
				cur_frm.set_value("net_weight_uom",base_weight_uom);
			}
			
			$.each(this.frm.doc["items"] || [], function(i, item) {
				if(item.weight_uom)
				{
					var converted_info = convert_weight_unit(item.total_weight,item.weight_uom,base_weight_uom);
					if(converted_info[0])
						total += flt(converted_info[1]);
					else
					{
						frappe.msgprint(__("The weight_uom " + item.weight_uom + " of item " + item.item_code + ",row " + i + " is invalid."));
					}
					
				}
				
			});
			
			cur_frm.set_value("total_net_weight",total);
		}
		
		this.shipping_rule();
	},

	set_dynamic_labels: function() {
		// What TODO? should we make price list system non-mandatory?
		this.frm.toggle_reqd("plc_conversion_rate",
			!!(this.frm.doc.price_list_name && this.frm.doc.price_list_currency));

		var company_currency = this.get_company_currency();
		this.change_form_labels(company_currency);
		this.change_grid_labels(company_currency);
		this.frm.refresh_fields();
	},

	change_form_labels: function(company_currency) {
		var me = this;

		this.frm.set_currency_labels(["base_total", "base_net_total", "base_total_taxes_and_charges",
			"base_discount_amount", "base_grand_total", "base_rounded_total", "base_in_words",
			"base_taxes_and_charges_added", "base_taxes_and_charges_deducted", "total_amount_to_pay",
			"base_paid_amount", "base_write_off_amount", "base_change_amount", "base_operating_cost",
			"base_raw_material_cost", "base_total_cost", "base_scrap_material_cost",
			"base_rounding_adjustment"], company_currency);

		this.frm.set_currency_labels(["total", "net_total", "total_taxes_and_charges", "discount_amount",
			"grand_total", "taxes_and_charges_added", "taxes_and_charges_deducted",
			"rounded_total", "in_words", "paid_amount", "write_off_amount", "operating_cost",
			"scrap_material_cost", "rounding_adjustment", "raw_material_cost",
			"total_cost"], this.frm.doc.currency);

		this.frm.set_currency_labels(["outstanding_amount", "total_advance"],
			this.frm.doc.party_account_currency);

		cur_frm.set_df_property("conversion_rate", "description", "1 " + this.frm.doc.currency
			+ " = [?] " + company_currency);

		if(this.frm.doc.price_list_currency && this.frm.doc.price_list_currency!=company_currency) {
			cur_frm.set_df_property("plc_conversion_rate", "description", "1 "
				+ this.frm.doc.price_list_currency + " = [?] " + company_currency);
		}

		// toggle fields
		this.frm.toggle_display(["conversion_rate", "base_total", "base_net_total",
			"base_total_taxes_and_charges", "base_taxes_and_charges_added", "base_taxes_and_charges_deducted",
			"base_grand_total", "base_rounded_total", "base_in_words", "base_discount_amount",
			"base_paid_amount", "base_write_off_amount", "base_operating_cost", "base_raw_material_cost",
			"base_total_cost", "base_scrap_material_cost", "base_rounding_adjustment"],
		this.frm.doc.currency != company_currency);

		this.frm.toggle_display(["plc_conversion_rate", "price_list_currency"],
			this.frm.doc.price_list_currency != company_currency);

		var show = cint(cur_frm.doc.discount_amount) ||
				((cur_frm.doc.taxes || []).filter(function(d) {return d.included_in_print_rate===1}).length);

		if(frappe.meta.get_docfield(cur_frm.doctype, "net_total"))
			cur_frm.toggle_display("net_total", show);

		if(frappe.meta.get_docfield(cur_frm.doctype, "base_net_total"))
			cur_frm.toggle_display("base_net_total", (show && (me.frm.doc.currency != company_currency)));

	},

	change_grid_labels: function(company_currency) {
		var me = this;

		this.frm.set_currency_labels(["base_rate", "base_net_rate", "base_price_list_rate", "base_amount", "base_net_amount"],
			company_currency, "items");

		this.frm.set_currency_labels(["rate", "net_rate", "price_list_rate", "amount", "net_amount"],
			this.frm.doc.currency, "items");

		if(this.frm.fields_dict["operations"]) {
			this.frm.set_currency_labels(["operating_cost", "hour_rate"], this.frm.doc.currency, "operations");
			this.frm.set_currency_labels(["base_operating_cost", "base_hour_rate"], company_currency, "operations");

			var item_grid = this.frm.fields_dict["operations"].grid;
			$.each(["base_operating_cost", "base_hour_rate"], function(i, fname) {
				if(frappe.meta.get_docfield(item_grid.doctype, fname))
					item_grid.set_column_disp(fname, me.frm.doc.currency != company_currency);
			});
		}

		if(this.frm.fields_dict["scrap_items"]) {
			this.frm.set_currency_labels(["rate", "amount"], this.frm.doc.currency, "scrap_items");
			this.frm.set_currency_labels(["base_rate", "base_amount"], company_currency, "scrap_items");

			var item_grid = this.frm.fields_dict["scrap_items"].grid;
			$.each(["base_rate", "base_amount"], function(i, fname) {
				if(frappe.meta.get_docfield(item_grid.doctype, fname))
					item_grid.set_column_disp(fname, me.frm.doc.currency != company_currency);
			});
		}

		if(this.frm.fields_dict["taxes"]) {
			this.frm.set_currency_labels(["tax_amount", "total", "tax_amount_after_discount"], this.frm.doc.currency, "taxes");

			this.frm.set_currency_labels(["base_tax_amount", "base_total", "base_tax_amount_after_discount"], company_currency, "taxes");
		}

		if(this.frm.fields_dict["advances"]) {
			this.frm.set_currency_labels(["advance_amount", "allocated_amount"],
				this.frm.doc.party_account_currency, "advances");
		}

		// toggle columns
		var item_grid = this.frm.fields_dict["items"].grid;
		$.each(["base_rate", "base_price_list_rate", "base_amount"], function(i, fname) {
			if(frappe.meta.get_docfield(item_grid.doctype, fname))
				item_grid.set_column_disp(fname, me.frm.doc.currency != company_currency);
		});

		var show = (cint(cur_frm.doc.discount_amount)) ||
			((cur_frm.doc.taxes || []).filter(function(d) {return d.included_in_print_rate===1}).length);

		$.each(["net_rate", "net_amount"], function(i, fname) {
			if(frappe.meta.get_docfield(item_grid.doctype, fname))
				item_grid.set_column_disp(fname, show);
		});

		$.each(["base_net_rate", "base_net_amount"], function(i, fname) {
			if(frappe.meta.get_docfield(item_grid.doctype, fname))
				item_grid.set_column_disp(fname, (show && (me.frm.doc.currency != company_currency)));
		});

		// set labels
		var $wrapper = $(this.frm.wrapper);
	},

	recalculate: function() {
		this.calculate_taxes_and_totals();
	},

	recalculate_values: function() {
		this.calculate_taxes_and_totals();
	},

	calculate_charges: function() {
		this.calculate_taxes_and_totals();
	},

	ignore_pricing_rule: function() {
		if(this.frm.doc.ignore_pricing_rule) {
			var me = this;
			var item_list = [];

			$.each(this.frm.doc["items"] || [], function(i, d) {
				if (d.item_code) {
					item_list.push({
						"doctype": d.doctype,
						"name": d.name,
						"pricing_rule": d.pricing_rule
					})
				}
			});
			return this.frm.call({
				method: "erpnext.accounts.doctype.pricing_rule.pricing_rule.remove_pricing_rules",
				args: { item_list: item_list },
				callback: function(r) {
					if (!r.exc && r.message) {
						me._set_values_for_item_list(r.message);
						me.calculate_taxes_and_totals();
						if(me.frm.doc.apply_discount_on) me.frm.trigger("apply_discount_on");
					}
				}
			});
		} else {
			this.apply_pricing_rule();
		}
	},

	apply_pricing_rule: function(item, calculate_taxes_and_totals) {
		var me = this;
		var args = this._get_args(item);
		if (!(args.items && args.items.length)) {
			if(calculate_taxes_and_totals) me.calculate_taxes_and_totals();
			return;
		}
		return this.frm.call({
			method: "erpnext.accounts.doctype.pricing_rule.pricing_rule.apply_pricing_rule",
			args: {	args: args },
			callback: function(r) {
				if (!r.exc && r.message) {
					me._set_values_for_item_list(r.message);
					if(item) me.set_gross_profit(item);
					if(calculate_taxes_and_totals) me.calculate_taxes_and_totals();
					if(me.frm.doc.apply_discount_on) me.frm.trigger("apply_discount_on")
				}
			}
		});
	},

	_get_args: function(item) {
		var me = this;
		return {
			"items": this._get_item_list(item),
			"customer": me.frm.doc.customer || me.frm.doc.party_name,
			"quotation_to": me.frm.doc.quotation_to,
			"customer_group": me.frm.doc.customer_group,
			"territory": me.frm.doc.territory,
			"supplier": me.frm.doc.supplier,
			"supplier_group": me.frm.doc.supplier_group,
			"currency": me.frm.doc.currency,
			"conversion_rate": me.frm.doc.conversion_rate,
			"price_list": me.frm.doc.selling_price_list || me.frm.doc.buying_price_list,
			"price_list_currency": me.frm.doc.price_list_currency,
			"plc_conversion_rate": me.frm.doc.plc_conversion_rate,
			"company": me.frm.doc.company,
			"transaction_date": me.frm.doc.transaction_date || me.frm.doc.posting_date,
			"campaign": me.frm.doc.campaign,
			"sales_partner": me.frm.doc.sales_partner,
			"ignore_pricing_rule": me.frm.doc.ignore_pricing_rule,
			"doctype": me.frm.doc.doctype,
			"name": me.frm.doc.name,
			"is_return": cint(me.frm.doc.is_return),
			"update_stock": in_list(['Sales Invoice', 'Purchase Invoice'], me.frm.doc.doctype) ? cint(me.frm.doc.update_stock) : 0,
			"conversion_factor": me.frm.doc.conversion_factor,
			"pos_profile": me.frm.doc.doctype == 'Sales Invoice' ? me.frm.doc.pos_profile : ''
		};
	},

	_get_item_list: function(item) {
		var item_list = [];
		var append_item = function(d) {
			if (d.item_code) {
				item_list.push({
					"doctype": d.doctype,
					"name": d.name,
					"item_code": d.item_code,
					"item_group": d.item_group,
					"brand": d.brand,
					"qty": d.qty,
					"uom": d.uom,
					"stock_uom": d.stock_uom,
					"parenttype": d.parenttype,
					"parent": d.parent,
					"pricing_rule": d.pricing_rule,
					"warehouse": d.warehouse,
					"serial_no": d.serial_no,
					"discount_percentage": d.discount_percentage || 0.0,
					"conversion_factor": d.conversion_factor || 1.0
				});

				// if doctype is Quotation Item / Sales Order Iten then add Margin Type and rate in item_list
				if (in_list(["Quotation Item", "Sales Order Item", "Delivery Note Item", "Sales Invoice Item"]), d.doctype){
					item_list[0]["margin_type"] = d.margin_type;
					item_list[0]["margin_rate_or_amount"] = d.margin_rate_or_amount;
				}
			}
		};

		if (item) {
			append_item(item);
		} else {
			$.each(this.frm.doc["items"] || [], function(i, d) {
				append_item(d);
			});
		}
		return item_list;
	},

	_set_values_for_item_list: function(children) {
		var me = this;
		var price_list_rate_changed = false;
		for(var i=0, l=children.length; i<l; i++) {
			var d = children[i];
			var existing_pricing_rule = frappe.model.get_value(d.doctype, d.name, "pricing_rule");
			for(var k in d) {
				var v = d[k];
				if (["doctype", "name"].indexOf(k)===-1) {
					if(k=="price_list_rate") {
						if(flt(v) != flt(d.price_list_rate)) price_list_rate_changed = true;
					}
					frappe.model.set_value(d.doctype, d.name, k, v);
				}
			}

			// if pricing rule set as blank from an existing value, apply price_list
			if(!me.frm.doc.ignore_pricing_rule && existing_pricing_rule && !d.pricing_rule) {
				me.apply_price_list(frappe.get_doc(d.doctype, d.name));
			}
		}

		if(!price_list_rate_changed) me.calculate_taxes_and_totals();
	},

	apply_price_list: function(item, reset_plc_conversion) {
		// We need to reset plc_conversion_rate sometimes because the call to
		// `erpnext.stock.get_item_details.apply_price_list` is sensitive to its value
		if (!reset_plc_conversion) {
			this.frm.set_value("plc_conversion_rate", "");
		}

		var me = this;
		var args = this._get_args(item);
		if (!((args.items && args.items.length) || args.price_list)) {
			return;
		}

		if (me.in_apply_price_list == true) return;

		me.in_apply_price_list = true;
		return this.frm.call({
			method: "erpnext.stock.get_item_details.apply_price_list",
			args: {	args: args },
			callback: function(r) {
				if (!r.exc) {
					frappe.run_serially([
						() => me.frm.set_value("price_list_currency", r.message.parent.price_list_currency),
						() => me.frm.set_value("plc_conversion_rate", r.message.parent.plc_conversion_rate),
						() => {
							if(args.items.length) {
								me._set_values_for_item_list(r.message.children);
							}
						},
						() => { me.in_apply_price_list = false; }
					]);

				} else {
					me.in_apply_price_list = false;
				}
			}
		}).always(() => {
			me.in_apply_price_list = false;
		});
	},

	validate_company_and_party: function() {
		var me = this;
		var valid = true;

		$.each(["company", "customer"], function(i, fieldname) {
			if(frappe.meta.has_field(me.frm.doc.doctype, fieldname) && me.frm.doc.doctype != "Purchase Order") {
				if (!me.frm.doc[fieldname]) {
					frappe.msgprint(__("Please specify") + ": " +
						frappe.meta.get_label(me.frm.doc.doctype, fieldname, me.frm.doc.name) +
						". " + __("It is needed to fetch Item Details."));
					valid = false;
				}
			}
		});
		return valid;
	},

	get_terms: function() {
		var me = this;

		erpnext.utils.get_terms(this.frm.doc.tc_name, this.frm.doc, function(r) {
			if(!r.exc) {
				me.frm.set_value("terms", r.message);
			}
		});
	},

	taxes_and_charges: function() {
		var me = this;
		if(this.frm.doc.taxes_and_charges) {
			return this.frm.call({
				method: "erpnext.controllers.accounts_controller.get_taxes_and_charges",
				args: {
					"master_doctype": frappe.meta.get_docfield(this.frm.doc.doctype, "taxes_and_charges",
						this.frm.doc.name).options,
					"master_name": this.frm.doc.taxes_and_charges,
				},
				callback: function(r) {
					if(!r.exc) {
						if(me.frm.doc.shipping_rule && me.frm.doc.taxes) {
							for (let tax of r.message) {
								me.frm.add_child("taxes", tax);
							}

							refresh_field("taxes");
						} else {
							me.frm.set_value("taxes", r.message);
							me.calculate_taxes_and_totals();
						}
					}
				}
			});
		}
		else{
			me.frm.set_value("taxes", []);
			me.calculate_taxes_and_totals();
		}
	},

	is_recurring: function() {
		// set default values for recurring documents
		if(this.frm.doc.is_recurring && this.frm.doc.__islocal) {
			frappe.msgprint(__("Please set recurring after saving"));
			this.frm.set_value('is_recurring', 0);
			return;
		}

		if(this.frm.doc.is_recurring) {
			if(!this.frm.doc.recurring_id) {
				this.frm.set_value('recurring_id', this.frm.doc.name);
			}

			var owner_email = this.frm.doc.owner=="Administrator"
				? frappe.user_info("Administrator").email
				: this.frm.doc.owner;

			this.frm.doc.notification_email_address = $.map([cstr(owner_email),
				cstr(this.frm.doc.contact_email)], function(v) { return v || null; }).join(", ");
			this.frm.doc.repeat_on_day_of_month = frappe.datetime.str_to_obj(this.frm.doc.posting_date).getDate();
		}

		refresh_many(["notification_email_address", "repeat_on_day_of_month"]);
	},

	from_date: function() {
		// set to_date
		if(this.frm.doc.from_date) {
			var recurring_type_map = {'Monthly': 1, 'Quarterly': 3, 'Half-yearly': 6,
				'Yearly': 12};

			var months = recurring_type_map[this.frm.doc.recurring_type];
			if(months) {
				var to_date = frappe.datetime.add_months(this.frm.doc.from_date,
					months);
				this.frm.doc.to_date = frappe.datetime.add_days(to_date, -1);
				refresh_field('to_date');
			}
		}
	},

	set_gross_profit: function(item) {
		if (this.frm.doc.doctype == "Sales Order" && item.valuation_rate) {
			var rate = flt(item.rate) * flt(this.frm.doc.conversion_rate || 1);
			item.gross_profit = flt(((rate - item.valuation_rate) * item.stock_qty), precision("amount", item));
		}
	},

	setup_item_selector: function() {
		// TODO: remove item selector

		return;
		// if(!this.item_selector) {
		// 	this.item_selector = new erpnext.ItemSelector({frm: this.frm});
		// }
	},

	get_advances: function() {
		if(!this.frm.is_return) {
			return this.frm.call({
				method: "set_advances",
				doc: this.frm.doc,
				callback: function(r, rt) {
					refresh_field("advances");
				}
			})
		}
	},

	make_payment_entry: function() {
		return frappe.call({
			method: cur_frm.cscript.get_method_for_payment(),
			args: {
				"dt": cur_frm.doc.doctype,
				"dn": cur_frm.doc.name
			},
			callback: function(r) {
				var doclist = frappe.model.sync(r.message);
				frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				// cur_frm.refresh_fields()
			}
		});
	},

	get_method_for_payment: function(){
		var method = "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry";
		if(cur_frm.doc.__onload && cur_frm.doc.__onload.make_payment_via_journal_entry){
			if(in_list(['Sales Invoice', 'Purchase Invoice'],  cur_frm.doc.doctype)){
				method = "erpnext.accounts.doctype.journal_entry.journal_entry.get_payment_entry_against_invoice";
			}else {
				method= "erpnext.accounts.doctype.journal_entry.journal_entry.get_payment_entry_against_order";
			}
		}

		return method
	},


	set_query_for_batch: function(doc, cdt, cdn) {
		// Show item's batches in the dropdown of batch no

		var me = this;
		var item = frappe.get_doc(cdt, cdn);

		if(!item.item_code) {
			frappe.throw(__("Please enter Item Code to get batch no"));
		} else if (doc.doctype == "Purchase Receipt" ||
			(doc.doctype == "Purchase Invoice" && doc.update_stock)) {

			return {
				filters: {'item': item.item_code}
			}
		} else {
			let filters = {
				'item_code': item.item_code,
				'posting_date': me.frm.doc.posting_date || frappe.datetime.nowdate(),
			}
			if (item.warehouse) filters["warehouse"] = item.warehouse;

			return {
				query : "erpnext.controllers.queries.get_batch_no",
				filters: filters
			}
		}
	},

	payment_terms_template: function() {
		var me = this;
		const doc = this.frm.doc;
		if(doc.payment_terms_template && doc.doctype !== 'Delivery Note') {
			var posting_date = doc.posting_date || doc.transaction_date;
			frappe.call({
				method: "erpnext.controllers.accounts_controller.get_payment_terms",
				args: {
					terms_template: doc.payment_terms_template,
					posting_date: posting_date,
					grand_total: doc.rounded_total || doc.grand_total,
					bill_date: doc.bill_date
				},
				callback: function(r) {
					if(r.message && !r.exc) {
						me.frm.set_value("payment_schedule", r.message);
					}
				}
			})
		}
	},

	payment_term: function(doc, cdt, cdn) {
		var row = locals[cdt][cdn];
		if(row.payment_term) {
			frappe.call({
				method: "erpnext.controllers.accounts_controller.get_payment_term_details",
				args: {
					term: row.payment_term,
					bill_date: this.frm.doc.bill_date,
					posting_date: this.frm.doc.posting_date || this.frm.doc.transaction_date,
					grand_total: this.frm.doc.rounded_total || this.frm.doc.grand_total
				},
				callback: function(r) {
					if(r.message && !r.exc) {
						for (var d in r.message) {
							frappe.model.set_value(cdt, cdn, d, r.message[d]);
						}
					}
				}
			})
		}
	},
	
	weight_per_unit: function(doc, cdt, cdn) {
		var row = locals[cdt][cdn];
		if(row.weight_per_unit != 0)
		{
			row.total_weight = flt(row.stock_qty * row.weight_per_unit);
			refresh_field("total_weight", row.name, row.parentfield);
		}
		if(row.weight_per_unit != 0 && row.weight_uom)
		{
			
			this.calculate_net_weight();
			
		}
	},
	
	weight_uom:function(doc, cdt, cdn) {
		var row = locals[cdt][cdn];
		if(row.weight_per_unit != 0 && row.weight_uom)
		{
			this.calculate_net_weight();
			
		}
				
	},
	net_weight_uom:function() {
		if(this.frm.doc.net_weight_uom != null && is_weight_unit(this.frm.doc.net_weight_uom))
		{
			this.calculate_net_weight();
			
		}
		else
		{
			frappe.msgprint(__("The net weight uom required is invalid."));
			return;
		}
	},
	get_items_from:function (frm) {
		var me=this;
		
		var doc_options = ['Delivery Note','Purchase Order','Purchase Receipt','Product Collection','Sales Order',
		'Sales Invoice','Quotation'];
		
		var dialog = new frappe.ui.Dialog({
			title: __("Get Items From Document"),
			fields: [
				{fieldname:'clear_items', fieldtype:'Check', label: __('Clear Previous Items')},
				{fieldname:'sec_1', fieldtype:'Section Break'},
				{fieldname:'doc_type', fieldtype:'Select', options: doc_options, label: __('Type')},
				{fieldname:'col_1', fieldtype:'Column Break'},
				{fieldname:'doc_name', fieldtype:'Dynamic Link', options: 'doc_type', label: __('Name')},
				// {fieldname:'qty', fieldtype:'float', label: __('Quantity'),default:1},
			]
		});
		
		
		dialog.fields_dict["doc_name"].get_query = function(){
			return {
				filters: [
						['docstatus', '<', '2'],
						// ['status', '!=', 'Closed'],
						// ['company', '=', frm.doc.company],
					]
					
				
			};
		};
		
		dialog.set_primary_action(__("Get Items"), function() {
		
		var filters = dialog.get_values();

		frappe.call({
			method:'erpnext.controllers.queries.get_items_from',
			args:{
				doc_type: filters.doc_type,
				doc_name: filters.doc_name
			},
			// freeze: true,
			// freeze_message: __("Getting Items..."),
			callback:function (r) {
			

				if(filters.clear_items === 1)
					cur_frm.set_value("items",[]);
				
				var row_info = {};
				var row_count = cur_frm.doc.items.length;
				
				
				for (var i=0; i< r.message.length; i++) {
					var row = frappe.model.add_child(cur_frm.doc, cur_frm.fields_dict.items.df.options, cur_frm.fields_dict.items.df.fieldname);
					row.item_code = r.message[i].item_code
					
					
					cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
					var row_index = row_count + i;
					row_info[row_index] = r.message[i];
					
					/* for (var key in r.message[i]) {
						var has_margin_field = frappe.meta.has_field(row.doctype, key);
						if(has_margin_field)
						{
							row[key] = r.message[i][key];
						}
					
					} */
				}
				
				dialog.hide();
				frappe.show_progress(__("Getting Items.."),0);

				//code before the pause
				setTimeout(function(){
					for(var row_index in row_info)
					{
						var row = cur_frm.doc.items[row_index];
						var data = row_info[row_index];

						for (var key in data) {
							var has_margin_field = frappe.meta.has_field(row.doctype, key);
							if(has_margin_field)
							{
								row[key] = data[key];
							}
					
						}
						
					}
					
					cur_frm.refresh_field('items');
					me.calculate_taxes_and_totals();
					cur_frm.dirty();
					frappe.show_progress(__("Getting Items.."),100);

				}, 1000);

				
				
				
			}
		})
		});
		dialog.show();
	},
	
	
	multiply_room:function (frm) {
		var me=this;
		var dialog = new frappe.ui.Dialog({
			title: __("Multiply Room"),
			fields: [
				// {fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				// {fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'qty', fieldtype:'Int', label: __('Quantity'),default:'1'},
			]
		});
		dialog.set_primary_action(__("Change"), function() {
		
			var filters = dialog.get_values();

			var qty =1;
			var filter_qty = 1;
			if ( dialog.get_value('qty') > 0)
				filter_qty = dialog.get_value('qty');
			
			original_qty = cur_frm.doc.room_qty;
			qty = flt(filter_qty)/flt(original_qty);
			cur_frm.set_value("room_qty",filter_qty);
			
			var items = cur_frm.doc.items;
			$.each(items, function(i, item) {
				item.qty = flt(item.qty) * flt(qty);
				cur_frm.script_manager.trigger("item_qty", item.doctype, item.name);

			});
			cur_frm.refresh_field('items');
					me.calculate_taxes_and_totals();
			cur_frm.dirty();
			dialog.hide();
		});
		dialog.show();
	},
	
	multiply_items:function (frm) {
		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("Multiply All Items"),
			fields: [
				//{fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				//{fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'qty', fieldtype:'Float', label: __('Quantity'),default:'1'},
			]
		});
		dialog.set_primary_action(__("Multiply"), function() {
		
			var filters = dialog.get_values();
			var qty =1;
			var filter_qty = 1;
			if ( dialog.get_value('qty') > 0)
				filter_qty = dialog.get_value('qty');
			
			original_qty = cur_frm.doc.room_qty;
			qty = filter_qty;

			//cur_frm.set_value("room_qty",qty);
			
			var items = cur_frm.doc.items;

			$.each(items, function(i, item) {
				item.qty = flt(item.qty) * flt(qty);
				cur_frm.script_manager.trigger("item_code", item.doctype, item.name);

			});
			
			cur_frm.refresh_field('items');
					me.calculate_taxes_and_totals();
			cur_frm.dirty();
			dialog.hide();
		});
		dialog.show();
	},
	
	multiply_rate:function (frm) {
		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("Multiply All Item Rate"),
			fields: [
				//{fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				//{fieldname:'base_variable', fieldtype:'Section Break'},
				{fieldname:'qty', fieldtype:'Float', label: __('Percent'),default:'100'},
			]
		});
		dialog.set_primary_action(__("Multiply"), function() {
		
			var filters = dialog.get_values();
			var percent = 100;
			if ( dialog.get_value('qty') > 0)
				percent = dialog.get_value('qty');
			
			
			var items = cur_frm.doc.items;

			$.each(items, function(i, item) {
				item.rate = flt(item.rate) * flt(percent)/100;
				//cur_frm.script_manager.trigger("item_code", item.doctype, item.name);

			});
			
			cur_frm.refresh_field('items');
			me.calculate_taxes_and_totals();
			cur_frm.dirty();

			dialog.hide();
		});
		dialog.show();
	},

	pro_rata:function (frm) {
		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("Pro Rata Item Rate"),
			fields: [
				//{fieldname:'bundle', fieldtype:'Link', options: 'Product Collection', label: __('Collection')},
				// {fieldname:'branch', fieldtype:'Link', options: 'Branch', label: __('Branch')},
				{fieldname:'target', fieldtype:'Float', label: __('Total Required'),default:me.frm.doc.grand_total},
				//{fieldname:'base_variable', fieldtype:'Section Break'},
				//{fieldname:'qty', fieldtype:'Float', label: __('Percent'),default:'100'},
			]
		});
		dialog.set_primary_action(__("Bata"), function() {
		
			var filters = dialog.get_values();
			
			var target = original_total = me.frm.doc.grand_total;
			if ( dialog.get_value('target') > 0)
				target = dialog.get_value('target');
			
			var percent_change = (target-original_total)/original_total
			
			var items = cur_frm.doc.items;
			$.each(items, function(i, item) {
				var new_amount = item.amount*(1+percent_change);
				item.rate = flt(new_amount/item.qty);
			});
			
			cur_frm.refresh_field('items');
			me.calculate_taxes_and_totals();
			cur_frm.dirty();

			dialog.hide();
		});
		dialog.show();
	},
	
	blanket_order: function(doc, cdt, cdn) {
		var me = this;
		var item = locals[cdt][cdn];
		if (item.blanket_order && (item.parenttype=="Sales Order" || item.parenttype=="Purchase Order")) {
			frappe.call({
				method: "erpnext.stock.get_item_details.get_blanket_order_details",
				args: {
					args:{
						item_code: item.item_code,
						customer: doc.customer,
						supplier: doc.supplier,
						company: doc.company,
						transaction_date: doc.transaction_date,
						blanket_order: item.blanket_order
					}
				},
				callback: function(r) {
					if (!r.message) {
						frappe.throw(__("Invalid Blanket Order for the selected Customer and Item"));
					} else {
						frappe.run_serially([
							() => frappe.model.set_value(cdt, cdn, "blanket_order_rate", r.message.blanket_order_rate),
							() => me.frm.script_manager.trigger("price_list_rate", cdt, cdn)
						]);
					}
				}
			})
		}
	},

	set_warehouse: function() {
		var me = this;
		if(this.frm.doc.set_warehouse) {
			$.each(this.frm.doc.items || [], function(i, item) {
				frappe.model.set_value(me.frm.doctype + " Item", item.name, "warehouse", me.frm.doc.set_warehouse);
			});
		}
	}
});

erpnext.show_serial_batch_selector = function(frm, d, callback, on_close, show_dialog) {
	frappe.require("assets/erpnext/js/utils/serial_no_batch_selector.js", function() {
		new erpnext.SerialNoBatchSelector({
			frm: frm,
			item: d,
			warehouse_details: {
				type: "Warehouse",
				name: d.warehouse
			},
			callback: callback,
			on_close: on_close
		}, show_dialog);
	});
}


	
var is_weight_unit =  function(UOM)
{
	var weight_array = ['kg','g','tonne']
	return (weight_array.indexOf(UOM.toLowerCase()) != -1);
}
	
var convert_weight_unit = function(in_value, in_uom, out_uom)
{
	var base_value = 0;
	var out_value = 0;
	if (in_value != null && in_uom != null && out_uom != null)
	{
		
		if(is_weight_unit(in_uom) && is_weight_unit(out_uom))
		{
			base_value = convert_weight_to_base(in_uom,in_value)
			out_value = convert_weight_from_base(out_uom,base_value)
			return [true,out_value];
		}
		
		return [false,out_value];
		
	}
	
	return [false,out_value];
	
}

var convert_weight_to_base = function(unit,value) {
	var finalvalue = 0;
	if (unit == "g")
		finalvalue = flt(value) * flt(0.001);
	else if (unit == "tonne")
		finalvalue = flt(value) * flt(1000);
	else
		finalvalue = flt(value);
	return finalvalue;
}

var convert_weight_from_base = function(unit,value) {
	var finalvalue = 0;
	if (unit == "g")
		finalvalue = flt(value) / flt(0.001);
	else if (unit == "tonne")
		finalvalue = flt(value) / flt(1000);
	else
		finalvalue = flt(value);
	return finalvalue;
}
