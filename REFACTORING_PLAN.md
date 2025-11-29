# Prospect Discovery Service Refactoring Plan

## Current State
- **File:** `backend/app/services/prospect_discovery_service.py`
- **Size:** 3,946 lines
- **Issues:** 
  - Hard to maintain
  - Prone to indentation errors
  - Difficult to test individual components
  - Mixed concerns (extraction, validation, scoring, saving)

## Refactoring Strategy

### 1. Extract Constants → `prospect_constants.py`
- `CREDENTIALS`, `CRED_PATTERN`
- `PROSPECT_CATEGORIES`
- `DC_AREA_VARIATIONS`, `DC_NEIGHBORHOODS`, `DC_LOCATION_QUERY`
- `GENERIC_EMAIL_PREFIXES`, `BLOCKED_DOMAINS`

### 2. Extract Validators → `prospect_validators.py`
- `_is_valid_person_name()` → `is_valid_person_name()`
- Organization validation logic
- Final prospect validation for saving

### 3. Extract Organization Extraction → `organization_extractor.py`
- `_extract_organization()` method
- All organization extraction logic

### 4. Extract Category-Specific Extractors → `extractors/` directory
- `psychology_today_extractor.py` → `_extract_psychology_today()`, `_extract_psychology_today_listing()`, `_extract_profile_urls_from_json()`
- `doctor_directory_extractor.py` → `_extract_doctor_directory()`
- `treatment_center_extractor.py` → `_extract_treatment_center()`
- `embassy_extractor.py` → `_extract_embassy_contacts()`
- `youth_sports_extractor.py` → `_extract_youth_sports()`
- `generic_extractor.py` → `_extract_generic()`, `extract_prospects_from_content()`

### 5. Extract Scoring → `prospect_scoring.py`
- `calculate_fit_score()` → `calculate_influence_score()`

### 6. Extract Saving Logic → `prospect_saver.py`
- `_save_to_prospects()` method
- `_store_discovery()` method

### 7. Extract Scraping Utilities → `scraping_utils.py`
- `_free_scrape()` method

### 8. Keep Main Service → `prospect_discovery_service.py` (orchestrator)
- `__init__()`, `_init_clients()`
- `build_search_query()`, `build_category_search_query()`
- `find_prospects_free()` (orchestrates extraction)
- `_parse_ai_prospect_response()` (if AI search is used)

## New File Structure

```
backend/app/services/prospect_discovery/
├── __init__.py
├── constants.py
├── validators.py
├── organization_extractor.py
├── prospect_scoring.py
├── prospect_saver.py
├── scraping_utils.py
├── extractors/
│   ├── __init__.py
│   ├── psychology_today_extractor.py
│   ├── doctor_directory_extractor.py
│   ├── treatment_center_extractor.py
│   ├── embassy_extractor.py
│   ├── youth_sports_extractor.py
│   └── generic_extractor.py
└── prospect_discovery_service.py (orchestrator, ~500-800 lines)
```

## Benefits
1. **Maintainability:** Each file has a single responsibility
2. **Testability:** Can test extractors independently
3. **Readability:** Smaller files are easier to understand
4. **Fewer errors:** Less chance of indentation issues
5. **Scalability:** Easy to add new extractors

## Migration Strategy
1. Create new directory structure
2. Move constants first (no dependencies)
3. Move utilities (scraping, validators)
4. Move extractors one by one
5. Update main service to import from new modules
6. Test after each step
7. Keep old file as backup until fully migrated

## Implementation Order
1. ✅ Create directory structure
2. ✅ Extract constants
3. ✅ Extract validators
4. ✅ Extract organization extractor
5. ✅ Extract scraping utils
6. ✅ Extract scoring
7. ✅ Extract saving logic
8. ✅ Extract category extractors (one by one)
9. ✅ Refactor main service to use new modules
10. ✅ Test and verify

