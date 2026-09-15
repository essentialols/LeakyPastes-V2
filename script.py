import base64, csv, hashlib, json, lzma, math, os, shutil, struct, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat

OUT = Path('afro_payload')
WORK = Path('afro_work')
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

sources = {
 'KEN_R10_2024_official.sav':'https://www.afrobarometer.org/wp-content/uploads/2025/06/KEN_R10.Data_28June24.wtd_.final_.release_updated.13Feb25.sav',
 'MDG_R10_2024_official.csv':'https://www.afrobarometer.org/wp-content/uploads/2025/11/MAD_R10.Data_02Dec24.wtd_.final_.release_updated.13Feb25.csv',
 'NGA_R10_2024_official.csv':'https://www.afrobarometer.org/wp-content/uploads/2025/11/NIG_R10.Data_18Nov24.wtd_.final_.release_updated.13Feb25.csv',
 'TZA_R10_2024_official.sav':'https://www.afrobarometer.org/wp-content/uploads/2025/11/TAN_R10.Data_20Sep24.wtd_.final_.release_updated.13Feb25.sav',
 'ZMB_R10_2024_official.csv':'https://www.afrobarometer.org/wp-content/uploads/2025/11/ZAM_R10.Data_27Sep24.wtd_.final_.release_updated.13Feb25.csv',
 'ZAF_R9_2022_official.sav':'https://www.afrobarometer.org/wp-content/uploads/2024/02/SAF_R9.data_.final_.wtd_release.30May23.sav',
}
expected = {
 'KEN_R10_2024_official.sav':'6b53c17ddcd5cd5613446d2da2d8a034476bfd2c93baaf87d3e5a52d940a8ccd',
 'MDG_R10_2024_official.csv':'e165d5d782beb9d531b1161581a6cd52698052a8b8d8cf5909d83b8e78a741da',
 'NGA_R10_2024_official.csv':'abd2cbccb6f9739576e0c76c276672ae0ca49233b537b0c2e77a2c8d2e4dddb7',
 'TZA_R10_2024_official.sav':'009e0807e5bfda90001277b566ea2e3e5c0ead5489fa10ecc1f8667daf17a60e',
 'ZMB_R10_2024_official.csv':'6d4247ed626030f1663d38852a270ef5fc983c7b92397f738db7831690a2ff53',
 'ZAF_R9_2022_official.sav':'d99670bc7c30be675ac789ee41f0034c379d333b16951ac78e2d9571a582f75b',
}

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()

def canon_sav(v):
 if pd.isna(v): return ''
 if isinstance(v,(np.integer,int)): return str(int(v))
 if isinstance(v,(np.floating,float)):
  x=float(v)
  if x.is_integer(): return str(int(x))
  return format(x,'.17g')
 return str(v)

def encode_columns(headers, rows):
 # Lossless cell-value dictionary encoding. Each column's code vector is uint16.
 n=len(rows); cols=[]
 for j,name in enumerate(headers):
  vals=[]; lookup={}; codes=np.empty(n,dtype='<u2')
  for i,row in enumerate(rows):
   v=row[j]
   if v not in lookup:
    if len(vals)>=65535: raise RuntimeError('too many unique values')
    lookup[v]=len(vals); vals.append(v)
   codes[i]=lookup[v]
  cols.append({'name':name,'dictionary':vals,'codes_b64':base64.b64encode(codes.tobytes()).decode('ascii')})
 return cols

bundle={'format':'AFROBAROMETER_RAW_COMPACT_V1','description':'Complete respondent-level cell values for all six African Digital Empires countries. Decode with restore_afrobarometer_raw.py.','datasets':[]}
manifest={'generated_utc':pd.Timestamp.utcnow().isoformat(),'files':[],'note':'KEN/MDG/NGA/TZA/ZMB use Round 10 2024. ZAF uses latest public respondent microdata located as of 2026-09-14: Round 9 2022; Round 10 2025 aggregate results exist but respondent microdata were not publicly listed.'}

for fn,url in sources.items():
 p=WORK/fn
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(req,timeout=180) as r, open(p,'wb') as f: shutil.copyfileobj(r,f)
 got=sha(p)
 if got!=expected[fn]: raise RuntimeError(f'hash mismatch {fn}: {got}')
 meta_extra={}
 if fn.endswith('.csv'):
  with open(p,'r',encoding='utf-8-sig',newline='') as f:
   allrows=list(csv.reader(f))
  headers=allrows[0]; rows=allrows[1:]
  if any(len(r)!=len(headers) for r in rows): raise RuntimeError(f'irregular CSV {fn}')
  source_representation='official_csv_exact_cell_values'
 else:
  df,meta=pyreadstat.read_sav(str(p),apply_value_formats=False)
  headers=[str(x) for x in df.columns]
  rows=[[canon_sav(v) for v in row] for row in df.itertuples(index=False,name=None)]
  source_representation='sav_raw_numeric_codes_with_labels'
  meta_extra={'column_labels':dict(zip(meta.column_names,meta.column_labels)),'variable_value_labels':meta.variable_value_labels,'missing_ranges':meta.missing_ranges}
 dataset={'official_filename':fn,'source_url':url,'official_sha256':got,'official_bytes':p.stat().st_size,'source_representation':source_representation,'rows':len(rows),'columns':len(headers),'encoded_columns':encode_columns(headers,rows)}
 if meta_extra: dataset['sav_metadata']=meta_extra
 bundle['datasets'].append(dataset)
 manifest['files'].append({'official_filename':fn,'source_url':url,'official_sha256':got,'official_bytes':p.stat().st_size,'rows':len(rows),'columns':len(headers),'source_representation':source_representation})

raw=json.dumps(bundle,ensure_ascii=False,separators=(',',':'),default=str).encode('utf-8')
compressed=lzma.compress(raw,format=lzma.FORMAT_XZ,preset=9|lzma.PRESET_EXTREME)
payload=base64.b64encode(compressed).decode('ascii')
PART=180000
parts=[payload[i:i+PART] for i in range(0,len(payload),PART)]
for old in OUT.glob('raw_bundle.part*.b64'): old.unlink()
for i,part in enumerate(parts,1): (OUT/f'raw_bundle.part{i:03d}.b64').write_text(part+'\n',encoding='ascii')
manifest.update({'bundle_json_bytes':len(raw),'bundle_xz_bytes':len(compressed),'bundle_base64_chars':len(payload),'parts':len(parts),'bundle_xz_sha256':hashlib.sha256(compressed).hexdigest()})
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
(OUT/'restore_afrobarometer_raw.py').write_text(r'''#!/usr/bin/env python3
import base64,csv,json,lzma
from pathlib import Path
import numpy as np
here=Path(__file__).resolve().parent
payload=''.join(p.read_text().strip() for p in sorted(here.glob('raw_bundle.part*.b64')))
bundle=json.loads(lzma.decompress(base64.b64decode(payload)).decode('utf-8'))
out=here/'restored'; out.mkdir(exist_ok=True)
for ds in bundle['datasets']:
 cols=ds['encoded_columns']; n=ds['rows']
 decoded=[]
 for c in cols:
  codes=np.frombuffer(base64.b64decode(c['codes_b64']),dtype='<u2')
  dictionary=c['dictionary']; decoded.append([dictionary[int(x)] for x in codes])
 fn=ds['official_filename'].replace('_official.sav','_raw_codes.csv')
 with open(out/fn,'w',encoding='utf-8',newline='') as f:
  w=csv.writer(f); w.writerow([c['name'] for c in cols]); w.writerows(zip(*decoded))
 if 'sav_metadata' in ds:
  (out/fn.replace('_raw_codes.csv','_sav_metadata.json')).write_text(json.dumps(ds['sav_metadata'],ensure_ascii=False,indent=2,default=str)+'\n')
 print(fn,n,len(cols))
''')
print(json.dumps(manifest,indent=2))
