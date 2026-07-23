import re
import phonenumbers

def normalize_email(email: str) -> str:
    if not email:
        return email
    return email.strip().lower()

def normalize_phone(phone: str, default_region: str = "IN") -> str:
    if not phone:
        return phone
    try:
        parsed = phonenumbers.parse(phone, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except phonenumbers.NumberParseException:
        pass
    return re.sub(r"[^\d+]", "", phone)