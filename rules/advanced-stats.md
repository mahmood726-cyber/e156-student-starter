# Advanced Statistics Rules (gotchas only)

> Formulas/theory: look up when needed. This file = mistake-prevention rules only.

## Pooling
- **DL bias**: Never use DL for k<10 - use REML or PM.
- **HKSJ floor**: If `Q < k-1`, HKSJ *narrows* CI below DL - set floor: `max(1, Q/(k-1))`.
- **HKSJ df**: Use `qt(alpha/2, k-1)` NOT `qnorm`. t-distribution matters when k<30.
- **OR->SMD constant**: `sqrt(3)/pi ~= 0.5513`, NOT `sqrt(3/pi)`.
- **Fisher z variance**: `1/(n-3)` exact - don't use n-2.
- **Log scale**: Always pool logRR/logOR/logHR, back-transform after. Natural scale + RE = Simpson's paradox.
- **Zero cells**: Add 0.5 ONLY if >=1 cell is zero. Unconditional correction biases OR->1.
- **PI formula**: `t_{k-2}` NOT `t_{k-1}`. Undefined for k<3.

## Heterogeneity
- **I^2 != magnitude**: Measures proportion, not amount. Report tau^2 alongside.
- **I^2=0 != homogeneity**: Just means Q <= df. Low power with few studies.
- **I^2 CI**: Use Q-profile method (Viechtbauer 2007) for small k.

## Publication Bias
- **Egger's**: Use radial version. Low power for k<10. For binary outcomes: use Peters' test.
- **Trim-and-fill**: Sensitivity analysis only - never the primary result.
- **PET-PEESE**: PET first; if rejects null, switch to PEESE. Conditional procedure matters.
- **Copas**: Needs k>=15.

## NMA
- **Always test consistency** (design-by-treatment + node-splitting) before interpreting.
- **SUCRA != effect size**: Never rank by SUCRA alone - show CrI of relative effects.
- **Disconnected networks**: Cannot do NMA. Check connectivity first.
- **Multi-arm trials**: Off-diagonal covariance = `tau^2/2` (shared control).

## DTA
- **Bivariate convergence**: Common failure with k<5. Constrain rho to [-0.95, 0.95] or fix rho=0.
- **Threshold effect**: Spearman corr(logit(Se), logit(1-Sp)) > 0.6 -> report SROC curve, not pooled Se/Sp.

## Bayesian
- **Rhat > 1.01**: Do NOT interpret. Increase iterations or reparameterize.
- **ESS < 400**: Unreliable CrI. Need >=400 per parameter.
- **Divergent transitions**: Increase adapt_delta to 0.95-0.99 or use non-centered parameterization.
- **Grid approximation**: 200x200 OK for unimodal. Fails beyond 2-3 params - use MCMC.

## Survival
- **RMST**: Always state tau*. Pool differences, not ratios.
- **Guyot IPD**: Never claim IPD-level accuracy. Verify events/median/p-value match published.
- **Non-PH**: If Schoenfeld rejects PH, single HR is misleading. Use interval HRs or RMST.

## Numerical
- **NPD matrix**: Fix with nearPD() (Higham), NOT eigenvalue clamping.
- **Log-likelihood**: Always compute on log scale. `exp(a)+exp(b)` -> `exp(a)*(1+exp(b-a))`.
- **Fisher z at r=+/-1**: Clamp to [-0.9999, 0.9999].
- **logit(0)/logit(1)**: Clamp to [1e-10, 1-1e-10].
- **Clopper-Pearson**: `qbeta(alpha/2, x, n-x+1)` - the alpha/2 IS correct. Agents false-flag this.

## TSA
- **O'Brien-Fleming**: `z_k = z_alpha / sqrt(t_k)`.
- **Design effect for heterogeneity**: `D = 1 + tau^2 * (sum(1/v_i^2)/(sum(1/v_i))^2 * k - 1)`. NOT cluster-design effect.
- **Binding vs non-binding futility**: If tool allows ignoring futility, must be non-binding.
