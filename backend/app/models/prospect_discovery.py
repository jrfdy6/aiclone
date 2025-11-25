"""
Prospect Discovery Models

For finding actual prospects (people/organizations) from public directories.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ProspectSource(str, Enum):
    """Sources for prospect discovery"""
    PSYCHOLOGY_TODAY = "psychology_today"
    IECA_DIRECTORY = "ieca_directory"
    GOOD_THERAPY = "good_therapy"
    NAIS_SCHOOLS = "nais_schools"
    BOARDING_SCHOOL_REVIEW = "boarding_school_review"
    PRIVATE_SCHOOL_REVIEW = "private_school_review"
    TREATMENT_CENTERS = "treatment_centers"
    GENERAL_SEARCH = "general_search"


# Site-specific search patterns
SOURCE_DORKS: Dict[ProspectSource, List[str]] = {
    ProspectSource.PSYCHOLOGY_TODAY: [
        'site:psychologytoday.com/us/therapists "{specialty}"',
        'site:psychologytoday.com "educational consultant" "{location}"',
        'site:psychologytoday.com "{specialty}" "{location}" "private school"',
    ],
    ProspectSource.IECA_DIRECTORY: [
        'site:iecaonline.com "{specialty}"',
        'site:iecaonline.com "educational consultant" "{location}"',
    ],
    ProspectSource.GOOD_THERAPY: [
        'site:goodtherapy.org/therapists "{specialty}" "{location}"',
    ],
    ProspectSource.NAIS_SCHOOLS: [
        'site:nais.org "member school" "{location}"',
        '"admissions director" "independent school" "{location}"',
    ],
    ProspectSource.BOARDING_SCHOOL_REVIEW: [
        'site:boardingschoolreview.com "{specialty}" "{location}"',
    ],
    ProspectSource.PRIVATE_SCHOOL_REVIEW: [
        'site:privateschoolreview.com "{location}"',
    ],
    ProspectSource.TREATMENT_CENTERS: [
        '"therapeutic boarding school" "admissions" "{location}"',
        '"wilderness therapy" "admissions director" "{location}"',
        '"residential treatment" "educational liaison" "{location}"',
    ],
    ProspectSource.GENERAL_SEARCH: [
        '"{specialty}" "{location}" contact email',
        '"{specialty}" "director" "{location}"',
    ],
}


# Extraction patterns for different sources
SOURCE_EXTRACTION_HINTS: Dict[ProspectSource, Dict[str, Any]] = {
    ProspectSource.PSYCHOLOGY_TODAY: {
        "name_patterns": ["Dr.", "LCSW", "LMFT", "PhD", "PsyD", "MEd"],
        "title_patterns": ["Therapist", "Counselor", "Consultant", "Psychologist"],
        "contact_patterns": ["email", "phone", "website", "contact"],
    },
    ProspectSource.NAIS_SCHOOLS: {
        "name_patterns": ["Director", "Head of", "Dean"],
        "title_patterns": ["Admissions", "Enrollment", "School"],
        "contact_patterns": ["admissions@", "contact", "apply"],
    },
}


class ProspectContact(BaseModel):
    """Contact information for a prospect"""
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None


class DiscoveredProspect(BaseModel):
    """A prospect discovered from public sources"""
    name: str = Field(..., description="Full name")
    title: Optional[str] = Field(None, description="Job title")
    organization: Optional[str] = Field(None, description="Company/school name")
    specialty: List[str] = Field(default_factory=list, description="Areas of expertise")
    location: Optional[str] = Field(None, description="City, State")
    source_url: str = Field(..., description="URL where found")
    source: ProspectSource = Field(..., description="Source type")
    contact: ProspectContact = Field(default_factory=ProspectContact)
    bio_snippet: Optional[str] = Field(None, description="Short bio excerpt")
    fit_score: int = Field(0, description="Calculated fit score 0-100")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw extracted data")


class ProspectDiscoveryRequest(BaseModel):
    """Request for prospect discovery"""
    user_id: str = Field(..., description="User ID")
    source: ProspectSource = Field(..., description="Source to search")
    specialty: Optional[str] = Field(None, description="Specialty filter (e.g., 'educational consultant')")
    location: Optional[str] = Field(None, description="Location filter (e.g., 'California')")
    keywords: List[str] = Field(default_factory=list, description="Additional keywords")
    max_results: int = Field(20, description="Max prospects to return", ge=5, le=50)
    auto_score: bool = Field(True, description="Auto-calculate fit scores")
    save_to_prospects: bool = Field(False, description="Save to /api/prospects")


class ProspectDiscoveryResponse(BaseModel):
    """Response from prospect discovery"""
    success: bool
    discovery_id: str
    source: str
    total_found: int
    prospects: List[DiscoveredProspect] = Field(default_factory=list)
    search_query_used: str = ""
    error: Optional[str] = None


# Specialty mappings by theme
THEME_SPECIALTIES: Dict[str, List[str]] = {
    "referral_networks": [
        "educational consultant",
        "school placement",
        "therapeutic boarding school",
        "adolescent therapy",
        "family therapy",
        "learning differences",
        "college counseling",
        "wilderness therapy",
    ],
    "enrollment_management": [
        "admissions director",
        "enrollment management",
        "head of school",
        "private school",
        "independent school",
        "boarding school",
    ],
    "neurodivergent_support": [
        "learning differences",
        "ADHD specialist",
        "autism support",
        "special education",
        "neurodivergent",
        "twice exceptional",
        "executive function",
    ],
}


# Location shortcuts
LOCATION_SHORTCUTS: Dict[str, str] = {
    "DC": "District of Columbia",
    "CA": "California",
    "NY": "New York",
    "TX": "Texas",
    "FL": "Florida",
    "MA": "Massachusetts",
    "CT": "Connecticut",
    "NJ": "New Jersey",
    "PA": "Pennsylvania",
    "VA": "Virginia",
    "MD": "Maryland",
}

