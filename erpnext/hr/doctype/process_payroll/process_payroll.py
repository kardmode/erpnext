# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import add_days, cint, cstr, flt, getdate,get_datetime, nowdate, rounded, date_diff
from frappe import _

from frappe.model.document import Document

class ProcessPayroll(Document):
			
	
	def calculate_lwp(self, e, m):
		lwp = 0

		for d in range(m['month_days']):
		
			dt = add_days(cstr(m['month_start_date']), d)

			leave = frappe.db.sql("""
				select t1.name, t1.half_day, t1.leave_type
				from `tabLeave Application` t1, `tabLeave Type` t2
				where t2.name = t1.leave_type
				and t2.is_lwp = 1
				and t1.docstatus < 2
				and t1.status = 'Approved'
				and t1.employee = %s
				and %s between from_date and to_date
			""", (e, dt))
			if leave:
				if leave.leave_type == "Vacation Leave":
					lwp = cint(leave[0][1]) and (lwp + 0.5) or (lwp + 1)
	
		return lwp
	
	def get_emp_list(self):
		"""
			Returns list of active employees based on selected criteria
			and for which salary structure exists
		"""

		cond = self.get_filter_condition()
		cond += self.get_joining_releiving_condition()

		emp_list = frappe.db.sql("""
			select t1.name
			from `tabEmployee` t1, `tabSalary Structure` t2
			where t1.docstatus!=2 and t1.status !='Left' and t2.docstatus != 2
			and t2.is_active = 'Yes' and t1.name = t2.employee
		%s """% cond)
		
		m = get_month_details(self.fiscal_year, self.month)
		
		if not self.fiscal_year:
			self.fiscal_year = frappe.db.get_default("fiscal_year")
		if not self.month:
			self.month = "%02d" % getdate(nowdate()).month
		
		new_emp_list = ()
		for e in emp_list:

			joining_date, relieving_date = frappe.db.get_value("Employee", e[0], 
				["date_of_joining", "relieving_date"])
		
			lwp = self.calculate_lwp(e,m)
			payment_days = flt(self.get_payment_days(m, joining_date, relieving_date))-flt(lwp)
			if payment_days > 0:
				new_emp_list = new_emp_list + (e,)



		return new_emp_list

				
	def get_payment_days(self, month, joining_date, relieving_date):
		start_date = month['month_start_date']
		if joining_date:
			if joining_date > month['month_start_date']:
				start_date = joining_date
			elif joining_date > month['month_end_date']:
				return
				
		end_date = month['month_end_date']
		if relieving_date:
			if relieving_date > start_date and relieving_date < month['month_end_date']:
				end_date = relieving_date
			elif relieving_date < month['month_start_date']:
				frappe.throw(_("Employee relieved on {0} must be set as 'Left'")
					.format(relieving_date))			
			
		payment_days = date_diff(end_date, start_date) + 1
			
		return payment_days

	def get_filter_condition(self):
		self.check_mandatory()

		cond = ''
		for f in ['company', 'branch', 'department', 'designation']:
			if self.get(f):
				cond += " and t1." + f + " = '" + self.get(f).replace("'", "\'") + "'"

		return cond


	def get_joining_releiving_condition(self):
		m = get_month_details(self.fiscal_year, self.month)
		cond = """
			and ifnull(t1.date_of_joining, '0000-00-00') <= '%(month_end_date)s'
			and ifnull(t1.relieving_date, '2199-12-31') >= '%(month_start_date)s'
		""" % m
		return cond


	def check_mandatory(self):
		for f in ['company', 'month', 'fiscal_year']:
			if not self.get(f):
				frappe.throw(_("Please set {0}").format(f))

	def create_sal_slip(self):
		"""
			Creates salary slip for selected employees if already not created
		"""

		emp_list = self.get_emp_list()
		ss_list = []
		for emp in emp_list:
			if not frappe.db.sql("""select name from `tabSalary Slip`
					where docstatus < 2 and employee = %s and month = %s and fiscal_year = %s and company = %s
					""", (emp[0], self.month, self.fiscal_year, self.company)):
				ss = frappe.get_doc({
					"doctype": "Salary Slip",
					"fiscal_year": self.fiscal_year,
					"employee": emp[0],
					"month": self.month,
					"email_check": self.send_email,
					"company": self.company,
				})
				ss.insert()
				ss_list.append(ss.name)

		return self.create_log(ss_list)


	def create_log(self, ss_list):
		log = "<p>" + _("No employee for the above selected criteria OR salary slip already created") + "</p>"
		if ss_list:
			log = "<b>" + _("Salary Slip Created") + "</b>\
			<br><br>%s" % '<br>'.join(self.format_as_links(ss_list))
		return log


	def get_sal_slip_list(self):
		"""
			Returns list of salary slips based on selected criteria
			which are not submitted
		"""
		cond = self.get_filter_condition()
		ss_list = frappe.db.sql("""
			select t1.name from `tabSalary Slip` t1
			where month = %s and fiscal_year = %s %s
		""" % ('%s', '%s', cond), (self.month, self.fiscal_year))
		return ss_list


	def submit_salary_slip(self):
		"""
			Submit all salary slips based on selected criteria
		"""
		ss_list = self.get_sal_slip_list()
		not_submitted_ss = []
		for ss in ss_list:
			ss_obj = frappe.get_doc("Salary Slip",ss[0])
			try:
				ss_obj.email_check = self.send_email
				ss_obj.submit()
			except Exception,e:
				not_submitted_ss.append(ss[0])
				frappe.msgprint(e)
				continue

		return self.create_submit_log(ss_list, not_submitted_ss)
	
	def print_salary_slips(self):
		"""
			Print all salary slips based on selected criteria
		"""
		ss_list = self.get_sal_slip_list()

		return ss_list

	def create_submit_log(self, all_ss, not_submitted_ss):
		log = ''
		if not all_ss:
			log = "No salary slip found to submit for the above selected criteria"
		else:
			all_ss = [d[0] for d in all_ss]

		submitted_ss = self.format_as_links(list(set(all_ss) - set(not_submitted_ss)))
		if submitted_ss:
			mail_sent_msg = self.send_email and " (Mail has been sent to the employee)" or ""
			log = """
			<b>Salary Slips Submitted %s:</b>\
			<br><br> %s <br><br>
			""" % (mail_sent_msg, '<br>'.join(submitted_ss))

		if not_submitted_ss:
			log += """
				<b>Not Submitted Salary Slips: </b>\
				<br><br> %s <br><br> \
				Reason: <br>\
				May be company email id specified in employee master is not valid. <br> \
				Please mention correct email id in employee master or if you don't want to \
				send mail, uncheck 'Send Email' checkbox. <br>\
				Then try to submit Salary Slip again.
			"""% ('<br>'.join(not_submitted_ss))
		return log

	def format_as_links(self, ss_list):
		return ['<a href="#Form/Salary Slip/{0}">{0}</a>'.format(s) for s in ss_list]


	def get_total_salary(self):
		"""
			Get total salary amount from submitted salary slip based on selected criteria
		"""
		cond = self.get_filter_condition()
		tot = frappe.db.sql("""
			select sum(rounded_total) from `tabSalary Slip` t1
			where t1.docstatus < 2 and month = %s and fiscal_year = %s %s
		""" % ('%s', '%s', cond), (self.month, self.fiscal_year))

		return flt(tot[0][0])


	def make_journal_entry(self, salary_account = None):
		amount = self.get_total_salary()
		default_bank_account = frappe.db.get_value("Company", self.company,
			"default_bank_account")

		journal_entry = frappe.new_doc('Journal Entry')
		journal_entry.voucher_type = 'Bank Entry'
		journal_entry.user_remark = _('Payment of salary for the month {0} and year {1}').format(self.month,
			self.fiscal_year)
		journal_entry.fiscal_year = self.fiscal_year
		journal_entry.company = self.company
		journal_entry.posting_date = nowdate()
		journal_entry.set("accounts", [
			{
				"account": salary_account,
				"debit_in_account_currency": amount
			},
			{
				"account": default_bank_account,
				"credit_in_account_currency": amount
			},
		])

		return journal_entry.as_dict()


def get_month_details(year, month):
	ysd = frappe.db.get_value("Fiscal Year", year, "year_start_date")
	if ysd:
		from dateutil.relativedelta import relativedelta
		import calendar, datetime
		diff_mnt = cint(month)-cint(ysd.month)
		if diff_mnt<0:
			diff_mnt = 12-int(ysd.month)+cint(month)
		msd = ysd + relativedelta(months=diff_mnt) # month start date
		month_days = cint(calendar.monthrange(cint(msd.year) ,cint(month))[1]) # days in month
		med = datetime.date(msd.year, cint(month), month_days) # month end date
		return frappe._dict({
			'year': msd.year,
			'month_start_date': msd,
			'month_end_date': med,
			'month_days': month_days
		})
