# ChargeReady: small-budget hosting and AI plan

Checked against official product pages on October 17, 2026. Nothing has been purchased or deployed.

A domain is the address. Hosting runs the application, login, database and PDF generator. A separate AI API handles the optional review when a customer presses the review button. Hostinger's AI website or server assistant is not automatically the app's customer-review model or an unlimited review allowance.

## Suggested pilot

1. Keep the current local app until content, security, payment and usability checks are finished.
2. For this Python app, use Hostinger **VPS**, rather than buying ordinary website-builder/shared hosting and expecting Python support. Hostinger says Python/Django/Flask need VPS and that VPS administration is the owner's responsibility. KVM 1 is a reasonable low-traffic pilot candidate; resource testing is still needed before selecting it for real customers.
3. The official UAE-priced page currently displays KVM 1 at **US$6.49/month promotional**, renewing at **US$11.99/month for two years**. Confirm the country, upfront term, renewal total, taxes and domain renewal at checkout. This is not a monthly-pay guarantee or a live quote for your account.
4. Use a separate server-side OpenAI project/key, never a key embedded in the website. Start with a **US$5 AI spending target**, prepaid funds where supported, provider usage alerts and the app's paid-review limits. Provider budget alerts may not be hard stops. Monitor actual charges and revoke/disable the API key if necessary. SMTP, backups, domain renewal, payment fees and server maintenance are additional costs.
5. Consider **gpt-5.6-luna** for the constrained plain-English explanation, subject to a real quality/safety evaluation. Rule-based code performs amounts, calculations and the preparation score; the AI does not decide immigration eligibility. A model being inexpensive does not prove that it is suitable for legal content.

## AI cost example, not a bill

Official GPT-5.6 Luna standard rates below its large-input breakpoint: US$0.20 / million input tokens and US$1.20 / million output tokens. A hypothetical review using 6,000 input tokens and 1,000 total billable output tokens costs:

- Input: $0.0012
- Output: $0.0012
- Total: **$0.0024 per review**, **$0.012 for five**, or **$1.20 for 500 reviews**.

Actual profiles, reasoning tokens, retries, model choice, rates and taxes can change this. The five-review limit controls repeated requests, while payload/output limits and provider monitoring control expense. Review top-ups require an explicit $5 checkout; no automatic customer charge occurs. Failed API calls may cost the business even when the customer's credit is returned.

## How the five-review feature works

A paid application starts with five successful reviews. A transaction reserves a slot before a model call; concurrent requests cannot spend the same allowance. If the call fails or its output cannot be parsed, that slot is returned. Completed results are stored encrypted for account recovery and repeated request IDs return the same result without another call. Five additional reviews are a separate $5 order. Verified payment adds the allowance; refund/dispute revokes that purchase's allowance. The paid PDF entitlement stays separate. The normal preparation checklist continues without AI.

## Owner work before a paid launch

Connect and test PayPal Business sandbox checkout and signed webhooks, then configure the approved live account. Configure transactional email and test delivery/recovery. Establish HTTPS, private database storage, patching, encrypted off-server backups, restore drills, operator policies, and independent legal/security review. Confirm brand/domain availability before buying a domain. The current name/logo are a working brand, not a cleared trademark.

Official sources:

- [Hostinger: supported languages and Python/VPS](https://www.hostinger.com/support/which-programming-languages-and-frameworks-are-supported-at-hostinger/)
- [Hostinger VPS pricing, UAE page](https://www.hostinger.com/ae/vps-hosting)
- [OpenAI GPT-5.6 Luna rates and model details](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
