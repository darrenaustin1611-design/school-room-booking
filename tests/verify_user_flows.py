"""Run user journeys and Edge layout checks against an isolated demo database.

Run: python tests/verify_user_flows.py
Browser artifacts are retained in a temporary directory for visual inspection.
"""
import html
import io
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import Config


def verify():
    artifacts = Path(tempfile.mkdtemp(prefix='edureserve-ui-'))
    with tempfile.TemporaryDirectory(prefix='edureserve-flow-') as temp:
        with patch.object(Config, 'DATABASE_PATH', str(Path(temp) / 'test.db')):
            from app import app, SCHOOL_TIMEZONE
            from database import get_db, init_db
            from services.booking_service import BookingService
            app.config.update(TESTING=True)
            init_db()  # Existing schema startup must also succeed.
            pages = {}

            def login(account):
                client = app.test_client()
                response = client.post('/login', data={'email': account, 'password': 'password123'}, follow_redirects=True)
                assert response.status_code == 200 and b'Log out' in response.data, account
                return client

            anonymous = app.test_client()
            pages['login'] = anonymous.get('/login').get_data(as_text=True)
            accounts = re.findall(r"fillLogin\('([^']+)'", pages['login'])
            assert len(accounts) == 9
            for account in accounts:
                login(account)
            assert anonymous.get('/dashboard').status_code == 302
            assert anonymous.post('/api/bookings/1/start-use').status_code == 401
            student = login('252610112')
            teacher = login('teacher9@example.com')
            pic = login('teacher1@example.com')
            admin = login('admin@example.com')
            for role, client in [('student', student), ('teacher', teacher), ('admin', admin)]:
                for route in ['/dashboard', '/rooms', '/my-bookings', '/teachers']:
                    response = client.get(route, follow_redirects=True)
                    assert response.status_code == 200, (role, route)
                pages[role] = client.get('/dashboard', follow_redirects=True).get_data(as_text=True)
            assert student.get('/admin/data').status_code == 302
            assert student.post('/api/approvals/1/action', json={'action': 'APPROVE'}).status_code == 403
            assert teacher.get('/approvals').status_code == 200
            conn = get_db()
            room_id = conn.execute("SELECT id FROM rooms WHERE name LIKE '%Physics%'").fetchone()[0]
            conn.close()
            day = (datetime.now(SCHOOL_TIMEZONE) + timedelta(days=1)).date().isoformat()
            draft = dict(room_id=room_id, booking_date=day, start_time='16:00', end_time='17:00', purpose='User journey check')
            for role, client in [('student', student), ('teacher', teacher)]:
                response = client.post('/book', data=draft)
                assert response.status_code == 302 and '/my-bookings' in response.location
                conn = get_db()
                booking_id = conn.execute('SELECT MAX(id) FROM bookings').fetchone()[0]
                conn.close()
                pages[role + '-pending'] = client.get('/dashboard').get_data(as_text=True)
                assert pic.get('/approvals').status_code == 200
                pages['approvals'] = pic.get('/approvals').get_data(as_text=True)
                assert not teacher.post(f'/api/approvals/{booking_id}/action', json={'action': 'APPROVE'}).json['success']
                assert pic.post(f'/api/approvals/{booking_id}/action', json={'action': 'APPROVE'}).json['success']
                other = login('252610153')
                assert not other.post(f'/api/bookings/{booking_id}/start-use', json={}).json['success']
                assert client.post(f'/api/bookings/{booking_id}/start-use', json={}).json['success']
                assert client.post(f'/api/bookings/{booking_id}/extend', json={'extra_minutes': 30}).json['success']
                assert pic.post(f'/api/approvals/{booking_id}/action', json={'action': 'APPROVE_EXTENSION'}).json['success']
                assert BookingService.get_booking_by_id(booking_id).end_time == '17:30'
                pages[role + '-active'] = client.get('/dashboard').get_data(as_text=True)
                assert client.post(f'/api/bookings/{booking_id}/finish-use', json={}).json['success']
                assert BookingService.get_booking_by_id(booking_id).status == 'COMPLETED'
            invalid = dict(draft, start_time='16:05')
            assert student.post('/book', data=invalid).status_code == 422
            assert student.post('/book', data=draft).status_code == 302
            conn = get_db()
            booking_id = conn.execute('SELECT MAX(id) FROM bookings').fetchone()[0]
            conn.close()
            assert pic.post(f'/api/approvals/{booking_id}/action', json={'action': 'REJECT'}).json['success']
            pages['room'] = student.get(f'/rooms/{room_id}?date={day}').get_data(as_text=True)
            export = admin.get('/admin/download-excel')
            assert export.status_code == 200
            response = admin.post('/admin/upload-excel', data={'excel_file': (io.BytesIO(export.data), 'roundtrip.xlsx')}, follow_redirects=True)
            assert response.status_code == 200 and b'Synchronization complete' in response.data
            assert student.get('/logout', follow_redirects=True).status_code == 200
            assert student.get('/dashboard').status_code == 302
            print('PASS: 9 demo logins; role pages/access; student + teacher booking/approval/extension/finish; rejection; invalid times; Excel roundtrip; logout', flush=True)
            browser_checks(pages, artifacts)
    print('Browser artifacts:', artifacts)


def browser_checks(pages, artifacts):
    edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    assert edge.exists(), 'Microsoft Edge is required for visual checks'
    checks = r'''
    document.addEventListener('DOMContentLoaded', () => {
      const results = {};
      const grids = [...document.querySelectorAll('.quick-demo-grid')];
      if (grids.length) {
        results.symmetric = grids.every(g => {
          const b = [...g.children].map(e=>e.getBoundingClientRect());
          return Math.abs(b[0].width-b[1].width)<1 && Math.abs(b[0].height-b[1].height)<1
            && Math.abs(b[0].top-b[1].top)<1 && g.scrollWidth<=g.clientWidth+1;
        });
        results.buttonsFit = grids.every(g=>[...g.children].every(b=>b.scrollWidth<=b.clientWidth+1 && b.scrollHeight<=b.clientHeight+1));
        let submitted = false;
        document.querySelector('form').addEventListener('submit', e=>{e.preventDefault(); submitted=true;});
        grids[0].querySelector('button').click();
        results.demoClick = submitted && document.querySelector('#loginEmail').value === '252610112';
      }
      const hero = document.querySelector('.dashboard-hero');
      if (hero && innerWidth<=640) {
        results.heroCompact = hero.getBoundingClientRect().height < 420;
        results.actionGap = hero.lastElementChild.getBoundingClientRect().top-hero.firstElementChild.getBoundingClientRect().bottom <= 24;
      }
      const menu = document.querySelector('#mobileMenuBtn');
      if (menu && innerWidth<=960) {
        menu.click(); results.menuOpens = menu.getAttribute('aria-expanded')==='true';
        menu.click(); results.menuCloses = menu.getAttribute('aria-expanded')==='false';
      }
      const form = document.querySelector('[data-booking-form]');
      if(form) {
        const start=form.elements.start_time, end=form.elements.end_time;
        start.selectedIndex=1; start.dispatchEvent(new Event('change'));
        end.selectedIndex=1; end.dispatchEvent(new Event('change'));
        results.timeControls = !!start.value && !!end.value && start.value<end.value && document.querySelector('#booking-duration').textContent.includes('minutes');
      }
      const dir=document.querySelector('[data-room-directory]');
      if(dir) {
        const search=dir.querySelector('input[type=search]');
        search.value='Physics';search.dispatchEvent(new Event('input'));
        results.roomSearch=[...dir.querySelectorAll('[data-room-row]')].filter(r=>!r.hidden&&!r.closest('details').hidden).length===1;
        dir.querySelector('[data-clear-room-search]').click();
      }
      results.pageFits=document.documentElement.scrollWidth<=innerWidth+1;
      const out=document.createElement('pre');out.id='verification';out.hidden=true;
      out.textContent=JSON.stringify({width:innerWidth,results});document.body.append(out);
      parent.postMessage(out.textContent, '*');
    });
    '''
    for name, markup in pages.items():
        markup = re.sub(r'<link[^>]+href="https:[^"]+"[^>]*>', '', markup)
        def asset(match):
            path = ROOT / 'static' / match.group(1)
            content = path.read_text(encoding='utf-8')
            if path.suffix == '.css':
                return '<style>' + re.sub(r'^@import[^\n]*', '', content, flags=re.MULTILINE) + '</style>'
            return '<script>' + content + '</script>'
        markup = re.sub(r'<link[^>]+href="/static/([^"?]+)(?:\?[^"]*)?"[^>]*>', asset, markup)
        markup = re.sub(r'<script[^>]+src="/static/([^"?]+)(?:\?[^"]*)?"[^>]*></script>', asset, markup)
        markup = markup.replace('</body>', '<script>' + checks + '</script></body>')
        page = artifacts / (name + '.html')
        page.write_text(markup, encoding='utf-8')
        for width in (390, 640, 1024):
            # Edge has a minimum top-level window width. An iframe gives the
            # application the exact requested CSS viewport, including phones.
            wrapper = artifacts / (name + '-viewport.html')
            wrapper.write_text('<!doctype html><style>body{margin:0;background:#06150f}iframe{border:0}</style>'
                + '<script>addEventListener("message",e=>{const p=document.createElement("pre");p.id="verification";p.hidden=true;p.textContent=e.data;document.body.append(p);});</script>'
                + f'<iframe width="{width}" height="1000" src="{page.name}"></iframe>', encoding='utf-8')
            args = [str(edge), '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--force-device-scale-factor=1', '--hide-scrollbars', '--virtual-time-budget=1500', f'--user-data-dir={artifacts / "edge-profile"}', f'--window-size={width+24},1100', '--dump-dom', f'--screenshot={artifacts / (name+str(width)+".png")}', wrapper.as_uri()]
            run = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=55)
            match = re.search(r'<pre id="verification"[^>]*>(.*?)</pre>', run.stdout)
            assert match, (name, width, run.stderr[-1000:])
            result = json.loads(html.unescape(match.group(1)))
            assert result['width'] == width, result
            assert all(result['results'].values()), (name, result)
            print('PASS browser:', name, result, flush=True)


if __name__ == '__main__':
    verify()
