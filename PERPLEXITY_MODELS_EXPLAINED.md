# Perplexity API Models Explained

## Key Difference: Legacy vs. Current Models

### ❌ `llama-3.1-sonar-large-128k-online` (Deprecated)
- **Status**: **Deprecated as of February 22, 2025**
- **Why it failed**: This model name is no longer supported by Perplexity API
- **Legacy name**: This was the old name for what is now `sonar-pro`
- **Context Window**: 128,000 tokens
- **Cost**: $1.00 per million tokens (was cheaper)

### ✅ `sonar-pro` (Current)
- **Status**: **Currently supported and recommended**
- **What it is**: The modern, renamed version of `llama-3.1-sonar-large-128k-online`
- **Context Window**: 128,000-200,000 tokens (larger than legacy)
- **Cost**: Higher ($3 input + $15 output per 750,000 words)
- **Capabilities**: Enhanced for complex queries, deeper research, better reasoning

## All Available Perplexity Models (2025)

| Model | Status | Use Case | Context | Cost |
|-------|--------|----------|---------|------|
| **sonar** | ✅ Current | Fast, lightweight queries | 128k tokens | Lower |
| **sonar-pro** | ✅ Current | Deep research, complex queries | 128k-200k tokens | Higher |
| **sonar-reasoning** | ✅ Current | Real-time reasoning with search | - | - |
| **sonar-reasoning-pro** | ✅ Current | Enhanced reasoning (DeepSeek-R1) | - | - |
| **llama-3.1-sonar-large-128k-online** | ❌ Deprecated | (Old name for sonar-pro) | 128k tokens | - |

## Why Your Code Failed

1. **Deprecated Model Name**: `llama-3.1-sonar-large-128k-online` was discontinued
2. **API Rejection**: Perplexity API returns 400 Bad Request for deprecated models
3. **Solution**: Use `sonar-pro` instead (same capabilities, new name)

## Model Comparison

### `sonar` (Fast & Lightweight)
- **Best for**: Quick searches, simple Q&A, chatbots
- **Speed**: Fastest
- **Cost**: Lowest
- **Use when**: Speed and cost are priorities

### `sonar-pro` (Advanced & Deep)
- **Best for**: Complex queries, multi-step reasoning, document analysis
- **Speed**: Slower but more thorough
- **Cost**: Higher
- **Use when**: You need comprehensive, well-sourced answers

## What Changed in Your Code

**Before (Broken):**
```python
model: str = "llama-3.1-sonar-large-128k-online"  # ❌ Deprecated
```

**After (Fixed):**
```python
model: str = "sonar-pro"  # ✅ Current, supported
```

## Recommendation for Your Use Case

For **prospecting research** (which you're doing), **`sonar-pro`** is the right choice because:
- ✅ Handles complex industry research queries
- ✅ Provides comprehensive, well-sourced answers
- ✅ Better for multi-step research tasks
- ✅ Supports longer context for combining multiple sources

If you need faster/cheaper responses for simple queries, you could also use `sonar`, but `sonar-pro` gives better results for research tasks.

---

**TL;DR**: `llama-3.1-sonar-large-128k-online` is the old (deprecated) name. `sonar-pro` is the new name for the same advanced model. Always use `sonar-pro` going forward.

