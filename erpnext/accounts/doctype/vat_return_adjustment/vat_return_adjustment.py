# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document

class VATReturnAdjustment(Document):
	def validate(self):
		self.validate_doc()

	def validate_doc(self):
		
		
		if self.get("__islocal"):
			docs = frappe.db.sql(
				"""select name from `tabVAT Return Adjustment` where document_type = %s and document = %s""",
				(self.document_type, self.document),as_dict = 1
			)
			
			if len(docs)>0:
		
				frappe.throw(
					_("An adjustment entry for this document and document type already exists: {0}").format(
						docs[0].name
					)
				)
				
		else:
			docs = frappe.db.sql(
				"""select name from `tabVAT Return Adjustment` where document_type = %s and document = %s and name !- %s""",
				(self.document_type, self.document,self.name),as_dict = 1
			)
			
			if len(docs)>0:
			
				frappe.throw(
					_("An adjustment entry for this document and document type already exists: {0}").format(
						docs[0].name
					)
				)
			

