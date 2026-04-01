# Memory Health Check Report - 2026-03-30

## Summary
The following checks were attempted for memory health:

1. **Context Pack Load**: Failed to locate the script for loading context pack.
2. **QMD Freshness Check**: (Check status not captured)
3. **Compaction Guardrail Check**: 
   - reserveTokensFloor: OK
   - softThresholdTokens: OK
   - flush: ON
4. **Index Status Check**: Script not found.
5. **Local Runtime Overrides Check**: Script not found.

## Conclusion
Due to missing scripts, some checks could not be performed. Please ensure all necessary scripts are available in the respective directories to conduct a full health check. Actions may be required to remedy the absence of required resources. Further details can be found in the documentation regarding the local runtime overrides.

---
**Audit Logging**: Health summary has been recorded for review.