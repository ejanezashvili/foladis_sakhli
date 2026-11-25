# -*- coding: utf-8 -*-
"""Looks at the pages before a scene is written: screenshots into work/probe, no video.
   run.ps1 probe.py <login> <path> [<path> ...]"""
import sys
from rec import Rec, rpc

login, paths = sys.argv[1], sys.argv[2:]
r = Rec('probe_' + login.replace('.', '_'), video=False)
r.login(login)
print('after login:', r.pg.url)
print(r.shot('home'))
for p in paths:
    try:
        r.goto(p, settle=3.0)
    except Exception as e:
        print('goto failed', p, str(e)[:200])
    print(p, '->', r.pg.url)
    print(r.shot(p.strip('/').replace('/', '_')[:40]))
r.close()
