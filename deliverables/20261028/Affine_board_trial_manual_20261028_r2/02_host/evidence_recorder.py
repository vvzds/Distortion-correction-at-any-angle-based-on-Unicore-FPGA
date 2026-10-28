"""Bounded asynchronous image/video evidence writer; never owns the UART."""
from collections import deque
import csv
import hashlib
import json
from pathlib import Path
import threading
import time

import cv2


class EvidenceRecorder:
    def __init__(self, journal, video=True):
        self.journal = journal
        self.directory = journal.directory
        (self.directory / 'images').mkdir(exist_ok=True)
        self.condition = threading.Condition()
        self.queue = deque()
        self.stopping = False
        self.counter = 0
        self.dropped = 0
        self.errors = 0
        self.video_requested = video
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _enqueue(self, job, important=False):
        with self.condition:
            if self.stopping:
                return False
            if len(self.queue) >= 16:
                victim = next((i for i, item in enumerate(self.queue) if item['kind'] == 'video'), None)
                if important and victim is not None:
                    del self.queue[victim]
                else:
                    self.dropped += 1
                    self.journal.event('recording_drop', kind_dropped=job['kind'], total=self.dropped)
                    return False
                self.dropped += 1
                self.journal.event('recording_drop', kind_dropped='video', total=self.dropped)
            self.queue.append(job)
            self.condition.notify()
            return True

    def snapshot(self, frame, metadata, role, name=None):
        self.counter += 1
        name = name or ('images/%05d_%s_f%07d.png' % (self.counter, role, metadata['frame']))
        queued = self._enqueue(dict(kind='image', frame=frame.copy(), metadata=dict(metadata),
                                    role=role, name=name), important=True)
        self.journal.event('image_requested', file=name, role=role, queued=queued, **metadata)
        return name if queued else None

    def video(self, preview, metadata):
        if self.video_requested:
            self._enqueue(dict(kind='video', frame=preview.copy(), metadata=dict(metadata)))

    def _run(self):
        video = None
        video_failed = False
        count = 0
        image_csv = video_csv = None
        try:
            image_csv = (self.directory / 'images.csv').open('w', encoding='utf-8-sig', newline='')
            video_csv = (self.directory / 'video_frames.csv').open('w', encoding='utf-8-sig', newline='')
            columns = ('file', 'role', 'frame', 'decoded_monotonic', 'generation', 'anchor',
                       'command_seq', 'state', 'sha256')
            images = csv.DictWriter(image_csv, fieldnames=columns, extrasaction='ignore')
            images.writeheader()
            frames = csv.writer(video_csv)
            frames.writerow(('video_index', 'frame', 'decoded_monotonic', 'generation',
                             'anchor', 'command_seq', 'state'))
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.queue or self.stopping)
                    if not self.queue:
                        break
                    job = self.queue.popleft()
                try:
                    metadata = job['metadata']
                    if job['kind'] == 'image':
                        ok, encoded = cv2.imencode('.png', job['frame'], [cv2.IMWRITE_PNG_COMPRESSION, 2])
                        if not ok:
                            raise OSError('PNG encoding failed')
                        payload = encoded.tobytes()
                        path = self.directory / job['name']
                        path.write_bytes(payload)
                        digest = hashlib.sha256(payload).hexdigest()
                        sidecar = dict(file=job['name'], role=job['role'], sha256=digest,
                                       saved_monotonic=time.monotonic(), matrix_applied_ack=False, **metadata)
                        path.with_suffix('.json').write_text(json.dumps(sidecar, ensure_ascii=False,
                                                                       indent=2), encoding='utf-8')
                        images.writerow(sidecar)
                        image_csv.flush()
                        self.journal.event('image_saved', **sidecar)
                    elif not video_failed:
                        if video is None:
                            video = cv2.VideoWriter(str(self.directory / 'preview.avi'),
                                                    cv2.VideoWriter_fourcc(*'MJPG'), 10., (960, 540))
                            if not video.isOpened():
                                raise OSError('MJPG AVI unavailable; raw screenshots remain enabled')
                            self.journal.event('video_open', file='preview.avi', nominal_fps=10,
                                               actual_timestamps='video_frames.csv', physical_latency=False)
                        video.write(job['frame'])
                        frames.writerow((count,) + tuple(metadata.get(key) for key in (
                            'frame', 'decoded_monotonic', 'generation', 'anchor', 'command_seq', 'state')))
                        count += 1
                        if count % 10 == 0:
                            video_csv.flush()
                except Exception as exc:
                    self.errors += 1
                    if job['kind'] == 'video':
                        video_failed = True
                    self.journal.event('recording_error', operation=job['kind'], message=str(exc))
                    print('RECORDING ERROR:', exc, flush=True)
        except Exception as exc:
            self.errors += 1
            self.journal.event('recording_error', operation='recorder_start', message=str(exc))
            print('RECORDING ERROR:', exc, flush=True)
        finally:
            if video is not None:
                video.release()
            for handle in (image_csv, video_csv):
                if handle is not None:
                    handle.close()
            self.journal.event('recording_end', video_frames=count, dropped=self.dropped, errors=self.errors)

    def close(self):
        with self.condition:
            self.stopping = True
            self.condition.notify_all()
        self.thread.join(timeout=5.)
        if self.thread.is_alive():
            self.journal.event('recording_incomplete', queued=len(self.queue), reason='disk_close_timeout')


def summarise_session(directory):
    """Generate a plain-language review and compact decision CSV on exit."""
    from collections import Counter
    events = []
    parse_errors = 0
    for line in (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            parse_errors += 1
    counts = Counter(e['kind'] for e in events)
    observations = [e for e in events if e['kind'] == 'observation']
    reasons = Counter(e.get('rejection') for e in observations if e.get('rejection'))
    with (directory / 'observations.csv').open('w', encoding='utf-8-sig', newline='') as output:
        keys = ('time', 'frame', 'generation', 'command_seq', 'estimate_ms', 'decoded_age_ms',
                'method', 'matches', 'inliers', 'inlier_ratio', 'reprojection_rms_px', 'ecc_result', 'rejection')
        writer = csv.DictWriter(output, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        for entry in observations:
            writer.writerow(dict(entry, **(entry.get('quality') or {})))
    start = next((e for e in events if e['kind'] == 'session_start'), {})
    rows = ['# 本次会话摘要', '',
            '模式：%s；版本：%s。' % (start.get('mode'), start.get('package_version')), '',
            '- 发出补偿矩阵：%d次；不是应用或显示确认。' % counts['matrix_sent'],
            '- 观察：%d次；本帧不更新：%d次。' % (len(observations), sum(reasons.values())),
            '- 人工操作：%d次；参考锚定：%d次。' % (counts['manual_action'], counts['anchor']),
            '- 原图保存成功：%d张；保存失败：%d次；记录丢弃：%d次。' % (
                counts['image_saved'], counts['recording_error'], counts['recording_drop']),
            '- 运行错误：%d次；日志损坏行：%d。' % (counts['error'], parse_errors), '',
            '图像质量不足时保持上一组参数并继续尝试；不会因连续失败自动关闭仿射。', '',
            'preview.avi是960×540观察录像，播放速度为名义10fps；真实PC解码时刻见video_frames.csv。',
            '原始1920×1080图在images目录及reference文件中；images.csv列出角色、帧和命令序号。',
            'command_seq仅是上位机发送序号；不是FPGA已应用确认。截图后的关闭标签也不等于应用ACK。', '',
            '## 本帧未更新的原因', '']
    rows.extend('- %s：%d次' % (reason, count) for reason, count in reasons.most_common())
    rows += ['', '## 人工操作时间线', '', '| 时间 | 按键/动作 | 参考编号 |', '| --- | --- | --- |']
    for event in events:
        if event['kind'] == 'manual_action':
            rows.append('| %s | %s | %s |' % (event['time'], event.get('action'), event.get('anchor')))
    (directory / '会话摘要.md').write_text('\n'.join(rows) + '\n', encoding='utf-8')
