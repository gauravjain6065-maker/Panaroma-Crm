import frappe
from frappe import _
from crm_saas.utils.helpers import validate_email, validate_slug, normalize_company_name, generate_site_name

@frappe.whitelist(allow_guest=True)
def signup(company_name=None, email=None, password=None, plan="Trial", slug=None, **kwargs):
    # We will write the validation and creation logic here next!
    pass