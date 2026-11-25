# -*- coding: utf-8 -*-
"""Screen recorder for the video manuals: headless Chrome through playwright with a video of the page,
a caption bar, a role chip, a visible pointer and click marks drawn into the page - so the recording
reads without sound. The live server is driven as a user would, on the demo department of setup_demo.py
only (test users, test tasks).

One Rec = one person's sitting (one browser, one login). A video is several sittings joined by join().
The demo users' password comes from the environment variable SH_VM_PW - it is never written here.
"""
import http.client, json, os, shutil, subprocess, sys, time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.environ.get('SH_VM_BASE', 'http://146.255.249.126')
DB = 'steelhouse'
MANAGER, EMPLOYEE, EMPLOYEE2 = 'demo.manager', 'demo.employee', 'demo.employee2'
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get('SH_VM_WORK') or os.path.join(HERE, 'work')      # raw recordings, probe screenshots
OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'Docs', 'ვიდეო მანუალები')
FFMPEG = shutil.which('ffmpeg') or 'ffmpeg'
W, H = 1600, 900
CAP_H = 74
# trial run: SH_VM_FAST=1 - no video, the reading pauses cut short, a screenshot at every caption
FAST = bool(os.environ.get('SH_VM_FAST'))

OVERLAY = r"""
(() => {
  if (window.__mv || window.top !== window) return;
  window.__mv = true;
  const make = () => {
    if (document.getElementById('mv-cap') || !document.body) return;
    const st = document.createElement('style');
    st.textContent = `
      html,body{height:calc(100vh - 74px) !important;overflow:hidden}
      .modal,.modal-backdrop,.o_dialog > .modal{bottom:74px !important;height:auto !important}
      .o_notification_manager{display:none !important}
      .o_kanban_renderer{padding-bottom:160px !important}
      #mv-cap{position:fixed;left:0;right:0;bottom:0;height:74px;z-index:2147483000;background:#111827;color:#fff;
        font:600 21px/1.3 'Segoe UI','Sylfaen',sans-serif;padding:0 30px 0 370px;display:flex;align-items:center;justify-content:center;
        text-align:center;border-top:4px solid #f59e0b;pointer-events:none;box-sizing:border-box}
      #mv-role{position:fixed;left:18px;bottom:17px;z-index:2147483001;font:700 16px 'Segoe UI','Sylfaen',sans-serif;
        padding:8px 16px;border-radius:999px;color:#fff;background:#2563eb;pointer-events:none}
      #mv-ptr{position:fixed;z-index:2147483600;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:50%;
        background:rgba(239,68,68,.55);border:2px solid #b91c1c;pointer-events:none;left:-50px;top:-50px;transition:transform .12s}
      #mv-ptr.down{transform:scale(1.9);background:rgba(239,68,68,.25)}
      #mv-title{position:fixed;inset:0;z-index:2147483500;background:#111827;color:#fff;display:flex;flex-direction:column;
        align-items:center;justify-content:center;font-family:'Segoe UI','Sylfaen',sans-serif;text-align:center;padding:60px;pointer-events:none}
      #mv-title h1{font-size:52px;font-weight:700;margin:0 0 22px;color:#fff}
      #mv-title p{font-size:27px;color:#fbbf24;margin:0;white-space:pre-line;line-height:1.55}
      .mv-ring{outline:4px solid #f59e0b !important;outline-offset:3px;border-radius:4px}
    `;
    document.head.appendChild(st);
    for (const id of ['mv-cap', 'mv-role', 'mv-ptr']) { const d = document.createElement('div'); d.id = id; document.body.appendChild(d); }
    const s = JSON.parse(sessionStorage.getItem('mv') || '{}');
    document.getElementById('mv-cap').textContent = s.cap || '';
    document.getElementById('mv-role').textContent = s.role || '';
    document.getElementById('mv-role').style.background = s.color || '#2563eb';
    if (!s.role) document.getElementById('mv-role').style.display = 'none';
  };
  document.addEventListener('DOMContentLoaded', make); setInterval(make, 300);
  document.addEventListener('mousemove', e => { const p = document.getElementById('mv-ptr'); if (p) { p.style.left = e.clientX + 'px'; p.style.top = e.clientY + 'px'; } }, true);
  // while a card is dragged the browser sends drag events instead of mouse moves
  document.addEventListener('dragover', e => { const p = document.getElementById('mv-ptr'); if (p) { p.style.left = e.clientX + 'px'; p.style.top = e.clientY + 'px'; } }, true);
  document.addEventListener('dragend', () => { const p = document.getElementById('mv-ptr'); if (p) p.classList.remove('down'); }, true);
  document.addEventListener('mousedown', () => { const p = document.getElementById('mv-ptr'); if (p) p.classList.add('down'); }, true);
  document.addEventListener('mouseup', () => { const p = document.getElementById('mv-ptr'); if (p) setTimeout(() => p.classList.remove('down'), 250); }, true);
})();
"""


_UIDS = {}


def _call(service, method, args):
    data = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {'service': service, 'method': method, 'args': args}}).encode()
    for attempt in range(6):
        try:
            # a short connect: the line to the server drops for a few seconds now and then - a refused
            # connection is tried again (nothing reached the server, so nothing is done twice)
            conn = http.client.HTTPConnection(BASE.split('//')[1], timeout=8)
            conn.connect()
        except OSError:
            time.sleep(3)
            continue
        conn.sock.settimeout(180)
        conn.request('POST', '/jsonrpc', body=data, headers={'Content-Type': 'application/json'})
        r = json.loads(conn.getresponse().read())
        conn.close()
        if 'error' in r:
            raise RuntimeError(r['error']['data'].get('message'))
        return r.get('result')
    raise RuntimeError('the server is not reachable')


def rpc(login, model, method, args, kw=None):
    """A call as one of the demo users (the same rights as in the browser) - to prepare and check the demo tasks."""
    pw = os.environ['SH_VM_PW']
    if login not in _UIDS:
        _UIDS[login] = _call('common', 'authenticate', [DB, login, pw, {}])
    kw = dict(kw or {})
    kw.setdefault('context', {'lang': 'ka_GE', 'tz': 'Asia/Tbilisi'})
    return _call('object', 'execute_kw', [DB, _UIDS[login], pw, model, method, args, kw])


class Rec:
    def __init__(self, name, video=True):
        video = video and not FAST
        self.name, self.video = name, video
        os.makedirs(WORK, exist_ok=True)
        self.pw = sync_playwright().start()
        # playwright's own Chromium: the installed Chrome refuses the plain-http address (ERR_BLOCKED_BY_CLIENT)
        self.browser = self.pw.chromium.launch(headless=True)
        kw = {'viewport': {'width': W, 'height': H}, 'locale': 'ka-GE', 'timezone_id': 'Asia/Tbilisi', 'accept_downloads': True}
        if video:
            kw.update(record_video_dir=os.path.join(WORK, 'raw'), record_video_size={'width': W, 'height': H})
        self.ctx = self.browser.new_context(**kw)
        self.ctx.add_init_script(OVERLAY)
        self.pg = self.ctx.new_page()
        self.pg.set_default_timeout(30000)
        self.t0 = time.time()
        self.cut = 0.0
        self.n = 0

    # ---- overlay
    def _state(self, **kw):
        self.pg.evaluate("""(kw) => { const s = JSON.parse(sessionStorage.getItem('mv') || '{}'); Object.assign(s, kw);
            sessionStorage.setItem('mv', JSON.stringify(s));
            const c = document.getElementById('mv-cap'), r = document.getElementById('mv-role');
            if (c) { c.textContent = s.cap || ''; }
            if (r) { r.textContent = s.role || ''; r.style.display = s.role ? '' : 'none'; r.style.background = s.color || '#2563eb'; } }""", kw)

    def cap(self, text, wait=None):
        """A caption; stays long enough to be read (about 65 ms a character, 2.6 s at least)."""
        self._state(cap=text)
        if FAST:
            self.pg.wait_for_timeout(300)
            self.shot('cap')
            print('  cap:', text)
            return
        self.pg.wait_for_timeout(int((wait if wait is not None else max(2.6, len(text) * 0.065)) * 1000))

    def role(self, text, color='#2563eb'):
        self._state(role=text, color=color)

    def title(self, head, sub='', secs=4.0):
        self.pg.evaluate("""([h, s]) => { let d = document.getElementById('mv-title'); if (!d) { d = document.createElement('div'); d.id = 'mv-title'; document.body.appendChild(d); }
            d.innerHTML = ''; const a = document.createElement('h1'); a.textContent = h; const b = document.createElement('p'); b.textContent = s; d.append(a, b); }""", [head, sub])
        self.pg.wait_for_timeout(300 if FAST else int(secs * 1000))

    def untitle(self):
        self.pg.evaluate("() => { const d = document.getElementById('mv-title'); if (d) d.remove(); }")

    def mark_start(self):
        """Everything before this moment (the login) is cut from the video."""
        self.cut = time.time() - self.t0

    # ---- acting like a person
    def move(self, x, y):
        self.pg.mouse.move(x, y, steps=4 if FAST else 28)
        self.pg.wait_for_timeout(100 if FAST else 350)

    def point(self, loc, secs=1.2):
        loc = loc.first
        loc.scroll_into_view_if_needed()
        self.pg.wait_for_timeout(250)
        b = loc.bounding_box()
        if b['y'] + min(b['height'], 300) > H - CAP_H - 8:      # in the window, but behind the caption bar
            # the nearest scrolling box is moved (not the page itself), the element to the middle of what is seen
            loc.evaluate("""(e, lim) => {
                for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
                    if (!/(auto|scroll)/.test(getComputedStyle(p).overflowY) || p.scrollHeight <= p.clientHeight + 4) continue;
                    const r = e.getBoundingClientRect(), top = Math.max(p.getBoundingClientRect().top, 0);
                    const by = r.top + Math.min(r.height, 300) / 2 - (top + lim) / 2;
                    if (Math.abs(by) < 4) break;
                    p.scrollBy({top: by});
                }
                document.documentElement.scrollTop = 0; document.body.scrollTop = 0; }""", H - CAP_H)
            self.pg.wait_for_timeout(500)
            if FAST:
                print('  scrolled into view: y %d -> %d' % (b['y'], loc.bounding_box()['y']))
            b = loc.bounding_box()
        self.move(b['x'] + b['width'] / 2, b['y'] + min(b['height'] / 2, 200))
        loc.evaluate("e => e.classList.add('mv-ring')")
        self.pg.wait_for_timeout(150 if FAST else int(secs * 1000))
        loc.evaluate("e => e.classList.remove('mv-ring')")

    def click(self, loc, secs=0.9, after=0.9):
        loc = loc.first
        self.point(loc, secs)
        self.pg.mouse.down(); self.pg.wait_for_timeout(120); self.pg.mouse.up()
        self.pg.wait_for_timeout(int(after * 1000))

    def drag(self, loc, target, hold=1.5):
        """Drags the element to the point target() -> (x, y) of the page (asked for once the element is in
        view), slowly, and holds it there before the drop."""
        loc = loc.first
        self.point(loc, 0.7)
        b = loc.bounding_box()
        x, y = target()
        sx, sy = b['x'] + b['width'] / 2, b['y'] + min(b['height'] / 2, 200)
        self.pg.mouse.down()
        self.pg.mouse.move(sx + 14, sy + 6, steps=5)
        self.pg.mouse.move(x, y, steps=8 if FAST else 45)
        self.pg.mouse.move(x + 2, y + 1, steps=2)
        self.pg.wait_for_timeout(400 if FAST else int(hold * 1000))
        self.pg.mouse.up()
        self.pg.wait_for_timeout(600)

    def type(self, loc, text, clear=True):
        loc = loc.first
        self.point(loc, 0.5)
        loc.click()
        if clear:
            loc.press('Control+a')
        loc.type(text, delay=5 if FAST else 65)
        self.pg.wait_for_timeout(600)

    def wait(self, secs):
        """A pause for the page to settle (kept in a trial run)."""
        self.pg.wait_for_timeout(int(secs * 1000))

    def read(self, secs):
        """A pause for the viewer to look (skipped in a trial run)."""
        self.pg.wait_for_timeout(200 if FAST else int(secs * 1000))

    def shot(self, label=''):
        self.n += 1
        d = os.path.join(WORK, 'probe')
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, '%s_%02d_%s.png' % (self.name, self.n, label))
        self.pg.screenshot(path=path)
        return path

    def login(self, login, password=None):
        pg = self.pg
        for attempt in range(4):
            try:
                pg.goto(BASE + '/web/login', wait_until='load', timeout=25000)
                break
            except Exception:
                if attempt == 3:
                    raise
                pg.wait_for_timeout(3000)
        pg.fill('input[name="login"]', login)
        pg.fill('input[name="password"]', password or os.environ['SH_VM_PW'])
        pg.press('input[name="password"]', 'Enter')
        pg.wait_for_selector('.o_main_navbar, .o_action_manager', timeout=90000)
        pg.wait_for_timeout(2500)

    def goto(self, path, sel='.o_action_manager .o_view_controller, .o_action_manager .o_action', settle=2.0):
        for attempt in range(4):
            try:
                self.pg.goto(BASE + path, wait_until='load', timeout=25000)
                self.pg.wait_for_selector(sel, timeout=40000)
                break
            except Exception:
                if attempt == 3:
                    raise
                self.pg.wait_for_timeout(3000)
        self.pg.wait_for_timeout(int(settle * 1000))

    def close(self):
        """Ends the sitting; returns (raw webm path, seconds to cut from the start)."""
        path = None
        video = self.pg.video
        self.ctx.close()
        if video:
            path = video.path()
        self.browser.close(); self.pw.stop()
        return path, self.cut


def join(parts, out):
    """[(raw webm, seconds cut from the start), ...] -> one mp4 (H.264) in Docs/ვიდეო მანუალები."""
    if FAST:
        print('trial run - no video')
        return None
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, out)
    cmd = [FFMPEG, '-y', '-loglevel', 'error']
    for raw, cut in parts:
        cmd += ['-ss', '%.2f' % cut, '-i', raw]
    n = len(parts)
    flt = ''.join('[%d:v]fps=25,scale=%d:%d,setsar=1[v%d];' % (i, W, H, i) for i in range(n))
    flt += ''.join('[v%d]' % i for i in range(n)) + 'concat=n=%d:v=1:a=0[out]' % n
    cmd += ['-filter_complex', flt, '-map', '[out]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '22',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', dst]
    subprocess.run(cmd, check=True)
    for raw, _cut in parts:
        os.remove(raw)
    print('video:', dst, '| %.1f MB' % (os.path.getsize(dst) / 1e6))
    return dst
