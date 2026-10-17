"""Package application source and assets, excluding secrets/customer/reference data. Never publishes."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1];out=root/'output'/'chargeready-local-project.zip';out.parent.mkdir(exist_ok=True)
files=['start.command','VERIFICATION.md','package.json','package-lock.json','server.py','review_engine.py','visa-categories.json','maintenance.py','auth_store.py','services.py','model.py','pdfgen.py','schema.json','sample-profile.json','sample-family-profile.json','admin_setup.py','requirements.txt','requirements-lock.txt','requirements-dev.txt','README.md','AI_HOSTING_BUDGET.md','HOSTINGER_DEPLOYMENT.md','PRODUCT_PLANS.md','.env.example']
for directory in ('public','fonts','tests','scripts','deploy'):
 files += [str(p.relative_to(root)) for p in (root/directory).rglob('*') if p.is_file() and p.name != 'production.env' and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.sqlite3','.key')]
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for name in sorted(set(files)):z.write(root/name,'chargeready/'+name)
print(out)
