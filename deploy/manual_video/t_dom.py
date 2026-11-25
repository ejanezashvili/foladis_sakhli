# -*- coding: utf-8 -*-
"""Prints DOM facts of a page: t_dom.py <login> <path> <file with a js expression returning a string>"""
import sys
from rec import Rec
r = Rec('dom', video=False)
r.login(sys.argv[1])
r.goto(sys.argv[2], 'body', 5)
print(r.pg.evaluate(open(sys.argv[3], encoding='utf-8').read()))
r.shot('dom')
r.close()
