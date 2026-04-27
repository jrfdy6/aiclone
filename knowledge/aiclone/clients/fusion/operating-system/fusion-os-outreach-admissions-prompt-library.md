# Fusion OS Outreach And Admissions Prompt Library

## Purpose

Use these prompts against Fusion outreach and admissions data when the goal is not just reporting, but better decisions.

These prompts assume:

- outreach quality matters more than empty activity
- pro relationship strategy matters alongside short-term conversion
- campus context matters, so naive rankings can mislead
- intervention thresholds should drive escalation, not every fluctuation

## How To Use These Prompts

Before any prompt, paste a short context block like this:

```md
use my admissions playbook
campus: [campus]
time window: [last 2 weeks / last 6 weeks / quarter / FYTD / YoY]
primary decision: [reallocate outreach time / coach DAO / prioritize pros / set goals / diagnose risk]
priority outcome: [short-term enrollments / long-term pipeline health / relationship equity]
comparison rule: [compare to LY / compare to recent trend / do not rank against other campuses]
output mode: [executive summary / bullet insights / coaching script]
framing: [risk-first / opportunity-first]
```

If useful, add:

- `treat small week-over-week swings as noise unless they cross my thresholds`
- `do not use generic KPI logic if my playbook suggests a different interpretation`
- `separate structural constraints from execution problems`

## Core Operator Prompts

### 1. What Should I Pay Attention To This Month?

```md
Using my admissions playbook, analyze outreach and admissions performance for [campus] over [time window]. Flag only the patterns that matter for decision-making this month. Separate:
1. immediate risks
2. real opportunities
3. normal variance I should ignore

Then tell me what deserves action now versus monitoring only.
```

### 2. Reallocate Outreach Time

```md
Using my admissions playbook, analyze which outreach segments deserve more time, less time, or steady maintenance for [campus] over [time window]. Base your answer on outreach quality, meeting yield, LPR production, and strategic importance, not raw activity counts.

Return:
1. double down
2. maintain
3. deprioritize
4. watch for future upside
```

### 3. Volume Up, Conversion Down

```md
Using my admissions playbook, analyze [campus] for [time window] where outreach or inquiry volume is up but conversion is down. Diagnose whether this points to:
1. lower-quality demand
2. weak follow-up execution
3. longer-lag pipeline build
4. campus fit or pricing friction
5. expected seasonal distortion

Tell me which interpretation is most likely and why.
```

### 4. Short-Term Versus Long-Term Tradeoff

```md
Using my admissions playbook, evaluate whether current outreach behavior is optimized for:
1. short-term enrollments
2. long-term pipeline health
3. relationship equity with strategically important pros

Tell me where the current mix is imbalanced and what I should rebalance next.
```

## Conversion Stage Prompts

### 5. Inquiry To AM

```md
Using my admissions playbook, analyze Inquiry -> AM performance for [campus] over [time window]. Tell me whether the stage is healthy, delayed, or weak.

Separate:
1. signal
2. noise
3. likely causes
4. interventions worth testing
```

### 6. AM To Register

```md
Using my admissions playbook, analyze AM -> Register performance for [campus] over [time window]. Do not stop at conversion rate. Explain whether the result is being shaped more by:
1. package fit
2. cost friction
3. campus social confidence
4. scheduling lag
5. normal seasonality
```

### 7. Outreach To LPR

```md
Using my admissions playbook, analyze Outreach -> LPR performance for [campus] over [time window]. Focus on which professional segments and outreach behaviors are actually producing LPRs, and which ones are mostly activity without leverage.

Return:
1. strongest pathways
2. weak pathways
3. underdeveloped pathways
4. next actions
```

### 8. Stage Bottleneck Diagnosis

```md
Using my admissions playbook, identify the biggest stage bottleneck for [campus] over [time window] across Inquiry -> AM, AM -> Register, and Outreach -> LPR. Explain why that stage is the real bottleneck and what evidence supports it.
```

## Outreach Quality Prompts

### 9. Quality Outreach Versus Activity For Activity's Sake

```md
Using my admissions playbook, review outreach behavior for [campus] over [time window]. Distinguish quality outreach from empty activity. Use my definitions of strategic pros, meeting quality, follow-up discipline, and LPR conversion.

Tell me:
1. what looks disciplined
2. what looks busy but low-leverage
3. what should change next week
```

### 10. Which Outreach Behaviors Actually Work?

```md
Using my admissions playbook, identify the outreach behaviors that most consistently lead to LPRs for [campus]. Rank them by practical usefulness, not just correlation, and tell me what the operator should repeat.
```

### 11. Outreach Mix Audit

```md
Using my admissions playbook, audit the outreach mix for [campus] over [time window]. Tell me whether the team is over-indexed on:
1. easy but low-yield activity
2. maintenance relationships
3. strategic long-term pipeline building
4. short-term conversion opportunities

Then recommend a better mix.
```

### 12. Follow-Up Discipline

```md
Using my admissions playbook, evaluate whether follow-up behavior after professional meetings is strong enough for [campus] over [time window]. Tell me if weak results are more likely due to poor initial targeting or weak follow-through after good meetings.
```

## Referral Strategy Prompts

### 13. Who Should I Invest Relationship Time In Next?

```md
Using my admissions playbook, identify which pros or pro segments deserve more relationship time next in [campus] over [time window]. Balance:
1. recent results
2. strategic importance
3. likelihood of future referrals
4. relationship equity

Do not rank purely by current volume.
```

### 14. Protect Strategic Referral Sources

```md
Using my admissions playbook, identify the referral relationships I should protect even if recent volume is down. Explain whether each one matters because of fit quality, historical yield, political importance, or future strategic value.
```

### 15. Underdeveloped Pro Segments

```md
Using my admissions playbook, identify which pro segments are strategically underdeveloped for [campus]. Tell me where we may be underinvesting relative to likely long-term value.
```

### 16. Power Referrer Review

```md
Using my admissions playbook, review power-referring pros for [campus] over [time window]. Tell me:
1. who is still healthy
2. who is softening
3. where concentration risk is emerging
4. what backup relationships need to be built
```

### 17. Lag Between Outreach And Referral Yield

```md
Using my admissions playbook, analyze the likely lag between outreach activity and LPR conversion for [campus]. Tell me whether current low yield should be treated as a real issue or an expected delay based on the timing and type of outreach.
```

## Risk And Intervention Prompts

### 18. Intervene Or Observe?

```md
Using my admissions playbook, review [campus] over [time window] and tell me whether current patterns require intervention or observation only. Flag only issues that cross my intervention thresholds.

Return:
1. intervene now
2. monitor closely
3. ignore as noise
```

### 19. Coaching Problem Or System Problem?

```md
Using my admissions playbook, analyze whether the main issue in [campus] over [time window] is:
1. individual execution
2. weak targeting
3. structural market constraint
4. staffing or capacity issue
5. seasonality

Tell me whether this should turn into coaching, process change, or no action.
```

### 20. Earliest Warning Signs

```md
Using my admissions playbook, identify the earliest warning signs in the outreach and admissions data for [campus]. Prioritize indicators that whisper trouble before register numbers fall.
```

### 21. Hidden Strengths

```md
Using my admissions playbook, identify positive patterns in the data that could be easy to miss if someone looked only at headline conversion or register numbers. Tell me what is healthier than it appears and why.
```

## Coaching Prompts

### 22. Coach A DAO

```md
Using my admissions playbook, review [person or campus] over [time window] and write a coaching brief for a DAO. Distinguish:
1. what they are doing well
2. what is not yet working
3. the most likely reason
4. the one behavior to tighten first
5. the one relationship strategy to improve next
```

### 23. Coaching Script

```md
Using my admissions playbook, turn the current outreach and admissions performance for [person or campus] into a short coaching script I can say out loud. Keep it direct, specific, and operational. Include:
1. what I noticed
2. why it matters
3. what I want changed
4. what success looks like next month
```

### 24. Praise With Precision

```md
Using my admissions playbook, identify the strongest operator behaviors in [person or campus] over [time window]. Write a short recognition note that reinforces the behaviors actually worth repeating, not just the outcome.
```

## Goal-Setting Prompts

### 25. Set Next Month's Goals

```md
Using my admissions playbook, recommend goals for [campus] for the next month. Separate:
1. outreach activity goals
2. quality goals
3. referral relationship goals
4. conversion goals

Make sure the goals reflect structural constraints and seasonality rather than generic growth assumptions.
```

### 26. Is This Quarter Off-Track Or Just Delayed?

```md
Using my admissions playbook, tell me whether [campus] is directionally off-track this quarter or just delayed. Use the right time horizon, expected lags, seasonality, and known distortions before calling something a problem.
```

### 27. Goal Fairness Across Campuses

```md
Using my admissions playbook, review whether current goals or expectations are fair across campuses. Tell me which comparisons are valid, which are misleading, and where structural differences should change interpretation.
```

## Executive Review Prompts

### 28. Executive Summary

```md
Using my admissions playbook, write an executive summary of [campus] outreach and admissions performance for [time window]. Keep it concise and decision-oriented.

Include:
1. what matters most
2. what does not matter yet
3. biggest risk
4. biggest opportunity
5. one recommendation
```

### 29. Risk-First Readout

```md
Using my admissions playbook, produce a risk-first readout for [campus] over [time window]. Only surface risks that are actionable, material, and above threshold. Do not pad with generic observations.
```

### 30. Opportunity-First Readout

```md
Using my admissions playbook, produce an opportunity-first readout for [campus] over [time window]. Focus on where additional effort, better sequencing, or stronger follow-up could create meaningful gains without pretending every positive trend is durable.
```

## Pattern-Sensitivity Prompts

### 31. Noise Versus Signal

```md
Using my admissions playbook, analyze whether recent week-over-week movement in [metric or stage] is signal or noise for [campus]. Use my preferred sensitivity to variance, seasonality, and the right comparison window.
```

### 32. When YoY Should Not Be Trusted

```md
Using my admissions playbook, evaluate whether YoY is a valid comparison for [campus] and [time window]. Tell me what would make YoY misleading here and what comparison I should trust instead.
```

### 33. Structural Constraint Check

```md
Using my admissions playbook, assess whether weak performance in [campus] looks like real underperformance or a structural constraint caused by market maturity, staffing, capacity, or campus context.
```

## Notes On Interpretation

- A high-activity answer is not automatically a good answer.
- A low-conversion answer is not automatically a bad answer if the work is building high-value future pipeline.
- A campus should not be called weak without checking structural constraints first.
- A relationship should not be deprioritized only because recent ROI is soft.
- A drop should not be escalated until it crosses your actual intervention logic.

## Suggested Next Layer

If you want this library to become sharper, the next step is to define:

- your exact intervention thresholds
- your definitions of acceptable, strong, and concerning by stage
- your real time windows for trusted trend judgment
- which campuses and roles should not be compared directly
- which pro segments count as priority, maintenance, and long-term only
