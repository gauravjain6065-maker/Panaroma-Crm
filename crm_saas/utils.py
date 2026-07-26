def get_domain(email):
    if not email or "@" not in email:
        return None
    return email.split("@")[-1].lower()