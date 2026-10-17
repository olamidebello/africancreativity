#!/usr/bin/env python3
"""Locate a dedicated active vhost without changing unrelated sites."""
import argparse,json,re
from pathlib import Path

def discover(domain,root):
    if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',domain):
        raise ValueError('Invalid DNS hostname')
    root=Path(root);allowed={domain,'www.'+domain};matches={}
    candidates=list((root/'sites-enabled').glob('*'))+list((root/'conf.d').glob('*.conf'))
    for candidate in candidates:
        if not candidate.is_file():continue
        content=re.sub(r'#.*','',candidate.read_text())
        names=[name for block in re.findall(r'\bserver_name\s+([^;]+);',content) for name in block.split()]
        if domain not in names:continue
        if any(name not in allowed for name in names):
            raise ValueError('The target hostname shares a config with other hostnames. Split its vhost before switching: '+str(candidate))
        matches[str(candidate.resolve())]=True
    if len(matches)>1:raise ValueError('Multiple active configurations match this hostname; resolve duplicates before switching')
    if matches:return {'config':next(iter(matches)),'active':True}
    dest=root/'sites-available'/domain
    if dest.exists():
        content=re.sub(r'#.*','',dest.read_text())
        names=[name for block in re.findall(r'\bserver_name\s+([^;]+);',content) for name in block.split()]
        if not names or any(name not in allowed for name in names):raise ValueError('Existing inactive config is not dedicated to this hostname')
    return {'config':str(dest.resolve()),'active':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('domain');p.add_argument('--root',default='/etc/nginx');args=p.parse_args()
    try:print(json.dumps(discover(args.domain,args.root)))
    except (ValueError,OSError) as error:raise SystemExit(str(error))
