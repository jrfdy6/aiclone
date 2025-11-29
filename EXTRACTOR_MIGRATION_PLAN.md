# Extractor Migration Plan

## Current Status

✅ **Core modules extracted:**
- constants.py
- validators.py
- organization_extractor.py
- scraping_utils.py
- scoring.py
- prospect_saver.py
- extractors/base.py
- extractors/factory.py

## Extractor Methods to Migrate

The following extractor methods in `prospect_discovery_service.py` need to be extracted:

1. **`_extract_psychology_today()`** (~120 lines)
   - Extract to: `extractors/psychology_today.py`
   - Class: `PsychologyTodayExtractor(BaseExtractor)`

2. **`_extract_psychology_today_listing()`** (~190 lines)
   - Same file: `extractors/psychology_today.py`
   - Method: `extract_listing()` in `PsychologyTodayExtractor`

3. **`_extract_profile_urls_from_json()`** (~85 lines)
   - Same file: `extractors/psychology_today.py` or shared utility
   - Static method or utility function

4. **`_extract_doctor_directory()`** (~213 lines)
   - Extract to: `extractors/doctor_directory.py`
   - Class: `DoctorDirectoryExtractor(BaseExtractor)`

5. **`_extract_treatment_center()`** (~428 lines)
   - Extract to: `extractors/treatment_center.py`
   - Class: `TreatmentCenterExtractor(BaseExtractor)`

6. **`_extract_embassy_contacts()`** (~329 lines)
   - Extract to: `extractors/embassy.py`
   - Class: `EmbassyExtractor(BaseExtractor)`

7. **`_extract_youth_sports()`** (~335 lines)
   - Extract to: `extractors/youth_sports.py`
   - Class: `YouthSportsExtractor(BaseExtractor)`

8. **`_extract_generic()`** (~337 lines)
   - Extract to: `extractors/generic.py`
   - Class: `GenericExtractor(BaseExtractor)`

## Migration Pattern

Each extractor should:

1. Inherit from `BaseExtractor`
2. Implement `extract(content, url, source, category)` method
3. Use imports from new modules:
   - `from ..constants import PROSPECT_CATEGORIES, GENERIC_EMAIL_PREFIXES`
   - `from ..validators import is_valid_person_name`
   - `from ..organization_extractor import extract_organization`
   - `from ..scraping_utils import free_scrape`

## Benefits

- Main file reduces from ~3,100 lines → ~400 lines (orchestrator)
- Each extractor is independently testable
- Easy to add new extractors
- Clear separation of concerns
- Factory pattern auto-selects extractors

## Next Steps

1. Extract one extractor as a pattern (e.g., `generic.py`)
2. Test that it works
3. Extract remaining extractors one-by-one
4. Update main service to use factory pattern
5. Remove old extractor methods from main file

