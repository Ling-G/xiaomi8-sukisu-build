#!/usr/bin/env python3
"""Clear Baidu Map, onboard, search 开锁 and open 即时达, ten rounds by default.

All taps use vt_touch.ko through vt_touch_test. Accessibility is used only
to read UI and set Unicode text. Each default round clears app data.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PACKAGE = 'com.baidu.BaiduMap'
ROOT = Path(__file__).resolve().parent


class Flow:
    def __init__(self, args):
        self.args = args
        self.adb = [args.adb] + (['-s', args.serial] if args.serial else [])
        self.out = args.batch_dir / f'round-{args.round_number:02d}'
        self.out.mkdir(parents=True, exist_ok=False)
        self.events = []
        self.sequence = 0
        self.outcome = 'failed'

    def log(self, message, **extra):
        print(message, flush=True)
        self.events.append({'time': time.strftime('%H:%M:%S'), 'message': message, **extra})
        (self.out / 'run.json').write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding='utf-8')

    def command(self, *parts, timeout=35, check=True):
        r = subprocess.run(self.adb + list(parts), capture_output=True, timeout=timeout)
        output = r.stdout.decode('utf-8', 'replace').strip()
        error = r.stderr.decode('utf-8', 'replace').strip()
        if check and r.returncode:
            raise RuntimeError(f'ADB failed ({r.returncode}): {output}\n{error}')
        return output

    def shell(self, *parts, root=False, **kwargs):
        command = shlex.join([str(p) for p in parts])
        if root:
            command = 'su -c ' + shlex.quote(command)
        return self.command('shell', command, **kwargs)

    def helper(self, *parts):
        return self.shell('env', 'CLASSPATH=/data/local/tmp/map-ui-helper.jar',
                          'app_process', '/system/bin', 'MapUiText', *parts)

    def snapshot(self):
        # Unlike uiautomator dump, this does not wait for continuously animated
        # map content to reach idle, nor reuse a stale XML on command failure.
        self.helper('--dump', '/data/local/tmp/map-auto-ui.xml')
        text = self.shell('cat', '/data/local/tmp/map-auto-ui.xml')
        root = ET.fromstring(text)
        self.sequence += 1
        (self.out / f'ui-{self.sequence:03d}.xml').write_text(text, encoding='utf-8')
        nodes = list(root.iter('node'))
        return nodes

    @staticmethod
    def label(n):
        return n.get('text', '').strip() or n.get('content-desc', '').strip()

    @staticmethod
    def bounds(n):
        values = re.findall(r'-?\d+', n.get('bounds', ''))
        if len(values) != 4:
            raise RuntimeError('No usable bounds for UI element')
        return tuple(map(int, values))

    @classmethod
    def visible(cls, n):
        try:
            l,t,r,b = cls.bounds(n)
            return 0 <= l < r <= 1080 and 0 <= t < b <= 2248
        except RuntimeError:
            return False

    def find(self, predicate, timeout=35):
        deadline = time.monotonic() + timeout
        last = []
        while time.monotonic() < deadline:
            last = self.snapshot()
            candidates = [n for n in last if self.visible(n) and predicate(n)
                          and n.get('enabled', 'true') == 'true']
            if candidates:
                return candidates[0]
            time.sleep(0.5)
        labels = [self.label(n) for n in last if self.label(n)]
        raise RuntimeError('Expected page/control not found; visible labels: ' + ' | '.join(labels)[:1600])

    def text(self, *values, **kwargs):
        return self.find(lambda n: self.label(n) in values, **kwargs)

    def tap(self, n, description):
        left, top, right, bottom = self.bounds(n)
        x, y = (left + right) // 2, (top + bottom) // 2
        if not (0 <= left < right <= 1080 and 0 <= top < bottom <= 2248):
            raise RuntimeError(f'Element outside native portrait screen: {n.attrib}')
        self.log(description, x=x, y=y, label=self.label(n))
        result = self.shell('/data/local/tmp/vt_touch_test', '--tap', x, y, 100, root=True)
        if 'PASS: one press/release completed' not in result:
            raise RuntimeError('Driver did not confirm a completed click: ' + result)
        time.sleep(0.6)

    def screenshot(self, name):
        self.shell('screencap', '-p', '/data/local/tmp/map-auto-screen.png')
        self.command('pull', '/data/local/tmp/map-auto-screen.png', str(self.out / name))

    def prepare(self):
        manifest = ROOT / 'FILES-SHA256.json'
        if manifest.exists():
            for name, digest in json.loads(manifest.read_text(encoding='utf-8')).items():
                if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
                    raise RuntimeError('Packaged file checksum mismatch: ' + name)
        self.command('get-state')
        if self.shell('uname', '-r') != '4.9.186-perf-g10af704':
            raise RuntimeError('This package is built only for kernel 4.9.186-perf-g10af704')
        if 'uid=0' not in self.shell('id', root=True):
            raise RuntimeError('Root permission is required')
        size = self.shell('wm', 'size')
        orientation = re.findall(r'SurfaceOrientation:\s*(\d+)', self.shell('dumpsys', 'input'))
        if '1080x2248' not in size or not orientation or any(v != '0' for v in orientation):
            raise RuntimeError('Keep the phone in native portrait mode (1080x2248)')
        if not self.shell('pm', 'path', PACKAGE).startswith('package:'):
            raise RuntimeError('Baidu Map is not installed')
        for name in ['vt_touch.ko', 'vt_touch_test', 'map-ui-helper.jar']:
            if not (ROOT/name).is_file():
                raise RuntimeError('Missing packaged file: ' + name)
            self.command('push', str(ROOT/name), '/data/local/tmp/'+name)
        self.shell('chmod', '700', '/data/local/tmp/vt_touch_test', root=True)
        version = self.shell('cat', '/sys/module/vt_touch/version', root=True, check=False)
        if version and version != '0.2':
            self.shell('rmmod', 'vt_touch', root=True)
        if version != '0.2':
            self.shell('insmod', '/data/local/tmp/vt_touch.ko', root=True)
        result = self.shell('/data/local/tmp/vt_touch_test', '--selftest', root=True)
        if 'PASS:' not in result:
            raise RuntimeError('Touch selftest failed: ' + result)
        self.log('点击驱动已就绪（vt_touch 0.2）')

    def onboard(self):
        self.tap(self.text('同意'), '同意服务协议')
        # Only the foreground location choice is accepted; never select always.
        self.tap(self.find(lambda n: n.get('resource-id', '').endswith('/permission_allow_foreground_only_button')
                           or self.label(n) in ('仅在使用中允许', '仅在使用该应用时允许')),
                 '仅在使用中允许定位')
        self.tap(self.text('暂不开启'), '暂不开启个性化行程')
        # Verify that the privacy dialog actually disappears before continuing.
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            nodes = self.snapshot()
            if not any(self.label(n) == '暂不开启' for n in nodes):
                return
            time.sleep(0.5)
        raise RuntimeError('暂不开启 was clicked but the dialog did not disappear')

    def search(self):
        def search_box(n):
            if n.get('package') != PACKAGE:
                return False
            resource = n.get('resource-id', '').lower()
            label = self.label(n)
            l,t,r,b = self.bounds(n)
            return (t < b <= 350 and r-l > 250 and
                    ('search' in resource or '搜索' in label or 'EditText' in n.get('class', '')))
        self.tap(self.find(search_box), '打开顶部搜索框')
        self.find(lambda n: n.get('editable') == 'true' or n.get('class', '').endswith('EditText'))
        result = self.helper(base64.b64encode('开锁'.encode()).decode())
        if 'PASS:' not in result:
            raise RuntimeError('Unicode input failed: ' + result)
        self.log('已输入“开锁”')
        self.find(lambda n: self.label(n) == '开锁' and
                  (n.get('editable') == 'true' or n.get('class', '').endswith('EditText')))
        self.tap(self.text('搜索'), '提交开锁搜索')

    def select_result(self):
        # Only inspect the first result screen. Do not scroll, expand more
        # results, change the query or click an off-screen accessibility node.
        deadline = time.monotonic() + 45
        while True:
            nodes = self.snapshot()
            names = [self.label(n) for n in nodes if self.visible(n)]
            list_ready = any(self.label(n) == '检索列表页' for n in nodes)
            content_ready = any('开锁' in name and 3 <= len(name) <= 80 for name in names)
            empty_result = any('没有找到相关' in name or '未找到相关' in name for name in names)
            if list_ready and (content_ready or empty_result):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('搜索结果尚未加载完成，不能判断是否找到')
            time.sleep(0.5)
        matches = [n for n in nodes if self.visible(n) and
                   self.args.target in self.label(n).replace(' ', '') and
                   len(self.label(n)) <= 80 and
                   not n.get('class', '').endswith('EditText')]
        exact = [n for n in matches if self.label(n).strip() == self.args.target]
        if exact:
            matches = exact
        distinct = {(self.label(n), n.get('bounds')) for n in matches}
        if len(distinct) > 1:
            raise RuntimeError('Multiple matching entries are visible; specify the intended branch/address')
        self.screenshot('first-screen.png')
        if not matches:
            self.outcome = 'not_found'
            self.log('LOG 没有找到', outcome='not_found', scope='first_screen_only')
            return
        self.tap(matches[0], '点击搜索结果“'+self.args.target+'”')
        time.sleep(2)
        detail = self.snapshot()
        names = [self.label(n) for n in detail if self.visible(n)]
        if not any(self.args.target in x for x in names):
            raise RuntimeError('Target name not present after clicking')
        if not any(x in ('到这去', '去这里', '导航', '电话', '路线', '收藏', '详情') for x in names):
            raise RuntimeError('Target detail controls not confirmed')
        if '检索列表页' in names:
            raise RuntimeError('Still on the result list after clicking the target')
        self.screenshot('success.png')
        self.outcome = 'opened'
        self.log('完成：已打开'+self.args.target, outcome='opened', scope='first_screen_only')

    def run(self):
        self.prepare()
        if self.args.resume == 'none':
            self.log('清除百度地图全部应用数据和缓存')
            result = self.shell('pm', 'clear', '--user', '0', PACKAGE, root=True)
            if result != 'Success':
                raise RuntimeError('Application data clear failed: ' + result)
            self.log('全部应用数据和缓存已清除')
            self.shell('monkey', '-p', PACKAGE, '-c', 'android.intent.category.LAUNCHER', '1')
            self.onboard()
        if self.args.resume != 'results':
            self.search()
        self.select_result()


def main():
    parser = argparse.ArgumentParser(description='循环清空百度地图、首次启动、搜索开锁并在第一屏打开即时达。默认10轮，每轮删除全部应用数据。')
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial')
    parser.add_argument('--target', default='即时达', help='搜索结果店名关键词，默认即时达（可匹配郑州即时达等完整店名）')
    parser.add_argument('--rounds', type=int, default=10, help='完整循环次数，默认10')
    parser.add_argument('--resume', choices=['none', 'search', 'results'], default='none',
                        help='none=清除数据并全程运行；search/results=从当前页面继续，不清除数据')
    args = parser.parse_args()
    if not 1 <= args.rounds <= 100:
        parser.error('--rounds must be between 1 and 100')
    if args.resume != 'none' and args.rounds != 1:
        parser.error('Resume mode requires --rounds 1; loops must clear data each round')
    if not args.target.strip():
        parser.error('--target cannot be empty')
    args.batch_dir = ROOT / 'runs' / ('batch-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns()%1000000))
    args.batch_dir.mkdir(parents=True, exist_ok=False)
    results = []
    for index in range(1, args.rounds+1):
        args.round_number = index
        print(f'\n===== 第 {index}/{args.rounds} 轮：目标 {args.target} =====', flush=True)
        flow = Flow(args)
        started = time.monotonic()
        try:
            flow.run()
        except KeyboardInterrupt:
            flow.log('用户中止测试', outcome='interrupted')
            flow.outcome = 'interrupted'
        except Exception as e:
            flow.log('失败：'+str(e), outcome='failed')
            try: flow.screenshot('failure.png')
            except Exception: pass
        results.append({'round': index, 'outcome': flow.outcome,
                        'seconds': round(time.monotonic()-started, 2), 'log_directory': flow.out.name})
        counts = {key: sum(r['outcome'] == key for r in results)
                  for key in ['opened','not_found','failed','interrupted']}
        summary = {'target': args.target, 'query': '开锁', 'scope': 'first_screen_only',
                   'requested_rounds': args.rounds, 'completed_rounds': len(results),
                   'counts': counts, 'rounds': results}
        (args.batch_dir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        text = f"已执行 {len(results)}/{args.rounds} 轮：找到 {counts['opened']}，未找到 {counts['not_found']}，失败 {counts['failed']}，中止 {counts['interrupted']}"
        (args.batch_dir/'summary.txt').write_text(text+'\n',encoding='utf-8')
        print(text, flush=True)
        if flow.outcome == 'interrupted':
            break
    print('日志：'+str(args.batch_dir), flush=True)
    return 1 if counts['failed'] or counts['interrupted'] else 0


if __name__ == '__main__':
    sys.exit(main())
