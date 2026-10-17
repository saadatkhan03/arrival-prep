# ChargeReady — your settlement dossier

A local, account-based immigrant-visa preparation application. The free introduction covers interview basics, household and housing. Complete costs USD 5 for one application and adds detailed financial/work/insurance/budget/evidence intake, an employment application ledger, practice prompts, a personalized evidence checklist, wording assistance, saved revisions and a branded PDF. Corrections and downloads for that application are included. New applications start Free.

No GitHub or hosting publication is performed by the build or packaging scripts. The obsolete static browser edition is retired. The application requires its server; static file hosting cannot enforce paid access.

## Run locally

Use Python 3.10+ (tested with Python 3.12) and install `requirements.txt` in a private virtual environment. Run `python server.py`; it binds to 127.0.0.1:8765. For the existing local preview use `PORT=8898` and the configured private `VISA_DB_PATH`. The default database is `private/visaready.sqlite3`, never under web assets. Keep the server running while testing.

Create or recover an administrator with `python admin_setup.py` in the same environment/database configuration as the server. Password entry is interactive unless owner-provided environment variables are set. This revokes prior sessions. `VISA_RESET_MFA=yes` additionally clears administrator MFA for owner-controlled local recovery and records an audit event; there is no public MFA-reset endpoint. Use `/admin` for the private console.

`.env.example` documents optional settings; the server reads environment variables, not `.env` automatically. Do not place actual secrets, databases, original immigration documents or customer files in source control.

## Simple questions and final preparation review

The form uses simple English only, one open question at a time, choice lists with custom answers, and repeatable family/assets/debt/support rows. Existing wording is preserved. The first screen does not require an interview date, a notice, or an information date; those are optional under Interview details. The 159 visa-route/code choices are grouped and searchable; they are a code lookup rather than a legal-applicability determination. The source edition is recorded in visa-categories.json; some codes are legacy. NIW is an EB-2 route, not EB-3. Document IDs are created automatically.

The final review gives an openly defined preparation-completeness score and practical steps for missing plans/documents. It does not score approval, eligibility, wealth, age or health. Complete includes five successful AI preparation reviews per application; another five cost USD 5. Credits are reserved atomically, failures release them, request replays reuse completed results, and top-up refunds revoke unused capacity without revoking the underlying application entitlement. Ordinary rule-based preparation checks do not use AI credits. AI review results are encrypted at rest with the server key and readable by the owning account, unlike browser-encrypted applicant backups; they are erased on account closure. Full-profile AI review requires explicit consent and can disclose sensitive financial/immigration answers to the provider. No live model has been tested. Scores and AI notes are private planning tools outside the printed fact summary.

## Account and data behavior

- Session cookies are HttpOnly and SameSite Strict, Secure with HTTPS, with an 8-hour absolute and 30-minute idle expiry. Logout, password reset/change, pause and closure revoke sessions. A refreshed page shows the signed-in identity while keeping answers locked until password entry.
- Account encryption uses a random data key wrapped separately by the login password and a private recovery code. The browser encrypts dossier envelopes using AES-256-GCM and PBKDF2-SHA256 (600,000 rounds, random salt/IV). Password changes rewrap the data key rather than destroying answers. Password reset requires an emailed one-time token and the private recovery code to preserve encrypted content. Losing both the password and recovery code means those answers cannot be recovered.
- Legacy encrypted local dossiers are migrated on their next successful password-based unlock. Only fictional sample data is shipped. The read-only example view never replaces a live application.
- Saves are serialized and bound to account/application identities, with optimistic version checks. Failed saves and conflicts remain visible. Logout flushes pending work first. The latest 20 encrypted revisions per application can be restored; import/reset create new revisions.
- Validation and PDF generation process submitted plaintext on the server. Actual PDF page previews use Poppler (`pdftoppm`) in a private temporary directory removed at the end of the request; no preview is retained by the app. This is not end-to-end encryption across every operation, zero operator access, certified security or protection from a compromised device. PDFs and downloaded recovery codes are plaintext files and need careful storage.
- The PDF and application review use the shared presentation model and schema labels. Output tries 9, 8.5 and 8-point body type, fits two or three pages, and rejects overflow rather than truncating. Unsupported characters are explicitly flagged with a transliteration request. Full multilingual font/shaping support is not claimed.
- Financial calculations use decimal arithmetic, exclude incomplete conversions and future income, and identify missing evidence. They are planning calculations, not an eligibility score or approval prediction.

## External services and test mode

Local preview does not charge or send email unless providers are configured. Without SMTP, verification/reset messages are stored as owner-readable 0600 files in the database directory's `mail-preview` folder. Do not serve that folder or use this mailbox mode publicly. New accounts show unverified status; verification is enforced for production saves/checkout/export.

Configure SMTP using TLS with `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USER` and `SMTP_PASSWORD`. There are one-time expiring verification and reset links. No customer email was sent as part of the implementation tests.

PayPal configuration: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_MERCHANT_ID`, `PAYPAL_WEBHOOK_ID` and `PAYPAL_ENV` (`sandbox` by default). Server-created orders are linked to applications. Capture checks provider reference, application, USD 5 amount, currency, merchant and completed capture. Signed webhooks are verified through PayPal and event IDs processed once. Refund/dispute events revoke the corresponding entitlement. Manual reconciliation requires administrator reauthentication, a reason and a receipt/reference. Test/complimentary grants are separately identified; recording a refund does not itself send money. No real payment or PayPal sandbox account was used in testing; transport is mocked.

Official implementation references: [PayPal Orders API](https://developer.paypal.com/api/rest/integration/orders-api), [webhook verification](https://developer.paypal.com/api/rest/webhooks/rest/).

Crypto checkout remains unavailable; a Binance account or personal wallet is not treated as a verified checkout integration. Do not advertise Bitcoin acceptance until a supported provider and jurisdiction-specific business review are completed.

Optional AI uses configured `OPENAI_API_KEY` and `OPENAI_MODEL`. Availability is driven by server configuration. Users authorize each section/answer transmission. Grammar suggestions highlight differences, check protected numbers/currencies/negatives/status terms and require applicant approval. These checks do not prove semantic equivalence. `store:false` does not guarantee zero provider retention. Basic cleanup never calls a provider. AI transport tests are mocked; no live model was called.

## Admin, privacy and release limits

The console shows account/transaction metadata, current-application aggregate metrics, support tickets and audit events. It does not show raw applicant answers. Admin MFA uses time-based authenticator codes with encrypted secret storage and replay protection. MFA is mandatory for production dashboard access. Ten single-use backup codes are issued at enrollment; keep them offline separately from the encrypted-data recovery code. Dangerous operations require current password, a fresh code when MFA is enabled, and a recorded reason.

Private support tickets replace public GitHub feedback. The notice version is stored on acknowledged accounts. Account closure anonymizes identity and erases encrypted applicant records while preserving minimal transaction/audit metadata. Policy text in `/policies` is an operational draft, with operator identity, retention/refund terms and independent legal/security/content review still required before public use. No jurisdiction-wide legal compliance claim is made.

Production refuses startup unless HTTPS origin, server-secret key, SMTP and explicit owner acknowledgement of independent review are configured. This gate does not perform the review. Use a supported reverse proxy, private database volume and proper secret/backup management. The current server is a bounded localhost service, not a managed multi-instance platform. See `deploy/README.md` for domain/server templates and owner-admin setup, and `HOSTINGER_DEPLOYMENT.md` for outstanding owner/provider work. Source can be hosted on GitHub; no live domain has been deployed.

## Tests and release package

Run `python -m unittest discover -s tests -v`, `node tests/test_backup.mjs`, and `node tests/test_workspace.mjs`. Python dependencies include PDF inspection and cryptographic runtime requirements. Tests use isolated databases, mocked provider responses and synthetic profiles. HTTP tests briefly open a localhost listener.

`python scripts/package-release.py` creates `output/chargeready-local-project.zip` containing source, fonts, tests and configuration examples. It excludes private databases, secrets, mailboxes, references, historical static assets and customer output. It never publishes. `maintenance.py` backs up/restores the SQLite database using a separately held `VISA_BACKUP_KEY`, checks integrity, and refuses to overwrite an existing restore target. Preserve the separate server-secret key as well; test recovery before relying on backups.

For the owner’s budget and AI/hosting explanation, see AI_HOSTING_BUDGET.md. The IR1 family and EB-2 NIW examples are available through the paid read-only teaching-example chooser. No actual email dispatch or insurance quote is claimed by a fictional example.
