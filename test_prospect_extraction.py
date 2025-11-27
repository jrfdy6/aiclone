"""
Local test script for prospect extraction - iterate fast without deploying
"""
import re
import requests
from bs4 import BeautifulSoup

# Bad name words filter
BAD_NAME_WORDS = [
    'educational', 'administrative', 'outreach', 'experience', 'engagement',
    'customer', 'patient', 'human', 'service', 'services', 'standardized',
    'test', 'prep', 'head', 'start', 'reviewer', 'board', 'college',
    'resources', 'featured', 'guidance', 'admissions', 'tutoring', 'academic',
    'available', 'advising', 'member', 'independent', 'county', 'montgomery',
    'tedeschi', 'marks', 'education', 'consultant', 'consulting', 'group',
    'center', 'institute', 'foundation', 'association', 'program', 'school',
    'academy', 'learning', 'development', 'training', 'coaching', 'support',
    'help', 'how', 'can', 'you', 'your', 'child', 'contact', 'phone', 'number',
    'email', 'address', 'click', 'here', 'read', 'more', 'learn', 'about',
    'options', 'certified', 'planner', 'risk', 'lines', 'personal', 'day',
    'schools', 'what', 'why', 'when', 'where', 'our', 'the', 'and', 'for',
    'with', 'this', 'that', 'from', 'have', 'been', 'will', 'would', 'could',
    'should', 'their', 'there', 'which', 'other', 'some', 'many', 'most',
    'free', 'best', 'top', 'new', 'first', 'last', 'next', 'back', 'home',
    'page', 'site', 'web', 'online', 'info', 'information', 'details',
    'submit', 'send', 'get', 'find', 'search', 'browse', 'view', 'see',
    'call', 'today', 'now', 'schedule', 'book', 'appointment', 'meeting'
]

CREDENTIALS = [
    "PhD", "PsyD", "LCSW", "LMFT", "MEd", "MA", "MS", "EdD",
    "CEP", "IEC", "IECA", "MBA", "MSW", "Founder", "Director",
    "Principal", "Counselor", "Therapist", "Consultant",
    "Advisor", "Coach", "Specialist", "MD", "DO", "NP", "RN",
    "LPC", "LCPC", "LMHC", "NCC", "NBCC"
]
CRED_PATTERN = "|".join(re.escape(c) for c in CREDENTIALS)


def is_valid_person_name(name: str) -> bool:
    """Check if name looks like a real person name."""
    name_lower = name.lower()
    words = name.split()
    
    # Must be exactly 2-3 words
    if len(words) < 2 or len(words) > 3:
        return False
    
    # No bad words (check each word individually)
    for word in words:
        if word.lower() in BAD_NAME_WORDS:
            return False
    
    # Each word should be 2-12 chars
    if not all(2 <= len(w.replace('.', '')) <= 12 for w in words):
        return False
    
    # First word should look like a first name (not "Internet", "Licensed", etc.)
    common_non_names = ['internet', 'licensed', 'professional', 'clinical', 'certified',
                        'registered', 'national', 'american', 'eclectic', 'compassion',
                        'focused', 'cognitive', 'behavioral', 'mental', 'health',
                        'therapists', 'therapist', 'family', 'child', 'adult', 'couples',
                        'marriage', 'anxiety', 'depression', 'trauma', 'addiction',
                        'pyne', 'jinny']  # Common false positives
    if words[0].lower() in common_non_names:
        return False
    
    # Last word shouldn't be a title/role
    role_words = ['therapist', 'counselor', 'psychologist', 'psychiatrist', 'coach',
                  'specialist', 'consultant', 'advisor', 'director', 'manager', 'worker']
    if words[-1].lower() in role_words:
        return False
    
    # Filter famous people (likely quotes/testimonials)
    famous = ['maya angelou', 'martin luther', 'oprah winfrey', 'barack obama']
    if name_lower in famous:
        return False
    
    # Filter job titles that look like names
    job_titles = ['social worker', 'case manager', 'program director', 'clinical director']
    if name_lower in job_titles:
        return False
    
    return True


def free_scrape(url: str) -> str:
    """Scrape a URL for free"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()
    
    text = soup.get_text(separator=' ', strip=True)
    return re.sub(r'\s+', ' ', text)[:50000]


def extract_prospects(content: str):
    """Extract prospects from content"""
    names_found = []
    
    # Pattern 1: STRICT - "FirstName LastName, CREDENTIAL" 
    # Only match: "John Smith, PhD" or "Jane Doe, LCSW"
    # The name part must be exactly 2 words, both capitalized
    strict_cred_pattern = rf'\b([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}}),\s*({CRED_PATTERN})\b'
    for match in re.findall(strict_cred_pattern, content):
        name = match[0].strip()
        if is_valid_person_name(name):
            names_found.append({"name": name, "title": match[1], "source": "credentials"})
    
    # Pattern 2: Dr./Mr./Ms. prefix - STRICT
    # "Dr. John Smith" - exactly 2 words after prefix
    prefix_pattern = r'\b(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
    for match in re.findall(prefix_pattern, content):
        name = match.strip()
        if is_valid_person_name(name):
            names_found.append({"name": name, "title": "Dr.", "source": "prefix"})
    
    # Pattern 3: Look for email-like patterns that contain names
    # e.g., "john.smith@example.com" -> "John Smith"
    email_name_pattern = r'([a-z]+)\.([a-z]+)@'
    for match in re.findall(email_name_pattern, content.lower()):
        first, last = match[0].capitalize(), match[1].capitalize()
        name = f"{first} {last}"
        if is_valid_person_name(name) and len(first) > 2 and len(last) > 2:
            names_found.append({"name": name, "title": None, "source": "email"})
    
    # Extract emails
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
    emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.gif'))]
    
    # Extract phones
    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content)
    
    return names_found, list(set(emails)), list(set(phones))


# Test URLs for different categories
TEST_URLS = {
    "psychologist": [
        "https://www.psychologytoday.com/us/therapists/dc/washington",
    ],
    "pediatrician": [
        "https://www.healthgrades.com/pediatrics-directory/dc-district-of-columbia",
    ],
    "education_consultant": [
        "https://markseducation.com/",
        "https://www.collegeadmissionsstrategies.com/",
    ],
}

if __name__ == "__main__":
    print("=" * 60)
    print("PROSPECT EXTRACTION TEST BY CATEGORY")
    print("=" * 60)
    
    for category, urls in TEST_URLS.items():
        print(f"\n📁 CATEGORY: {category.upper()}")
        print("-" * 40)
        
        for url in urls:
            print(f"\n🔍 Testing: {url}")
            try:
                content = free_scrape(url)
                print(f"   Scraped {len(content)} chars")
                
                names, emails, phones = extract_prospects(content)
                
                print(f"   ✅ Names found: {len(names)}")
                for n in names[:5]:
                    print(f"      - {n['name']} ({n['title']})")
                
                print(f"   📧 Emails: {emails[:3]}")
                print(f"   📞 Phones: {phones[:3]}")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)

