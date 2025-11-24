# Phase 6 API Testing

## Quick Start

Run the test suite to verify all Phase 6 endpoints are working:

```bash
cd frontend
./test-phase6-simple.sh
```

## Test Coverage

The test suite covers all Phase 6 features:

### 6.1: Advanced AI & Machine Learning
- ✅ Predictive Analytics (Optimal Posting Time)
- ✅ Recommendations (Prospects, Topics, Hashtags)
- ✅ NLP Services (Intent, Entities, Summarization)
- ✅ Content Optimization (Scoring)

### 6.4: Advanced Analytics & BI
- ✅ Business Intelligence Dashboard
- ✅ Advanced Reporting
- ✅ Predictive Insights

### 6.5: Advanced Content Generation
- ✅ Multi-Format Generation (Blog, Email)
- ✅ Content Library
- ✅ Cross-Platform Analytics

## Test Script Details

**File:** `test-phase6-simple.sh`

**Features:**
- Tests 13 API endpoints
- Color-coded output (green for pass, red for fail)
- Summary statistics
- Easy to extend with new tests

**Customization:**
```bash
# Use custom API URL
NEXT_PUBLIC_API_URL=https://your-api-url.com ./test-phase6-simple.sh

# Use custom test user ID
TEST_USER_ID=my-user-id ./test-phase6-simple.sh
```

## Expected Results

When all tests pass:
```
✅ Passed: 13
❌ Failed: 0
🎉 All tests passed!
```

## Troubleshooting

If tests fail:
1. Check API URL is correct
2. Verify backend is deployed and running
3. Check network connectivity
4. Review error messages in test output

