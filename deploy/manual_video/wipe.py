# -*- coding: utf-8 -*-
"""Empties the demo board: every demo task and template (as the demo users themselves).  run.ps1 wipe.py"""
import scenes as s
from rec import rpc, MANAGER
s.wipe()
print('left on the demo board:', rpc(MANAGER, 'project.task', 'search_count', [['|', ('project_id', '=', s.project()), ('create_uid', '=', s.uid(MANAGER))]], s.ALL))
