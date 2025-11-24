# Cost-Optimized Perplexity Model Setup

## ✅ Current Configuration: **sonar** (Base Model)

**Decision**: Use base `sonar` model for cost efficiency while maintaining sufficient quality for prospecting workflow.

---

## Why `sonar` (Base) is Perfect for Your Use Case

### ✅ Cost Benefits
- **Lowest per-token cost**: ~$0.001-0.002 per 1K tokens
- **Reasonable request costs**: $5-12 per 1K requests
- **Estimated monthly cost**: $5-20 (for ~10 research + 20 scoring prompts/week)
- **Aligns with "near-zero cost" goal** ✅

### ✅ Capability Match
- ✅ Summarize web research effectively
- ✅ Pull basic insights for prospect scoring
- ✅ Handle light-to-medium complexity prompts
- ✅ Good enough for prospecting research needs

### ⚠️ Trade-offs (Acceptable)
- Not optimal for very deep research (but you have Firecrawl for that)
- Less "thoughtful" reasoning vs reasoning models (but sufficient for your workflow)
- For competitive intelligence, might need upgrade (but can switch per-request)

---

## Model Configuration

### Default: `sonar` (Base)
```python
# In backend/app/services/perplexity_client.py
model: str = "sonar"  # Cost-optimized default
```

### Available Models (Easy to Switch)

| Model | Cost | Quality | When to Use |
|-------|------|---------|-------------|
| **sonar** | 💰 Lowest | ⭐ Good | **Default - Most queries** |
| **sonar-pro** | 💰💰 Medium | ⭐⭐ Better | Complex queries, deeper research |
| **sonar-reasoning-pro** | 💰💰💰 Higher | ⭐⭐⭐ Best | Strategic analysis, complex reasoning |

---

## Cost Estimates

### Scenario: Your Typical Usage
- **10 research prompts/week** (medium length)
- **20 scoring prompts/week** (short-to-medium length)
- **Total: ~120 prompts/month**

**Using `sonar` (base):**
- Token costs: Minimal (~$2-5/month)
- Request costs: ~$0.60-1.44/month (at $5-12 per 1K)
- **Total: ~$5-10/month** ✅

**If you used `sonar-pro` instead:**
- **Total: ~$20-40/month** (2-4x more expensive)

**If you used `sonar-reasoning-pro`:**
- **Total: ~$50-100/month** (5-10x more expensive)

---

## Flexible Model Selection

### Option 1: Use Default (sonar) for Everything
```python
# Automatic - uses "sonar" by default
perplexity.research_topic("SaaS companies")
```

### Option 2: Override for Specific Research
```python
# Use sonar-pro for deeper research when needed
perplexity.research_topic(
    "SaaS companies",
    model="sonar-pro"  # Upgrade for this specific query
)
```

### Option 3: Environment Variable Override
```bash
# In .env file
PERPLEXITY_MODEL=sonar-pro  # Override default if needed
```

---

## When to Upgrade Model

### Stick with `sonar` (base) when:
- ✅ Regular prospecting research
- ✅ Basic insight extraction
- ✅ Cost is a priority
- ✅ Speed matters

### Consider `sonar-pro` when:
- ⚠️ Research quality is insufficient
- ⚠️ Need deeper competitive intelligence
- ⚠️ Complex multi-source synthesis needed

### Consider `sonar-reasoning-pro` when:
- ⚠️ Strategic planning tasks
- ⚠️ Complex multi-step analysis
- ⚠️ Quality is critical (and cost acceptable)

---

## Implementation

### Current Setup (Cost-Optimized)
```python
# backend/app/services/perplexity_client.py
def search(
    self,
    query: str,
    model: str = "sonar",  # ✅ Cost-optimized default
    ...
):
```

### Research Route (Uses Default)
```python
# backend/app/routes/research.py
research_data = perplexity.research_topic(
    topic=request.topic,
    num_results=10,
    include_comparison=True,
    # Uses default "sonar" model
)
```

### Easy Upgrade Path
If you need better quality for specific queries, you can:
1. Add `model` parameter to research route
2. Allow per-request model selection
3. Use environment variable for global override

---

## Cost Monitoring

### Track Your Usage
- Monitor Perplexity API dashboard
- Track request counts
- Monitor token usage
- Adjust model selection based on actual costs

### Cost Optimization Tips
1. ✅ Use `sonar` for most queries (current setup)
2. ✅ Combine with Firecrawl for deeper content (you're already doing this)
3. ✅ Cache research results when possible
4. ✅ Only upgrade model when quality is insufficient

---

## Summary

**Current Configuration:**
- ✅ Default model: `sonar` (base)
- ✅ Cost: ~$5-10/month estimated
- ✅ Quality: Sufficient for prospecting workflow
- ✅ Flexible: Easy to upgrade per-request if needed

**This setup aligns perfectly with your "near-zero cost" goal while maintaining good research quality!** 🎯

---

**Next Steps:**
1. ✅ Code updated to use `sonar` by default
2. Monitor actual costs in Perplexity dashboard
3. Upgrade to `sonar-pro` only if quality is insufficient
4. Consider hybrid approach (sonar for most, sonar-pro for complex)



