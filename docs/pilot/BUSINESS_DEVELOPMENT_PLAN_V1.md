# Business development plan V1

- Date: 2026-07-17
- Status: operating proposal
- Process dependency: `FULL_PROCESS_V5_DRAFT.md`, approved for lock in Codex round 5

## 1. Business objective

Build the operating system for commercial flooring estimating:

> Upload a plan set, receive an auditable flooring takeoff and estimate, and let the estimator spend time on exceptions and trade judgment instead of manually reconstructing every room.

The customer does not buy a segmentation model. The customer buys more bidding capacity, faster turnaround, traceable quantities, and fewer expensive omissions.

The twelve-month base objective is **$150,000 MRR / $1.8 million ARR**. The stretch objective is **$250,000 MRR / $3 million ARR**. These are company targets, not forecasts or valuation promises.

## 2. Initial market and customer

### Primary customer profile

Start with commercial flooring contractors that:

- employ roughly 1–10 estimators;
- process commercial PDF plan sets repeatedly;
- use MeasureSquare, STACK, Bluebeam, Excel, or outsourced takeoff;
- lose bidding capacity because estimating is slow;
- can verify our output against completed work;
- can justify a $12,000–$40,000 annual contract if the product saves estimator capacity.

Avoid leading with very small residential installers. Their price sensitivity and support burden work against a high-touch first product. Avoid the largest enterprises until basic security, integrations, permissions, and procurement materials are ready.

### Initial wedge

The first sale is not “replace your whole estimating department.” It is:

> Give us one completed historical project. We will produce an auditable flooring takeoff without seeing your final answer, compare it with your work, show every exception, and measure the time saved.

After the historical proof, run two live projects in parallel before asking the customer to rely on the system as its primary workflow.

## 3. Positioning

Lead with:

- bids completed per estimator;
- turnaround time;
- visible source evidence;
- human control;
- revision and exception handling;
- traceability from plan to quantity.

Do not lead with SAM, Mask2Former, vector graphs, tokens, or GPU training. Models are implementation details.

The differentiator should be **trade-specific, auditable automation**, not a black-box claim that “AI performs takeoff.”

## 4. Pricing

Published market pricing provides a floor, not our intended positioning. MeasureSquare Commercial currently lists at $197 per user per month. STACK lists $249–$299 per user per month billed annually and sells AI area takeoff as an add-on. Kreo publishes lower general takeoff tiers and custom enterprise/AI offerings. Sources: [MeasureSquare](https://cloud.measuresquare.com/purchase/windows), [STACK](https://www.stackct.com/takeoff-and-estimate-pricing/), [Kreo](https://www.kreo.net/).

We should charge for the completed workflow and saved estimator capacity, not merely editor access.

### Founding design-partner offer

- $2,000 onboarding.
- $1,500 monthly.
- Up to 10 processed projects monthly.
- $150–$300 per additional project, based on size/complexity.
- Six-month agreement.
- Direct founder involvement.
- Customer agrees to structured feedback and anonymized performance measurement.

Do not make the design partnership free. Payment establishes that the workflow addresses a real business problem.

### Proposed production packaging

| Plan | Starting price | Intended customer |
|---|---:|---|
| Core | $1,250/month plus usage | Small commercial estimating team |
| Team | $2,500/month | Established flooring contractor |
| Scale | $5,000/month | High-volume regional contractor |
| Enterprise | $7,500–$15,000+/month | Multi-office company and integrations |

Use annual agreements with a 10–15% prepayment discount after the pilot. Retain usage limits until the true AI and human-review cost per project is measured. Do not offer unlimited processing before unit economics are known.

## 5. Sales stages and goals

### Controlled cohort strategy

The founder's sales strength creates a risk: selling faster than product and onboarding can support. Scale in cohorts:

1. Five paid design partners.
2. At least 20 completed real projects.
3. Measured onboarding, review time, cost, and customer value.
4. Expand to 15 customers.
5. Prove repeat usage and retention.
6. Scale founder-led selling.
7. Hire/train sales only after the motion is repeatable.

### Cumulative targets

| Time | Paying customers | MRR target |
|---|---:|---:|
| Month 1 | 3 | $4,500 |
| Month 2 | 5–7 | $8,000–$12,000 |
| Month 3 | 10–15 | $18,000–$25,000 |
| Month 6 | 30–45 | $50,000–$80,000 |
| Month 12 base | 75–100 | $125,000–$175,000 |
| Month 12 stretch | 120–150 | $225,000–$300,000 |
| Month 18 base | 150–200 | $300,000–$400,000 |

The controlling metric is not demos. It is customers repeatedly submitting new projects and renewing.

## 6. Monthly cost guardrails

### Months 1–3

Target operating cost: **$8,000–$20,000/month**, excluding founder compensation.

- AI, GPU, storage, and infrastructure: $2,000–$5,000.
- Senior technical oversight/contract review: $3,000–$8,000.
- Qualified flooring estimator or QA help: $2,000–$5,000.
- Legal, security, and business tools: $1,000–$2,000.

### Months 4–6

Target operating cost: **$25,000–$50,000/month**.

- One strong senior/founding engineer.
- Part-time or full-time flooring QA/customer implementation specialist.
- AI/infrastructure.
- Monitoring, backups, and security work.

### Months 7–12

Target operating cost: **$50,000–$100,000/month**, only when supported by revenue or deliberate financing.

Possible additions:

- second engineer;
- product/design support;
- customer implementation lead;
- additional qualified estimating capacity.

Do not build a large junior development team. One senior technical owner who can use Codex/Claude effectively is more valuable. Do not hire salespeople while the founder remains the strongest seller and the motion is still changing.

SaaS Capital's 2026 private B2B spending survey reports median total spending around 96% of ARR for bootstrapped companies and 101% for equity-backed companies. This supports a capital-efficient plan rather than unlimited burn: [2026 spending benchmarks](https://www.saas-capital.com/blog-posts/spending-benchmarks-for-private-b2b-saas-companies/).

## 7. Unit economics and quality metrics

| Metric | Pilot allowance | Mature target |
|---|---:|---:|
| Gross margin | 40–60% | 75–85% |
| Variable processing cost | Measure every project | Under 15% of revenue |
| Founder-led CAC payback | Under 3 months | — |
| Scaled CAC payback | — | Under 12 months |
| Monthly logo churn | Learn first | Under 1.5% |
| Net revenue retention | Learn first | Above 110% |
| First-project time to value | Under 7 days | Under 1 day |

Track human review time separately from compute. If internal people spend several hours correcting every project indefinitely, the company is operating as a service rather than scalable software.

Customer-value measurements:

- baseline estimator hours versus assisted hours;
- bids processed per estimator;
- turnaround time;
- number and severity of customer corrections;
- critical missed pages/surfaces;
- repeated monthly usage;
- expansion and renewal.

## 8. Founder and hiring plan

The founder should own:

- customer discovery;
- design-partner recruitment;
- pricing and packaging;
- demos and closing;
- sales scripts;
- market positioning;
- customer executive relationships;
- training the future sales organization.

The first critical hire is a senior technical product owner or founding-engineer-level operator. The next is a commercial-flooring quality/customer implementation specialist. Sales hiring follows repeatability, not initial enthusiasm.

## 9. Valuation framework

Do not operate toward a vanity valuation. Operate toward recurring revenue quality, growth, retention, gross margin, and proprietary verified data.

Fundraising valuation and acquisition value are different:

- a fundraising valuation is negotiated from team, market, growth, and financing demand;
- acquisition value is more directly grounded in ARR, growth, retention, margin, and strategic fit.

SaaS Capital's updated framework identifies the public SaaS market, ARR growth, and net revenue retention as primary valuation inputs: [2026 valuation framework](https://www.saas-capital.com/research/whats-your-saas-company-worth/). Its 2025 private estimates were approximately 4.8x ARR for bootstrapped companies and 5.3x for equity-backed companies; this is a benchmark, not a guaranteed multiple: [private SaaS valuation research](https://www.saas-capital.com/blog-posts/private-saas-company-valuations-multiples/).

Planning ranges:

| Business stage | ARR | Indicative business-value range |
|---|---:|---:|
| Pre-revenue prototype | $0 | Team/traction negotiation, not formulaic |
| $25K MRR | $300K | $1.2M–$2M |
| $100K MRR | $1.2M | $5M–$8M |
| $150K MRR | $1.8M | $8M–$13M |
| $250K MRR | $3M | $15M–$24M |
| $500K MRR | $6M | $30M–$50M+ |
| $1M MRR | $12M | $60M–$100M+ |

Strategic value can exceed these ranges if the company owns a defensible flooring dataset, demonstrates strong retention, and becomes embedded in bid workflows. AI branding by itself does not create defensibility.

## 10. Weekly operating scorecard

Review every week:

- new qualified opportunities;
- paid proofs sold;
- customers activated;
- new MRR and total MRR;
- projects submitted and completed;
- median turnaround time;
- customer review minutes per project;
- critical corrections;
- variable cost per project;
- gross margin;
- customer usage and churn risks;
- product blockers affecting multiple customers.

Do not prioritize a feature solely because one prospect requests it. Prioritize repeated workflow failures and capabilities required by the locked process.
