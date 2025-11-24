# LinkedIn Industry Targeting - Quick Start

## 🎯 Find What Works in Your Industry

### Step 1: Get Industry Insights

See what's working in your target industry:

```bash
# Replace "SaaS" with your industry
curl http://localhost:8080/api/linkedin/industry/SaaS/insights
```

**This shows you:**
- Top hashtags used
- Top companies posting
- Average engagement scores
- Content patterns that work

### Step 2: Search High-Engaging Posts

Find posts to model your content after:

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your topic",
    "industry": "SaaS",
    "min_engagement_score": 100.0,
    "max_results": 20
  }'
```

### Step 3: Filter by Industry Companies Only

Only see posts from companies in your industry:

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "product updates",
    "industry": "SaaS",
    "filter_by_company": true,
    "max_results": 20
  }'
```

## 📋 Available Industries

Get the full list:
```bash
curl http://localhost:8080/api/linkedin/industries
```

**Common industries:**
- SaaS
- FinTech
- Healthcare
- E-commerce
- AI/ML
- Marketing
- Real Estate
- Education
- Cybersecurity
- Biotech
- Gaming
- Energy

## 🔍 Example Workflows

### For SaaS Companies
```bash
# 1. Get insights
curl http://localhost:8080/api/linkedin/industry/SaaS/insights

# 2. Find high-engaging posts
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "customer success",
    "industry": "SaaS",
    "min_engagement_score": 150.0,
    "max_results": 20
  }'
```

### For FinTech Companies
```bash
# 1. Get insights
curl http://localhost:8080/api/linkedin/industry/FinTech/insights

# 2. Find posts about payments
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "digital payments",
    "industry": "FinTech",
    "max_results": 20
  }'
```

## 💡 Pro Tips

1. **Start with insights** - Understand patterns before searching
2. **Use engagement filters** - Focus on high-performing posts (min_engagement_score: 100+)
3. **Combine with topics** - Narrow down within industry
4. **Filter by company** - See what industry companies are posting

## 📚 Full Documentation

- **Industry Targeting Guide**: `LINKEDIN_INDUSTRY_TARGETING.md`
- **Fine-Tuning Guide**: `LINKEDIN_FINE_TUNING_GUIDE.md`
- **Testing Guide**: `LINKEDIN_TESTING_SUMMARY.md`

---

**Ready to find what works in your industry!** 🚀

