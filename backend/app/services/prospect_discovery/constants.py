"""
Constants for prospect discovery service
"""
import re

# =============================================================================
# UNIVERSAL CREDENTIALS & TITLES (Layer 1)
# =============================================================================

CREDENTIALS = [
    # Medical
    "MD", "DO", "PhD", "PsyD", "LCSW", "LMFT", "LPC", "NP", "RN", "LMHC", "LCPC",
    "Pediatrician", "Psychiatrist", "Psychologist", "Neuropsychologist",
    # Treatment/Admin
    "Director", "Admin", "Admissions", "Clinical Director", "Program Director",
    "Executive Director", "Administrator", "Manager", "Coordinator",
    # Education
    "CEP", "IEC", "IECA", "MEd", "EdD", "MA", "MS", "MBA", "MSW",
    "Counselor", "Consultant", "Advisor", "Coach", "Specialist",
    # Leadership
    "Founder", "President", "Chair", "Owner", "Principal", "Leader",
    # Embassy/Diplomatic
    "Ambassador", "Attaché", "Consul", "Officer", "Diplomat",
]

CRED_PATTERN = "|".join(re.escape(c) for c in CREDENTIALS)

# =============================================================================
# PROSPECT CATEGORIES
# =============================================================================

PROSPECT_CATEGORIES = {
    "education_consultants": {
        "name": "Education Consultants",
        "keywords": ["educational consultant", "college counselor", "IEC", "IECA", "CEP", "school placement"],
        "search_terms": ["educational consultant", "independent education consultant", "college counselor"],
    },
    "pediatricians": {
        "name": "Pediatricians",
        "keywords": ["pediatrician", "pediatric", "child doctor", "adolescent medicine"],
        "search_terms": ["pediatrician adolescent", "pediatric practice", "child doctor"],
    },
    "psychologists": {
        "name": "Psychologists & Psychiatrists",
        "keywords": ["psychologist", "psychiatrist", "therapist", "mental health", "child psychology"],
        "search_terms": ["child psychologist", "adolescent psychiatrist", "family therapist"],
    },
    "treatment_centers": {
        "name": "Treatment Centers",
        "keywords": ["treatment center", "residential treatment", "therapeutic", "rehab", "admissions"],
        "search_terms": ["treatment center admissions", "residential treatment adolescent", "therapeutic boarding"],
    },
    "embassies": {
        "name": "Embassies & Diplomats",
        "keywords": ["embassy", "diplomat", "cultural officer", "education attaché", "consulate"],
        "search_terms": ["embassy education officer", "cultural affairs", "diplomatic family services"],
    },
    "youth_sports": {
        "name": "Youth Sports Programs",
        "keywords": ["athletic academy", "sports academy", "elite athlete", "youth sports", "travel team"],
        "search_terms": ["athletic academy director", "elite youth sports", "sports academy high school"],
    },
    "mom_groups": {
        "name": "Mom Groups & Parent Networks",
        "keywords": ["mom group", "parent network", "PTA", "family", "parenting coach"],
        "search_terms": ["mom group leader", "parent network", "family services"],
    },
    "international_students": {
        "name": "International Student Services",
        "keywords": ["international student", "ESL", "foreign student", "visa", "host family"],
        "search_terms": ["international student services", "foreign student placement", "host family coordinator"],
    },
}

# =============================================================================
# DC AREA LOCATION VARIATIONS
# =============================================================================

DC_AREA_VARIATIONS = [
    "Washington DC", "DC", "D.C.", "DMV", "NOVA", "Northern Virginia",
    "Montgomery County", "Fairfax", "Arlington", "Bethesda", "Silver Spring",
    "Alexandria", "Chevy Chase", "Georgetown", "Capitol Hill", "Potomac",
    "McLean", "Tysons", "Rockville", "College Park", "Prince George"
]

# DC Neighborhoods - These are valid location names that should NOT be filtered
# Even though they contain location words, they are legitimate place names
DC_NEIGHBORHOODS = [
    "Capitol Heights", "Adams Morgan", "Anacostia", "Barry Farm", "Bellevue",
    "Benning", "Bloomingdale", "Brightwood", "Brookland", "Burleith",
    "Capitol Hill", "Chevy Chase", "Chinatown", "Columbia Heights", "Congress Heights",
    "Crestwood", "Deanwood", "Dupont Circle", "Eckington", "Edgewood",
    "Foggy Bottom", "Fort Totten", "Foxhall", "Friendship Heights", "Garfield Heights",
    "Georgetown", "Glover Park", "H Street", "Hillcrest", "Ivy City",
    "Kalorama", "Kenilworth", "Kingman Park", "Lamond Riggs", "LeDroit Park",
    "Logan Circle", "Manor Park", "Marshall Heights", "Massachusetts Heights", "Mayfair",
    "Mount Pleasant", "Navy Yard", "NoMa", "North Cleveland Park", "Northwest",
    "Palisades", "Park View", "Penn Branch", "Petworth", "Potomac Heights",
    "Randall Heights", "River Terrace", "Shaw", "Shepherd Park", "Southeast",
    "Southwest", "Stanton Park", "Takoma", "Tenleytown", "The Palisades",
    "Trinidad", "Truxton Circle", "Twining", "Union Heights", "Union Station",
    "U Street", "Washington Heights", "Wesley Heights", "West End", "Woodley Park",
    "Woodridge", "Woodland", "Woodland Terrace"
]

DC_LOCATION_QUERY = '("Washington DC" OR "DC" OR "DMV" OR "NOVA" OR "Montgomery County" OR "Fairfax" OR "Arlington" OR "Bethesda")'

# Generic email prefixes to filter out
GENERIC_EMAIL_PREFIXES = ['info', 'contact', 'support', 'hello', 'admin', 'sales', 
                          'help', 'office', 'mail', 'enquiries', 'inquiries', 'noreply',
                          'webmaster', 'newsletter', 'team', 'careers', 'jobs']

# Domains that can't be scraped or block bots
BLOCKED_DOMAINS = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com', 
                   'youtube.com', 'tiktok.com', 'pinterest.com', 'glassdoor.com',
                   'indeed.com', 'iecaonline.com']  # These block scraping

