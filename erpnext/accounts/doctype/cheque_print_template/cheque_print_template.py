# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt

class ChequePrintTemplate(Document):
	pass

@frappe.whitelist()
def get_total_in_words(amount,show_main_currency,line_one_max = 63):
	from frappe.utils import money_in_words,fmt_money
	
	if show_main_currency == 1:
		show_currency = True
	else:
		show_currency = False
	
	amount_in_words = money_in_words(float(amount),main_currency = "AED",fraction_currency="fils",show_main_currency = show_currency)
	amount_in_words = str(amount_in_words).strip()
	
	import textwrap
	lines = textwrap.wrap(amount_in_words, width=line_one_max)
	
	first_line = ""
	second_line =""
	if len(lines) > 0:
		first_line = lines[0]
		if len(lines) > 1:
			second_line_list = lines.pop(0)
			second_line = " ".join(lines)
	
	frappe.errprint(first_line)
	frappe.errprint(second_line)
	
	fmt_amount = fmt_money(amount)
	return fmt_amount,amount_in_words,first_line,second_line

@frappe.whitelist()
def create_or_update_cheque_print_format(template_name):
	if not frappe.db.exists("Print Format", template_name):
		cheque_print = frappe.new_doc("Print Format")
		cheque_print.update({
			"doc_type": "Payment Entry",
			"standard": "No",
			"custom_format": 1,
			"print_format_type": "Server",
			"name": template_name
		})
	else:
		cheque_print = frappe.get_doc("Print Format", template_name)
	
	doc = frappe.get_doc("Cheque Print Template", template_name)
	
	signatory = "{{ doc.company }}" if doc.show_signatory else ''
	account_no = "{{ doc.account_no or '' }}" if doc.show_account_no else ''
	symbol = doc.symbol_to_add or ''
	bearer_symbol = doc.bearer_symbol or ''
	
	cheque_print.html = """<div id="variables" style="display: none;"><span id="margin-bottom">0</span><span id="margin-top">%(starting_position_from_top_edge)smm</span>
<span id="margin-left">%(starting_position_from_left_edge)smm</span><span id="margin-right">0</span>
<span id="orientation">Landscape</span>
</div>
<div style="position: relative; top:0; font-family:Arial !important;">
	<div style="width:%(cheque_width)scm;height:%(cheque_height)scm;
	font-size:%(font_size)spx !important;font-weight:%(font_weight)s;">
		<span style="top: %(acc_pay_dist_from_top_edge)scm; left:%(acc_pay_dist_from_left_edge)scm;
			border-bottom: solid 1px;border-top:solid 1px; position: absolute;">
				%(message_to_show)s
		</span>
		<span style="top:%(date_dist_from_top_edge)scm; left:%(date_dist_from_left_edge)scm;
			position: absolute;">
			{{ frappe.utils.formatdate(doc.reference_date) or '' }}
		</span>
		<span style="top:%(acc_no_dist_from_top_edge)scm;left:%(acc_no_dist_from_left_edge)scm;
			position: absolute;">
			%(account_no)s
		</span>
		<span style="top:%(payer_name_from_top_edge)scm;left: %(payer_name_from_left_edge)scm;
			position: absolute;">
			%(symbol)s{{doc.party_name}}%(symbol)s
		</span>
		<span style="top:%(bearer_dist_from_top_edge)scm; left:%(bearer_dist_from_left_edge)scm;
			position: absolute;">
			%(bearer_symbol)s
		</span>
		<span style="top:%(amt_in_words_from_top_edge)scm; left:%(amt_in_words_from_left_edge)scm;
			position: absolute; display: block; width: %(amt_in_word_width)scm;
			line-height:%(amt_in_words_line_spacing)scm; word-wrap: break-word;text-indent:%(amt_in_words_indent)scm;">
				%(symbol)s{{frappe.utils.money_in_words(doc.base_paid_amount or doc.base_received_amount,show_main_currency = %(show_main_currency)s)}}%(symbol)s
		</span>
		<span style="top:%(amt_in_figures_from_top_edge)scm;left: %(amt_in_figures_from_left_edge)scm;
			position: absolute;">
			%(symbol)s{{doc.get_formatted("base_paid_amount") or doc.get_formatted("base_received_amount")}}%(symbol)s
		</span>
		<span style="top:%(signatory_from_top_edge)scm;left: %(signatory_from_left_edge)scm;
			position: absolute;">
			%(signatory)s
		</span>
	</div>
</div>"""%{
		"starting_position_from_top_edge": (210 - flt(doc.cheque_height)*10)/2\
			if doc.cheque_size == "A4" else 0.0,
		"starting_position_from_left_edge": (297 - flt(doc.cheque_width)*10) \
			if doc.cheque_size == "A4" else 0.0,
		"cheque_width_mm": flt(doc.cheque_width)*10+1, "cheque_height_mm": flt(doc.cheque_height)*10+1,
		"cheque_width": doc.cheque_width, "cheque_height": doc.cheque_height,
		"font_size": doc.font_size, "font_weight": doc.font_weight,
		"acc_pay_dist_from_top_edge": doc.acc_pay_dist_from_top_edge,
		"acc_pay_dist_from_left_edge": doc.acc_pay_dist_from_left_edge,
		"message_to_show": doc.message_to_show if doc.message_to_show else _("A/C PAYEE ONLY"),
		"date_dist_from_top_edge": doc.date_dist_from_top_edge,
		"date_dist_from_left_edge": doc.date_dist_from_left_edge,
		"acc_no_dist_from_top_edge": doc.acc_no_dist_from_top_edge,
		"acc_no_dist_from_left_edge": doc.acc_no_dist_from_left_edge,
		"account_no":account_no,
		"payer_name_from_top_edge": doc.payer_name_from_top_edge,
		"payer_name_from_left_edge": doc.payer_name_from_left_edge,
		"amt_in_words_from_top_edge": doc.amt_in_words_from_top_edge,
		"amt_in_words_from_left_edge": doc.amt_in_words_from_left_edge,
		"amt_in_word_width": doc.amt_in_word_width,
		"amt_in_words_line_spacing": doc.amt_in_words_line_spacing,
		"amt_in_words_indent": doc.amt_in_words_indent,
		"amt_in_figures_from_top_edge": doc.amt_in_figures_from_top_edge,
		"amt_in_figures_from_left_edge": doc.amt_in_figures_from_left_edge,
		"signatory_from_top_edge": doc.signatory_from_top_edge,
		"signatory_from_left_edge": doc.signatory_from_left_edge,
		"signatory":signatory,
		"symbol":symbol,
		"show_main_currency": doc.show_main_currency,
		"bearer_dist_from_top_edge": doc.bearer_dist_from_top_edge,
		"bearer_dist_from_left_edge": doc.bearer_dist_from_left_edge,
		"bearer_symbol":doc.bearer_symbol
	}
		
	cheque_print.save(ignore_permissions=True)
	
	frappe.db.set_value("Cheque Print Template", template_name, "has_print_format", 1)
		
	return cheque_print