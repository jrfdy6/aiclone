# Quick Fix Plan for Prospect Search Issues

## Issues to Fix (Priority Order)

### 🔴 Priority 1: Organization Name Extraction
**Problem**: Organization shows as "—" because extraction only checks page title
**Impact**: High - missing key prospect data
**Fix**: Extract organization from multiple sources:
- Page title (existing)
- Meta tags (`og:site_name`, `organization`)
- Header sections (h1, h2 near name/title)
- Breadcrumbs
- Practice/center name patterns in content
- Domain name as fallback

### 🔴 Priority 2: Per-Category Query Execution
**Problem**: Multi-category query may be too complex, causing Google to return fewer results
**Impact**: High - only 2 prospects for 5 categories
**Fix**: Run separate Google searches per category, then merge results
- Execute one search per selected category
- Merge and deduplicate prospects
- Better match rate per category

### 🟡 Priority 3: Enhanced Contact Enrichment
**Problem**: Contact info missing even though enrichment should run
**Impact**: Medium - prospects found but not contactable
**Fix**: 
- Ensure enrichment runs for all prospects
- Add more contact extraction patterns
- Better error handling/logging

### 🟡 Priority 4: Category-Specific Extraction Patterns
**Problem**: Some categories (Treatment Centers, Embassies) may not be triggering extraction
**Impact**: Medium - missing categories
**Fix**: Verify extraction methods are being called for each category

---

## Implementation Plan

### Phase 1: Improve Organization Extraction (Quick Win)
1. Extract from multiple HTML sources
2. Use domain name as fallback
3. Check meta tags and structured data

**Estimated Time**: 15 minutes
**Impact**: Immediate improvement in organization names

### Phase 2: Per-Category Search Execution (Major Improvement)
1. Refactor `find_prospects_free` to run per-category searches
2. Merge results and deduplicate
3. Maintain max_results limit across all categories

**Estimated Time**: 30 minutes
**Impact**: 5x more prospects (one search per category instead of combined)

### Phase 3: Enhanced Contact Enrichment
1. Verify enrichment is running
2. Add better error handling
3. Log enrichment attempts and results

**Estimated Time**: 15 minutes
**Impact**: More prospects with contact info

---

## Let's Start with Phase 1 & 2 (Highest Impact)

### Phase 1: Better Organization Extraction
- ✅ Add multi-source organization extraction
- ✅ Use domain/practice name patterns
- ✅ Fallback to domain name

### Phase 2: Per-Category Query Execution
- ✅ Split multi-category search into per-category searches
- ✅ Merge and deduplicate results
- ✅ Preserve all category tags

This should dramatically improve:
- Prospect count (5x increase expected)
- Organization names (from multiple sources)
- Category representation (guaranteed results per category)

