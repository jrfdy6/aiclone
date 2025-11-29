"""
Validators for prospect discovery
"""
from typing import List


def is_valid_person_name(name: str) -> bool:
    """
    Check if name looks like a real person name.
    Used during extraction to filter garbage names.
    
    Args:
        name: Name string to validate
        
    Returns:
        True if name appears to be a valid person name
    """
    if not name or not isinstance(name, str):
        return False
    
    name_lower = name.lower().strip()
    words = name.split()
    
    # Must be exactly 2-3 words
    if len(words) < 2 or len(words) > 3:
        return False
    
    # Bad name words that indicate it's not a real person name
    bad_name_words = [
        "inc", "llc", "ltd", "corp", "company", "services", "group",
        "team", "staff", "department", "division", "office", "center",
        "school", "academy", "institute", "university", "college",
        "hospital", "clinic", "practice", "associates", "partners",
        "administrator", "admin", "contact", "info", "support",
        "noreply", "no-reply", "hello", "sales", "marketing",
        "example", "test", "demo", "sample", "null", "none",
        "home", "about", "page", "main", "index", "directory",
        "list", "search", "results", "view", "more", "all",
        "click", "here", "read", "more", "learn", "see",
    ]
    
    # Check if any word matches bad name words
    for word in words:
        if word.lower().strip() in bad_name_words:
            return False
    
    # Each word should start with capital letter (for proper names)
    # Allow for some flexibility (middle initials, prefixes like "Dr.")
    valid_word_count = 0
    for word in words:
        word_clean = word.strip().rstrip(".,;:!?")
        if not word_clean:
            continue
        
        # Skip common prefixes/suffixes
        if word_clean.lower() in ["dr", "mr", "mrs", "ms", "jr", "sr", "ii", "iii", "iv"]:
            continue
        
        # Word should start with capital letter
        if word_clean[0].isupper() or word_clean.isupper():
            valid_word_count += 1
    
    # At least 2 words should be valid (allowing for prefixes/suffixes)
    if valid_word_count < 2:
        return False
    
    # Check minimum length - each word should be at least 2 characters
    for word in words:
        word_clean = word.strip().rstrip(".,;:!?")
        if len(word_clean) < 2:
            return False
    
    # Name shouldn't be all the same character
    name_chars = set(name_lower.replace(" ", ""))
    if len(name_chars) <= 1:
        return False
    
    return True


def is_valid_email(email: str) -> bool:
    """
    Basic email validation.
    
    Args:
        email: Email string to validate
        
    Returns:
        True if email appears valid
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip().lower()
    
    # Basic format check
    if "@" not in email or "." not in email.split("@")[1]:
        return False
    
    # Check for common invalid patterns
    invalid_patterns = [
        "example.com",
        "test.com",
        "noreply",
        "no-reply",
        "test@",
        "example@",
        "@example",
    ]
    
    for pattern in invalid_patterns:
        if pattern in email:
            return False
    
    return True


def is_valid_phone(phone: str) -> bool:
    """
    Basic phone number validation.
    
    Args:
        phone: Phone string to validate
        
    Returns:
        True if phone appears valid
    """
    if not phone or not isinstance(phone, str):
        return False
    
    # Remove common formatting characters
    digits_only = "".join(filter(str.isdigit, phone))
    
    # US phone numbers should have 10 digits (with or without country code)
    if len(digits_only) == 10 or len(digits_only) == 11:
        return True
    
    return False

