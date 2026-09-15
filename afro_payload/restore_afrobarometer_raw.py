#!/usr/bin/env python3
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
