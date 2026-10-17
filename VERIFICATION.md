# Verification — October 17, 2026

## Automated checks

- Full Python discovery: **75 tests passed**. Covers financial calculations, unknown values, three-page sample and two-page short dossier, overflow rejection, evidence, attestation, paid access, safe source serving, origin/CSRF/host checks, cookie session handling, AI consent/configuration and mocked wording protection.
- Storage coverage includes per-application entitlements, foreign application denial, optimistic save conflicts, 20 restorable revisions, logout revocation, pause/re-enable revocation, encrypted-data recovery wraps, one-time MFA and backup codes, payment event idempotency, refund revocation, account closure and audit-tamper detection.
- Provider tests use mocks for PayPal capture amount/payee/application checks, signed-webhook verification and refund reconciliation. Private local mail preview and encrypted database backup/restore with no overwrite passed.
- Six Web Crypto backup checks passed: round trip, encrypted contents, randomness, incorrect password, authenticated tampering and weak-password rejection.
- Workspace checks passed: stale encryption cancellation, account/application-scoped requests, serialized optimistic versions, persistent failed-save state, recovery unlock, password rewrap and preservation of encrypted answers.
- Updated JavaScript syntax and Python source parsing passed.

## Browser and PDF checks

- Notice checkbox gate, signed-in identity, separate Account / Sign out, paid application restoration, saved-before-sign-out behavior, refresh with locked answers and subsequent password unlock verified in the in-app browser.
- App review and PDF share the presentation schema; automated checks compare section headings and entered values. Updated complete fictional dossier is three US Letter pages; all three rendered pages were visually inspected without clipping or overlap. Short profiles use two pages. Private identity fields remain blank for handwriting.
- Actual PDF page images replace the blank browser PDF iframe. Browser displayed all three page images; first-page layout visually inspected. Private temporary rendering files are removed after the request.
- Browser download completed at Downloads/visaready-draft-dossier.pdf. Independently parsed: three pages, draft marker and handwritten case-number blank present.
- Administrator login, readable account/order tables, role-based actions, MFA enrollment entry, private support table and audit integrity status verified. Sensitive-action dialog requires reason, reference where applicable, password and configured MFA. No live account deletion or payment mutation performed during final browser checks; those paths are tested in isolated databases.
- Signed out of administrator console after verification. No real applicant answers or private documents were added to the release package.

## Limits of this verification

No live SMTP message, PayPal checkout/webhook, AI request, public deployment, independent penetration test, accessibility certification or immigration legal review occurred. Clean virtual-environment installation and physical paper printing were not exercised; runtime dependencies are declared and locked. Narrow viewport override did not change the in-app browser's reported 1280px width, so mobile device validation remains outstanding. Screen-reader and low-performance-device testing remain outstanding. Latin font limitations are explicitly reported rather than silently replacing unsupported characters.

Security controls are implemented and tested within these limits; this is not a certification or a guarantee of safety, legal compliance or visa approval. Provider credentials, approved operator policies, independent content/security review and supported hosting operations remain owner release requirements. Nothing was published to GitHub or Hostinger.

## ChargeReady beginner-flow update

- Simple English only, as requested. The default form opens one question at a time. Dropdowns, custom-answer options and structured rows cover every section; 41 fields have guided controls. No choices are preselected. The 159 visa/code choices are grouped and searchable. Interview date, embassy request and information date are optional; document numbers are automatic.
- New tests cover canonical choice-to-text formatting in browser and server, save/validate round trips, legacy custom wording, invalid structured amounts/dates, ownership-share limits and pending withdrawal permission.
- AI review tests use mocked provider output. Five included reviews, atomic reservations, completed-request replay, credit return on failure, encrypted stored results, per-application isolation, top-up/refund separation and concurrent request limits passed. Refunds of a partly used pack do not reduce a newly purchased five-review allowance.
- English IR1/family and EB-2 NIW teaching examples remain separate from live applicant answers. Both have branded three-page PDF examples; existing portrait layout and handwritten private fields are retained.
- Browser verified the English family-visa choice, first-interview stage without any date/notice, restored guided selections, preparation score/rubric, practical medical-cost steps and five unused AI credits with honest unconfigured status. No real AI request or payment was made.
- The preparation score is a transparent completeness formula, not a visa risk/approval score. AI explanations and score stay outside the printed applicant-prepared fact summary.

## GitHub and domain preparation — 2026-10-17

Re-ran all 75 Python tests and both JavaScript verification scripts successfully before source upload. Reviewed the release file list for customer databases, private keys, local email previews, synced references and applicant output; these remain excluded. Added a hardened single-instance Linux service template, private production environment template and Caddy HTTPS reverse proxy for the proposed prep.particlesolidlab.com subdomain. The main Particle Solid Lab repository and DNS are not modified. Linux service/Caddy validation and real domain deployment require a provisioned server; they have not been run locally on macOS. External payment, email and AI tests remain mocked as described above.
