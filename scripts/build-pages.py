"""Retire the old static edition; account/payment checks require the server."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ChargeReady preview retired</title><body><main><h1>The old static preview is retired</h1><p>The account-based ChargeReady application requires its server for encrypted saves, purchases and PDF access. This folder does not provide an alternative free PDF edition.</p><p>Use the local server while development continues. No new public deployment is configured.</p></main></body></html>'''
(root/'docs'/'index.html').write_text(page)
# Legacy files are intentionally absent from a generated server release; no publishing occurs here.
print('Static entry point retired. Build the server release with scripts/package-release.py.')
