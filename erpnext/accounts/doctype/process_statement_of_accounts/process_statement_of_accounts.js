// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Process Statement Of Accounts", {
	view_properties: function (frm) {
		frappe.route_options = { doc_type: "Customer" };
		frappe.set_route("Form", "Customize Form");
	},
	refresh: function (frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__("Send Emails"), function () {
				const customer_count = (frm.doc.customers || []).length;
				let msg = "";
				if (frm.doc.override_email && frm.doc.override_email.trim()) {
					msg = __(
						"<div style='padding: 8px 12px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 4px; color: #92400e; margin-bottom: 10px; font-weight: 600;'>" +
						"&#9888; TEST MODE ACTIVE: Override Recipient is set to <u>{0}</u>.<br>" +
						"Emails will NOT be sent to customers. They will ONLY be sent to this override address." +
						"</div>" +
						"Are you sure you want to proceed and send statements for <b>{1} customer(s)</b>?",
						[frappe.utils.escape_html(frm.doc.override_email.trim()), customer_count]
					);
				} else {
					msg = __(
						"Are you sure you want to queue and dispatch Statement of Accounts emails to <b>{0} customer(s)</b>?<br><br><span class='text-muted small'>All attached statements will be emailed to customer recipient addresses immediately.</span>",
						[customer_count]
					);
				}

				frappe.confirm(
					msg,
					function () {
						frappe.call({
							method: "erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.send_emails",
							args: {
								document_name: frm.doc.name,
							},
							freeze: true,
							freeze_message: __("Queueing statement emails..."),
							callback: function (r) {
								if (r && r.message) {
									frappe.show_alert({ message: __("Emails Queued successfully"), indicator: "green" });
								} else {
									frappe.msgprint(__("No Records found to send for these settings."));
								}
							},
						});
					},
					function () {
						// User cancelled
					}
				);
			});
			frm.add_custom_button(__("Download PDF"), function () {
				var url = frappe.urllib.get_full_url(
					"/api/method/erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.download_statements?" +
					"document_name=" +
					encodeURIComponent(frm.doc.name)
				);
				$.ajax({
					url: url,
					type: "GET",
					success: function (result) {
						if (jQuery.isEmptyObject(result)) {
							frappe.msgprint(__("No Records for these settings."));
						} else {
							window.location = url;
						}
					},
				});
			});
			frm.add_custom_button(__("Export to Excel"), function () {
				var url = frappe.urllib.get_full_url(
					"/api/method/erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.download_excel_statements?" +
					"document_name=" +
					encodeURIComponent(frm.doc.name)
				);
				window.open(url);
			});
		}
	},
	onload: function (frm) {
		frm.set_query("currency", function () {
			return {
				filters: {
					enabled: 1,
				},
			};
		});
		frm.set_query("account", function () {
			return {
				filters: {
					company: frm.doc.company,
				},
			};
		});
		if (frm.doc.__islocal) {
			frm.set_value("from_date", frappe.datetime.add_months(frappe.datetime.get_today(), -1));
			frm.set_value("to_date", frappe.datetime.get_today());
		}
	},
	report: function (frm) {
		let filters = {
			company: frm.doc.company,
		};
		if (frm.doc.report == "Accounts Receivable") {
			filters["account_type"] = "Receivable";
		}
		frm.set_query("account", function () {
			return {
				filters: filters,
			};
		});
	},
	customer_collection: function (frm) {
		frm.set_value("collection_name", "");
		if (frm.doc.customer_collection) {
			frm.get_field("collection_name").set_label(frm.doc.customer_collection);
		}
	},
	frequency: function (frm) {
		if (frm.doc.frequency != "") {
			frm.set_value("start_date", frappe.datetime.get_today());
		} else {
			frm.set_value("start_date", "");
		}
	},
	fetch_customers: function (frm) {
		if (frm.doc.collection_name) {
			frappe.call({
				method: "erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.fetch_customers",
				args: {
					customer_collection: frm.doc.customer_collection,
					collection_name: frm.doc.collection_name,
					primary_mandatory: frm.doc.primary_mandatory,
				},
				callback: function (r) {
					if (!r.exc) {
						if (r.message.length) {
							frm.clear_table("customers");
							for (const customer of r.message) {
								var row = frm.add_child("customers");
								row.customer = customer.name;
								row.primary_email = customer.primary_email;
								row.billing_email = customer.billing_email;
							}
							frm.refresh_field("customers");
						} else {
							frappe.throw(__("No Customers found with selected options."));
						}
					}
				},
			});
		} else {
			frappe.throw("Enter " + frm.doc.customer_collection + " name.");
		}
	},
	body: function (frm) {
		let plain_text = $("<div>").html(frm.doc.body || "").text().trim();
		if (!plain_text) {
			let default_body =
				"<p>To: <b>{{ customer.customer_name }}</b>,</p>" +
				"<p>Please find attached your official <b>Statement of Accounts</b> from <b>{{ doc.company }}</b>" +
				"{% if doc.from_date %} covering the period from <b>{{ doc.from_date }}</b> to <b>{{ doc.to_date }}</b>" +
				"{% else %} as of <b>{{ doc.to_date or doc.posting_date }}</b>{% endif %}.</p>" +
				"<p>Kindly review the statement and contact us should you have any questions or require any clarification.</p>" +
				"<p>Thank you for your business.</p>" +
				"<p>Kind regards,<br><b>{{ doc.company }}</b></p>";
			frm.set_value("body", default_body);
		}
	},
});

frappe.ui.form.on("Process Statement Of Accounts Customer", {
	customer: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (!row.customer) {
			return;
		}
		frappe.call({
			method: "erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.get_customer_emails",
			args: {
				customer_name: row.customer,
				primary_mandatory: frm.doc.primary_mandatory,
			},
			callback: function (r) {
				if (!r.exe) {
					if (r.message.length) {
						frappe.model.set_value(cdt, cdn, "primary_email", r.message[0]);
						frappe.model.set_value(cdt, cdn, "billing_email", r.message[1]);
					} else {
						return;
					}
				}
			},
		});
	},
});
