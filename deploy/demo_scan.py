"""List xml ids declared in the demo files of installed modules (prints module.name per line)."""
import ast, csv, os, sys
import xml.etree.ElementTree as ET
ADDONS = ['/usr/lib/python3/dist-packages/odoo/addons', '/opt/odoo/custom-addons']
mods = sys.argv[1].split(',')
out = set()
for m in mods:
    path = next((os.path.join(a, m) for a in ADDONS if os.path.isfile(os.path.join(a, m, '__manifest__.py'))), None)
    if not path:
        continue
    man = ast.literal_eval(open(os.path.join(path, '__manifest__.py')).read())
    for f in man.get('demo', []):
        fp = os.path.join(path, f)
        if not os.path.isfile(fp):
            continue
        if fp.endswith('.xml'):
            for el in ET.parse(fp).iter():
                if el.tag in ('record', 'template', 'menuitem') and el.get('id'):
                    i = el.get('id')
                    out.add(i if '.' in i else f'{m}.{i}')
        elif fp.endswith('.csv'):
            model = os.path.basename(fp)[:-4]
            for row in csv.DictReader(open(fp, encoding='utf-8')):
                i = row.get('id')
                if i:
                    out.add(i if '.' in i else f'{m}.{i}')
print('\n'.join(sorted(out)))
