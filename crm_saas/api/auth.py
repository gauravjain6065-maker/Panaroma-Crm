import frappe
from crm_saas.api.signup import request_trial

@frappe.whitelist(allow_guest=True)
def signup(company_name=None, email=None, password=None, plan="Trial", slug=None, companyName=None, **kwargs):
    """
    Wrapper endpoint for signup that routes to request_trial.
    """
    return request_trial(
        company_name=company_name or companyName,
        email=email,
        plan=plan,
        slug=slug,
        password=password,
        **kwargs
    )