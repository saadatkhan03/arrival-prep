# Arrival — immigrant visa reinterview preparation

Try the browser-only demo at **https://saadatkhan03.github.io/arrival-prep/**.

This public Pages edition keeps answers in the browser. It does not run the local Python server, does not send answers to an AI provider, and does not upload evidence. Use the repository's Issues tab to suggest improvements; share only fictional examples and remove personal or financial details.

A working browser application for an applicant-prepared settlement dossier. Start with a blank session, or explicitly select the fictional NIW example. No project-owner profile, NIW package, bank documents, case numbers, or credentials are distributed.

## Run

For the shareable version, open **https://saadatkhan03.github.io/arrival-prep/**. For local development, double-click `start.command`, then open **http://127.0.0.1:8765**. Keep the terminal open while using the local app.

On another computer with Python 3.10+:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python server.py
```

The local server binds only to 127.0.0.1. The Pages edition is static and intentionally omits the local Python server and AI integration.

## Use

1. Work through the 11 intake sections. Separate records cover each account, each adult and each evidence document. Record dates, sources, certainty and evidence IDs. Blank means unknown, not zero. Do not enter passport, Social Security, visa case or full account numbers.
2. Follow-ups adapt to housing, household, employment, insurance and benefits answers. Use the sidebar to revisit and correct any section. Answers remain in memory while the page is open.
3. Choose **Save & resume** to download a password-encrypted `.arrival` file. Use a unique password of at least 12 characters. To resume, select the file and enter the password. Password recovery is impossible. Saving is manual: refresh/close without a backup loses your work.
4. Review every fact and flag, then download a draft or explicitly attest and download a reviewed PDF. Changes invalidate review. Print the generated PDF on US Letter at actual size. A signature line remains for the applicant.
5. Keep evidence separately and label it using the index IDs. The app does not upload, authenticate or inspect evidence documents. “Available” and “document-supported” are applicant-reported statuses.

## Optional AI

The guided intake and deterministic PDF generation work without an AI service. Cloud AI is disabled on the public Pages edition. Do not add API keys to the browser app.

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in the server's environment, then restart. Use a model available to your OpenAI API account. Keep secrets out of source code, browser fields, shared logs and backups. The key is never sent to the browser.

The user must check a consent box for each section before asking AI. Only that section is sent; no whole dossier or source PDF is transmitted. AI returns a question and cannot modify facts, calculations or the dossier. Record any answer yourself in the relevant field. Output is advisory and may be wrong. `store:false` disables API response storage, but does not imply zero provider retention. Current reference: https://developers.openai.com/api/reference/resources/responses/methods/create

## Financial calculations

- Sum each account's applicant-declared accessible amount × USD-per-unit rate using decimal arithmetic. Account owner, balance, currency, accessible share, rate and dates/source are required to include it. Missing accounts are explicitly flagged and excluded.
- Applicant-declared accessible shares must not exceed balances. USD rate must equal 1. Joint funds should appear only once. Debt-funded amounts must be disclosed in liabilities; no claim of net worth is made.
- Monthly budget totals the nine monthly expense categories. One-time costs and protected emergency reserve are deducted from liquid funds for runway. Earnings, projected salaries, promised support and non-liquid assets are excluded.
- Runway is unavailable if any required budget input or account conversion is incomplete, or monthly costs are zero. It is a planning calculation, **not a sufficiency threshold or approval score**.
- Housing/premium inconsistencies, missing evidence references, unavailable documents and missing adult records are flagged. These checks are not exhaustive legal or financial verification.

## Exactly two pages

PDF content comes solely from validated applicant entries, deterministic arithmetic, explicit unknowns and cited preparation guidance. There is no AI summarization or invented narrative. Page 1 covers household, residence, resources and employment. Page 2 covers support, insurance, budget, benefits, evidence, gaps and attestation. The layout uses 10–8.5 pt body text and fails visibly when content cannot fit. It never truncates facts, discards evidence or adds a third page. Condense long answers while retaining material facts and reference the full underlying documents. Large/complex cases may require professional preparation beyond a two-page summary.

## Privacy and limitations

- No database, analytics, tracking, document uploads, localStorage or plaintext session persistence. The local server does process answers in RAM for validation and PDF creation. Request bodies and PDFs are not logged or stored by it.
- Encrypted backups: Web Crypto AES-256-GCM, PBKDF2-SHA256 with 600,000 iterations, a fresh 16-byte salt and 12-byte IV per save. Weak passwords and compromised/unlocked devices remain risks. Downloaded PDFs are unencrypted.
- The server checks Host, Origin and an unpredictable session token on writes; it serves only explicitly allowlisted assets. Responses are no-store with a restrictive CSP. This is a single-user local tool, not a certified secure hosted service.
- No automatic legal eligibility decision, official affiliation, approval guarantee, required-form determination, or instruction to stop public benefits. Follow the actual notice and seek qualified advice when appropriate.
- Official guidance reviewed 2026-10-16: State Department “Preventing Public Benefits Reliance” and “Visa Denials,” linked in the app and PDF. Rules and consular practices can change; recheck official instructions before use.
- NIW reference review used the dated petition brief and education/exhibit structure (package pages 29–30 and 39) to inform a generic research-professional example. Historical petition claims do not establish current employment, cash, insurance or eligibility. Personal details were not copied into the app.

## Verification

Run `python -m unittest discover -s tests -v` after installing `pypdf` for test-only PDF inspection. The 21 Python tests and six JavaScript backup checks passed. Browser checks confirmed sample loading, correction/navigation, review gating, and a downloaded two-page draft. The generated example was visually inspected on both pages. Run `node tests/test_backup.mjs` for encryption checks. Tests cover currency conversion, accessible funds, unknown-vs-zero budget behavior, inconsistent amounts, invalid inputs, evidence IDs, exactly two pages, attestation, escaping and overflow rejection. `output/fictional-example.pdf` is a synthetic test dossier, not anyone's real application.

The application has no live AI credential or production deployment configured. Treat those as explicit deployment work, not tested functionality.
