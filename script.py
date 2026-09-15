import subprocess, sys, os, json, hashlib, base64, csv, pathlib, shutil
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'requests', 'pandas', 'pyreadstat'])
import requests, pandas as pd, pyreadstat

FILES = [
 ('KEN','R10','https://www.afrobarometer.org/wp-content/uploads/2025/06/KEN_R10.Data_28June24.wtd_.final_.release_updated.13Feb25.sav','sav'),
 ('MDG','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/MAD_R10.Data_02Dec24.wtd_.final_.release_updated.13Feb25.csv','csv'),
 ('NGA','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/NIG_R10.Data_18Nov24.wtd_.final_.release_updated.13Feb25.csv','csv'),
 ('TZA','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/TAN_R10.Data_20Sep24.wtd_.final_.release_updated.13Feb25.sav','sav'),
 ('ZMB','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/ZAM_R10.Data_27Sep24.wtd_.final_.release_updated.13Feb25.csv','csv'),
 ('ZAF','R9','https://www.afrobarometer.org/wp-content/uploads/2024/02/SAF_R9.data_.final_.wtd_release.30May23.sav','sav'),
]
EXPECTED = {
 'KEN':'6b53c17ddcd5cd5613446d2da2d8a034476bfd2c93baaf87d3e5a52d940a8ccd',
 'MDG':'e165d5d782beb9d531b1161581a6cd52698052a8b8d8cf5909d83b8e78a741da',
 'NGA':'abd2cbccb6f9739576e0c76c276672ae0ca49233b537b0c2e77a2c8d2e4dddb7',
 'TZA':'009e0807e5bfda90001277b566ea2e3e5c0ead5489fa10ecc1f8667daf17a60e',
 'ZMB':'6d4247ed626030f1663d38852a270ef5fc983c7b92397f738db7831690a2ff53',
 'ZAF':'d99670bc7c30be675ac789ee41f0034c379d333b16951ac78e2d9571a582f75b',
}
root=pathlib.Path('/tmp/afro_complete'); shutil.rmtree(root,ignore_errors=True); root.mkdir()
manifest={'format':'full respondent-level data; all rows and columns','files':[]}
for iso,rnd,url,fmt in FILES:
    print('download',iso,url)
    b=requests.get(url,timeout=180).content
    got=hashlib.sha256(b).hexdigest(); assert got==EXPECTED[iso], (iso,got)
    src=root/f'{iso}_{rnd}_official.{fmt}'; src.write_bytes(b)
    if fmt=='sav':
        raw, meta=pyreadstat.read_sav(str(src), apply_value_formats=False)
        csvname=f'{iso}_{rnd}_raw_codes.csv'
        raw.to_csv(root/csvname,index=False,lineterminator='\n')
        md={'column_labels':dict(zip(meta.column_names,meta.column_labels)), 'variable_value_labels':meta.variable_value_labels, 'missing_ranges':meta.missing_ranges}
        mdname=f'{iso}_{rnd}_sav_metadata.json'; (root/mdname).write_text(json.dumps(md,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        rows,cols=raw.shape
        src.unlink()  # archive the complete decoded respondent data + metadata; official bytes are hash-pinned in manifest
    else:
        # Preserve official CSV bytes exactly in the archive.
        csvname=f'{iso}_{rnd}_official.csv'; src.rename(root/csvname)
        df=pd.read_csv(root/csvname,low_memory=False); rows,cols=df.shape
        mdname=None
    manifest['files'].append({'iso3':iso,'round':rnd,'source_url':url,'official_sha256':got,'rows':int(rows),'columns':int(cols),'data_file':csvname,'metadata_file':mdname})
(root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')

outdir=pathlib.Path('afro_payload_ppmd'); outdir.mkdir(exist_ok=True)
for p in outdir.iterdir(): p.unlink()
ppmd=outdir/'afrobarometer_full_respondent_microdata.7z'
lzma=outdir/'afrobarometer_full_respondent_microdata_lzma.7z'
subprocess.check_call(['7z','a','-t7z','-m0=PPMd','-mx=9','-ms=on',str(ppmd),str(root/'*')])
subprocess.check_call(['7z','a','-t7z','-m0=LZMA2','-mx=9','-ms=on',str(lzma),str(root/'*')])
for p in [ppmd,lzma]: print(p,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
best=min([ppmd,lzma],key=lambda p:p.stat().st_size)
print('BEST',best,best.stat().st_size)
data=best.read_bytes(); enc=base64.b64encode(data).decode('ascii')
# split below GitHub contents inline/tool limits
chunk=180000
for i in range(0,len(enc),chunk):
    (outdir/f'payload.part{i//chunk+1:03d}.b64').write_text(enc[i:i+chunk],encoding='ascii')
(outdir/'PAYLOAD_MANIFEST.json').write_text(json.dumps({'archive_name':best.name,'archive_bytes':len(data),'archive_sha256':hashlib.sha256(data).hexdigest(),'base64_chars':len(enc),'parts':(len(enc)+chunk-1)//chunk,'source_manifest':manifest},indent=2),encoding='utf-8')
# keep only chosen binary plus text chunks/manifest
for p in [ppmd,lzma]:
    if p != best: p.unlink()
print('BASE64',len(enc),'PARTS',(len(enc)+chunk-1)//chunk)
