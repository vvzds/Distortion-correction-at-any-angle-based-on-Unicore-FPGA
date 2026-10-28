"""Hardware-free checks of wire format and actual destination-to-source sampling."""
import contextlib
import io
import json
import platform
import struct
import sys
import time
import threading
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import serial
import board_trial as board
import uart_tool as uart
from tracking_engine import (RegistrationEstimator, EstimationWorker, ObservationError,
                             validate_geometry, match_quality, result_rejection)


def texture():
    rng = np.random.default_rng(20261027)
    image = rng.integers(0, 256, (540, 960), dtype=np.uint8)
    image = cv2.GaussianBlur(image, (7, 7), 1.5)
    for _ in range(200):
        x, y = rng.integers([25, 25], [935, 515])
        cv2.circle(image, (int(x), int(y)), int(rng.integers(3, 15)), int(rng.integers(0, 256)), -1)
    return image


def sampling(image, matrix):
    return cv2.warpAffine(image, matrix[:2], (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)


def render(image, matrix):
    return cv2.warpAffine(image, matrix[:2], (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_LINEAR)


def visible_from_command(matrix):
    return board.FLIP @ np.linalg.inv(matrix) @ board.FLIP


def point_error(a, b):
    points = np.array([[50., 910., 910., 50., 480.], [50., 50., 490., 490., 270.], [1., 1., 1., 1., 1.]])
    return float(np.linalg.norm(((a - b) @ points)[:2], axis=0).max())


def check_direction():
    ref = texture()
    known = np.array([[1., 0., 12.], [0., 1., -8.], [0., 0., 1.]])
    # No INVERSE_MAP here: source features move by known, so compensation
    # must sample current(known*p), not current(inv(known)*p).
    cur = cv2.warpAffine(ref, known[:2], (960, 540))
    estimate, confidence = board.estimate_sampling_delta(ref, cur, .25)
    assert estimate is not None and confidence > .9
    error = point_error(estimate, known)
    recovered = sampling(cur, estimate)
    roi = np.s_[40:-40, 40:-40]
    before = float(np.abs(cur[roi].astype(float) - ref[roi]).mean())
    after = float(np.abs(recovered[roi].astype(float) - ref[roi]).mean())
    assert error < .7 and after < before * .15, (error, before, after)
    return dict(max_point_error_px=error, image_mae_before=before, image_mae_after=after,
                confidence=confidence)


def check_composition():
    ref = texture()
    physical = board.homogeneous(cv2.getRotationMatrix2D((480., 270.), -2., 1.))
    physical[:2, 2] += [6., -4.]
    previous = board.homogeneous(cv2.getRotationMatrix2D((480., 270.), 1., 1.))
    previous[:2, 2] += [-3., 5.]
    start = point_error(visible_from_command(previous) @ physical, board.IDENTITY)
    for _ in range(6):
        cur = render(ref, visible_from_command(previous) @ physical)
        delta, confidence = board.estimate_sampling_delta(ref, cur, .25)
        assert delta is not None and confidence > .8
        candidate = board.propose(previous, delta, .5)
        board.check_candidate(candidate)
        _, previous = board.quantized_command(candidate)
    end = point_error(visible_from_command(previous) @ physical, board.IDENTITY)
    assert end < .8 and end < start * .15, (start, end)
    return dict(initial_max_point_error_px=start, final_max_point_error_px=end, iterations=6)


def check_step_controller():
    target = board.homogeneous(cv2.getRotationMatrix2D((960., 540.), 12., 1.))
    target[:2, 2] += [260., -180.]
    candidate, fraction = board.propose(board.IDENTITY, target, .7, 1.25, 40., report=True)
    angle = abs(float(np.rad2deg(np.arctan2(candidate[1, 0], candidate[0, 0]))))
    displacement = float(np.linalg.norm(candidate[:2, 2]))
    assert 0 < fraction < 1 and angle <= 1.3 and displacement <= 40.1
    board.check_candidate(candidate)
    return dict(step_fraction=fraction, rotation_step_deg=angle,
                translation_step_px=displacement)


def check_raw_and_quality():
    for matrix in (np.diag([-1., -1., 1.]), np.diag([2., .5, 1.]),
                   np.array([[1., 0., 9000.], [0., 1., 0.], [0., 0., 1.]])):
        try:
            board.propose(board.IDENTITY, matrix, .01, 1.25, 40.)
        except ValueError:
            pass
        else:
            raise AssertionError('Bad raw geometry hidden by a small step')
    src = np.float32([[x, y] for x in (80., 300., 600., 880.) for y in (60., 260., 470.)])
    dst = src + [12., -8.]
    matrix = np.array([[1., 0., 12.], [0., 1., -8.]])
    good = match_quality(src, dst, np.ones(len(src)), matrix, (540, 960))
    for inliers, observed in ((np.r_[np.ones(4), np.zeros(8)], dst),
                              (np.ones(12), dst + 20.)):
        try:
            match_quality(src, observed, inliers, matrix, (540, 960))
        except ObservationError:
            pass
        else:
            raise AssertionError('Bad feature quality accepted')
    return dict(raw_rejection='PASS', good_inliers=good['inliers'], mismatched_features='rejected')


def check_polar_and_corners():
    for angle in (5., 15.):
        initial = board.rotation(8.)
        candidate = board.propose(initial, board.rotation(angle), .6, 1.25, 40.)
        assert np.allclose(np.linalg.svd(candidate[:2, :2], compute_uv=False), [1., 1.], atol=1e-9)
        corners = np.array([[0., 1919., 0., 1919.], [0., 0., 1079., 1079.], [1., 1., 1., 1.]])
        assert np.linalg.norm(((candidate-initial) @ corners)[:2], axis=0).max() <= 60.0001
    return dict(pure_rotation_scale='preserved', final_corner_limit='PASS')


def check_cache_and_freshness():
    ref = texture()
    current = cv2.warpAffine(ref, np.float32([[1, 0, 12], [0, 1, -8]]), (960, 540))
    estimator = RegistrationEstimator()
    job = dict(generation=1, reference=ref, gray=current, scale=.25, budget=2., confidence_min=.65)
    for _ in range(2):
        result = estimator.estimate(job, lambda: False)
        assert point_error(result['delta'], np.array([[1.,0.,12.],[0.,1.,-8.],[0.,0.,1.]])) < .7
    assert estimator.estimate(job, lambda: False)['quality']['reference_cache_builds'] == 1
    assert estimator.cache_builds == 1
    large_error = []
    for angle in (-12., 12.):
        target = board.homogeneous(cv2.getRotationMatrix2D((480.,270.), angle, 1.))
        target[:2,2] += [80.,-40.]
        moved = cv2.warpAffine(ref, target[:2], (960,540))
        value = estimator.estimate(dict(job, generation=int(angle+20), gray=moved), lambda: False)
        large_error.append(point_error(value['delta'],target))
        assert value['quality']['inlier_ratio'] > .55 and value['quality']['overlap'] > .75
    assert max(large_error) < 1.
    try:
        estimator.estimate(dict(job, budget=0.), lambda: False)
    except ObservationError as exc:
        assert 'budget' in str(exc)
    else:
        raise AssertionError('Budget was ignored')
    observation = dict(generation=1, captured_monotonic=10., started_monotonic=10.,
                       finished_monotonic=10.1)
    assert result_rejection(observation, 1, 10.2, 9., .45, .25) is None
    assert result_rejection(observation, 2, 10.2, 9., .45, .25) == 'obsolete_anchor'
    assert result_rejection(observation, 1, 10.6, 9., .45, .25) == 'stale_decoded_frame'
    assert result_rejection(observation, 1, 10.2, 10.1, .45, .25) == 'before_settle_deadline'
    assert result_rejection(dict(observation, finished_monotonic=10.3), 1, 10.3, 9., .45, .25) == 'estimation_budget_exceeded'
    return dict(reference_cache_builds=estimator.cache_builds, stale_results='rejected',
                budget='enforced', large_rotation_max_point_error_px=max(large_error))


def check_worker_cancellation():
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    class SlowEstimator:
        def estimate(self, job, cancelled):
            entered.set()
            assert release.wait(2.)
            finished.set()
            return dict(delta=np.eye(3), confidence=.99)
    worker = EstimationWorker(SlowEstimator())
    job = dict(generation=1, frame=1, stamp=time.monotonic(), sent_matrix=np.eye(3))
    try:
        assert worker.submit(job) and entered.wait(2.)
        assert not worker.submit(dict(job, frame=2))  # no queue behind slow work
        worker.invalidate()  # same invalidation as D/R/Q
        release.set()
        assert finished.wait(2.)
        deadline = time.monotonic() + 2.
        while worker.busy and time.monotonic() < deadline:
            time.sleep(.001)
        assert not worker.busy and worker.poll() is None
        assert worker.submit(dict(job, generation=2, frame=3))
        result = None
        deadline = time.monotonic() + 2.
        while result is None and time.monotonic() < deadline:
            result = worker.poll()
            time.sleep(.001)
        assert result is not None and result['generation'] == 2
    finally:
        release.set()
        worker.close()
    return dict(no_backlog='PASS', invalidated_result='discarded', next_anchor='accepted')


def check_camera_controls_with_blocked_estimator():
    entered, release = threading.Event(), threading.Event()
    class SlowEstimator:
        def estimate(self, job, cancelled):
            entered.set()
            release.wait(3.)
            return dict(delta=np.eye(3), confidence=.99)
    class FakeCamera:
        def __init__(self, index):
            self.sequence = 0
            self.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        def get(self):
            self.sequence += 1
            return self.sequence, time.monotonic(), self.frame
        def close(self):
            pass
    journal, connection = MemoryJournal(), MockSerial()
    journal.directory = Path('.')
    saved = []
    state = dict(disabled=False, reanchored=False)
    started = time.monotonic()
    def keyboard(_):
        time.sleep(.002)
        if time.monotonic() - started > 2.5:
            raise AssertionError('Control integration timed out')
        if (entered.is_set() and not state['disabled'] and
                any(e['kind']=='observation_timeout' for e in journal.entries)):
            assert connection.commands==[]  # watchdog holds last state, never sends affine-off
            state['disabled'] = True
            return ord('d')
        if state['disabled'] and not state['reanchored']:
            state['reanchored'] = True
            return ord('r')
        if sum(e['kind'] == 'anchor' for e in journal.entries) >= 2:
            release.set()
            return ord('q')
        return 255
    args = board.parser().parse_args(['track', '--port', 'MOCK', '--estimate-budget', '0.1',
                                      '--max-frame-age', '0.3'])
    factory = EstimationWorker
    with patch.object(board, 'LatestCamera', FakeCamera), \
         patch.object(board, 'EstimationWorker', lambda: factory(SlowEstimator())), \
         patch.object(board.cv2, 'imshow'), patch.object(board.cv2, 'waitKey', keyboard), \
         patch.object(board.cv2, 'getWindowProperty', return_value=1), \
         patch.object(board.cv2, 'destroyAllWindows'), \
         patch.object(board, 'EvidenceRecorder', lambda journal, video: FakeRecorder(journal)):
        try:
            board.run_camera(args, connection, journal)
        finally:
            release.set()
    anchors = [e['file'] for e in journal.entries if e['kind'] == 'anchor']
    assert anchors == ['reference_001.png', 'reference_002.png']
    assert state['disabled'] and state['reanchored']
    assert not any(e['kind'] == 'matrix_sent' for e in journal.entries)
    assert connection.commands == [2, 2]  # D and R, both affine-off
    return dict(controls_during_blocked_estimate='PASS', watchdog_no_affine_off='PASS', distinct_anchors=anchors,
                stale_matrix_writes=0)


def check_default_response():
    args=board.parser().parse_args(['track','--port','MOCK'])
    counts=[]
    for degrees in (5.,12.,25.):
        physical=board.rotation(degrees)
        record={'input_deg':degrees}
        for name,gain,rot,shift,corner in (
                ('previous_conservative',.4,1.25,40.,60.),
                ('new_default',args.gain,args.max_rot_step,args.max_shift_step,args.max_corner_step)):
            command=np.eye(3)
            for step in range(1,101):
                residual=visible_from_command(command)@physical
                proposed=board.propose(command,residual,gain,rot,shift,max_corner_step=corner)
                board.check_candidate(proposed)
                _,command=board.quantized_command(proposed)
                residual=visible_from_command(command)@physical
                angle=abs(np.degrees(np.arctan2(residual[1,0],residual[0,0])))
                if angle<=.2:
                    record[name]=step
                    break
            else:
                raise AssertionError('Idealized pure-roll controller failed to converge')
        assert record['new_default']<record['previous_conservative']
        counts.append(record)
    return dict(model='ideal geometry only, no estimator/capture/delay',
                residual_threshold_deg=.2,steps=counts)


class FakeRecorder:
    errors = dropped = 0
    def __init__(self, journal, video=True):
        self.journal = journal
        self.count = 0
    def snapshot(self, frame, metadata, role, name=None):
        self.count += 1
        return name or 'images/mock_%d.png' % self.count
    def video(self, display, metadata):
        pass
    def close(self):
        pass


def check_manual_retry_and_resume():
    class FakeCamera:
        def __init__(self, index):
            self.sequence = 0
            self.frame = np.zeros((1080,1920,3),np.uint8)
        def get(self):
            self.sequence += 1
            return self.sequence,time.monotonic(),self.frame
        def close(self):
            pass
    class RejectThenAccept:
        def __init__(self):
            self.count = 0
        def estimate(self, job, cancelled):
            self.count += 1
            if self.count <= 8:
                raise ObservationError('blur_or_handshake', 'test', {'inliers': 0})
            return dict(delta=board.rotation(5.), confidence=.70, quality={'method':'test'})
    journal, connection = MemoryJournal(), MockSerial()
    journal.directory = Path('.')
    state = dict(disabled=False, resumed=False, reanchored=False)
    original_anchor = None
    started = time.monotonic()
    def keyboard(_):
        nonlocal original_anchor
        time.sleep(.002)
        if time.monotonic()-started > 4.:
            raise AssertionError('Manual retry integration timed out')
        matrices = [e for e in journal.entries if e['kind']=='matrix_sent']
        if matrices and not state['disabled']:
            assert len([e for e in journal.entries if e['kind']=='skip_update']) >= 8
            assert connection.commands.count(2) == 1, connection.commands
            original_anchor = len([e for e in journal.entries if e['kind']=='anchor'])
            state['disabled'] = True
            return ord('d')
        if state['disabled'] and not state['resumed']:
            state['resumed'] = True
            return ord('c')
        if state['resumed'] and len(matrices)>=2 and not state['reanchored']:
            assert len([e for e in journal.entries if e['kind']=='anchor']) == original_anchor
            state['reanchored'] = True
            return ord('r')
        if state['reanchored'] and len([e for e in journal.entries if e['kind']=='anchor']) >= 2:
            return ord('q')
        return 255
    args = board.parser().parse_args(['track','--port','MOCK'])
    factory = EstimationWorker
    with patch.object(board,'LatestCamera',FakeCamera), \
         patch.object(board,'EstimationWorker',lambda:factory(RejectThenAccept())), \
         patch.object(board,'EvidenceRecorder',lambda journal,video:FakeRecorder(journal)), \
         patch.object(board.cv2,'imshow'), patch.object(board.cv2,'waitKey',keyboard), \
         patch.object(board.cv2,'getWindowProperty',return_value=1), patch.object(board.cv2,'destroyAllWindows'):
        board.run_camera(args,connection,journal)
    assert all(state.values()) and not any(e['kind']=='degraded' for e in journal.entries)
    assert not any(e.get('label')=='degraded_affine_off' for e in journal.entries)
    first = next(e for e in journal.entries if e['kind']=='matrix_sent')
    assert first['step_alpha'] >= .89  # former .4 / 1.25-degree split is gone
    return dict(eight_bad_observations='retry_without_off', next_good='automatically_resumed',
                c_keeps_anchor='PASS', d_r_q='PASS', first_5deg_step_alpha=first['step_alpha'])


def check_ecc_fallback():
    ref = texture()
    known = np.array([[1.,0.,12.],[0.,1.,-8.],[0.,0.,1.]])
    cur = render(ref,known)
    job = dict(generation=1,reference=ref,gray=cur,scale=.25,budget=2.,confidence_min=.65)
    # Simulate an ECC result with excellent correlation but incorrect geometry.
    def wrong_ecc(template,reference,warp,*args):
        wrong = np.array([[1.,0.,-40.],[0.,1.,0.]],np.float32)
        return .999,wrong
    with patch('tracking_engine.cv2.findTransformECC',wrong_ecc):
        result = RegistrationEstimator().estimate(job,lambda:False)
    assert result['quality']['method']=='feature_affine'
    assert 'ecc_rejection' in result['quality']
    assert point_error(result['delta'],known)<1.
    return dict(high_score_bad_geometry='kept_valid_feature_fit',
                point_error_px=point_error(result['delta'],known))


def check_recording():
    from evidence_recorder import EvidenceRecorder, summarise_session
    from export_results import export
    with tempfile.TemporaryDirectory(prefix='human_trial_') as temporary:
        root = Path(temporary)
        directory = root/'sessions'/'session_01'
        journal = board.Journal(directory)
        journal.event('session_start',mode='test',package_version=board.PACKAGE_VERSION)
        recorder = EvidenceRecorder(journal)
        frame = np.zeros((1080,1920,3),np.uint8)
        metadata = dict(frame=1,decoded_monotonic=time.monotonic(),generation=0,anchor=1,
                        command_seq=0,state='TRACKING',affine_requested=False,matrix_sent=np.eye(3).tolist())
        recorder.snapshot(frame,metadata,'reference',name='reference_001.png')
        recorder.snapshot(frame,metadata,'manual')
        recorder.video(cv2.resize(frame,(960,540)),metadata)
        recorder.close()
        journal.event('observation',frame=1,quality={'method':'test'},rejection='blur')
        journal.event('manual_action',action='D_disable_pause',anchor=1)
        journal.event('session_end',normal=True)
        journal.close()
        summarise_session(directory)
        assert cv2.imdecode(np.frombuffer((directory/'reference_001.png').read_bytes(),np.uint8),
                            cv2.IMREAD_COLOR).shape==(1080,1920,3)
        assert (directory/'reference_001.json').is_file()
        assert (directory/'会话摘要.md').is_file()
        events = [json.loads(line) for line in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        assert sum(e['kind']=='image_saved' for e in events)==2
        assert not any(e['kind']=='recording_error' for e in events),events
        assert (directory/'preview.avi').stat().st_size>0
        archive = export(root)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None and 'return_manifest.json' in z.namelist()
    return dict(raw_png_and_sidecar='PASS', mjpg_and_timestamps='PASS',
                summary_and_observation_csv='PASS', return_zip='PASS')


def check_fixed_demo_capture():
    from types import SimpleNamespace
    clock=[100.]
    recorded=[]
    class Camera:
        def __init__(self,index):
            self.seq=0
        def get(self):
            self.seq+=1
            return self.seq,clock[0],np.zeros((1080,1920,3),np.uint8)
        def close(self):
            pass
    class Recorder(FakeRecorder):
        def snapshot(self,frame,metadata,role,name=None):
            recorded.append((name,metadata))
            return name
    class Monitor:
        def __init__(self,now):
            pass
        def tick(self,*args):
            pass
    def keyboard(_):
        clock[0]+=.25
        return 255
    journal,connection=MemoryJournal(),MockSerial()
    journal.directory=Path('.')
    args=board.parser().parse_args(['demo','--port','MOCK'])
    with patch.object(board,'LatestCamera',Camera), patch.object(board,'EvidenceRecorder',Recorder), \
         patch.object(board,'StatusMonitor',Monitor), \
         patch.object(board,'time',SimpleNamespace(monotonic=lambda:clock[0])), \
         patch.object(board.cv2,'imshow'), patch.object(board.cv2,'waitKey',keyboard), \
         patch.object(board.cv2,'getWindowProperty',return_value=1), patch.object(board.cv2,'destroyAllWindows'):
        board.run_demo(args,connection,journal)
    assert len(recorded)==5 and connection.commands==[2,2,2,2,2]
    assert [m['affine_requested'] for _,m in recorded]==[True,True,True,True,False]
    return dict(five_stages_and_raw_images='PASS', final_affine_off='PASS')


def check_manual_evidence_schedule():
    from types import SimpleNamespace
    clock=[100.]
    images=[]
    class Camera:
        def __init__(self,index):
            self.seq=0
            self.frame=np.zeros((1080,1920,3),np.uint8)
        def get(self):
            self.seq+=1
            return self.seq,clock[0],self.frame
        def close(self):
            pass
    class Worker:
        def poll(self):
            return None
        def invalidate(self):
            pass
        def close(self):
            pass
        def submit(self,job):
            return False
    class Recorder(FakeRecorder):
        def snapshot(self,frame,metadata,role,name=None):
            images.append((role,metadata.copy()))
            return name or 'images/mock.png'
    journal,connection=MemoryJournal(),MockSerial()
    journal.directory=Path('.')
    state={'b':False,'s':False,'d':False,'c':False,'r':False}
    def keyboard(_):
        clock[0]+=.1
        if clock[0]>105.:
            raise AssertionError('Evidence scheduling timed out')
        anchors=sum(e['kind']=='anchor' for e in journal.entries)
        if anchors:
            for key in ('b','s','d'):
                if not state[key]:
                    state[key]=True
                    return ord(key)
        if any(role=='off_repeat_after_D' for role,_ in images):
            if not state['c']:
                state['c']=True
                return ord('c')
            if not state['r']:
                state['r']=True
                return ord('r')
        if anchors>=2:
            return ord('q')
        return 255
    args=board.parser().parse_args(['track','--port','MOCK'])
    with patch.object(board,'LatestCamera',Camera), patch.object(board,'EstimationWorker',Worker), \
         patch.object(board,'EvidenceRecorder',Recorder), \
         patch.object(board,'time',SimpleNamespace(monotonic=lambda:clock[0])), \
         patch.object(board.cv2,'imshow'), patch.object(board.cv2,'waitKey',keyboard), \
         patch.object(board.cv2,'getWindowProperty',return_value=1), patch.object(board.cv2,'destroyAllWindows'):
        board.run_camera(args,connection,journal)
    roles=[role for role,_ in images]
    for required in ('reference','motion_start','settled_snapshot','before_D','off_after_D','off_repeat_after_D'):
        assert required in roles,roles
    assert all(not metadata['affine_requested'] and metadata['state']=='PAUSED'
               for role,metadata in images if role.startswith('off_'))
    assert all(state.values())
    return dict(b_s_markers='PASS', d_two_delayed_images='PASS', c_then_r='PASS')


def check_main_evidence_lifecycle():
    class Camera:
        def __init__(self,index):
            self.seq=0
            self.frame=np.zeros((1080,1920,3),np.uint8)
        def get(self):
            self.seq+=1
            return self.seq,time.monotonic(),self.frame
        def close(self):
            pass
    with tempfile.TemporaryDirectory(prefix='trial_main_') as temporary:
        root=Path(temporary)
        connection=MockSerial()
        started=time.monotonic()
        def keyboard(_):
            time.sleep(.005)
            return ord('q') if time.monotonic()-started>.7 else 255
        with patch.object(board,'ROOT',root), patch.object(board,'LatestCamera',Camera), \
             patch.object(board.uart,'open_serial',return_value=connection), patch.object(board,'initialize'), \
             patch.object(board.cv2,'imshow'), patch.object(board.cv2,'waitKey',keyboard), \
             patch.object(board.cv2,'getWindowProperty',return_value=1), patch.object(board.cv2,'destroyAllWindows'):
            assert board.main(['track','--port','MOCK','--no-video'])==0
        directories=list((root/'sessions').iterdir())
        assert len(directories)==1
        directory=directories[0]
        events=[json.loads(line) for line in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        assert events[-1]['kind']=='session_end' and events[-1]['normal']
        assert not events[0]['automatic_image_degradation']
        assert any(e.get('label')=='normal_exit_affine_off' for e in events)
        assert (directory/'console.log').is_file() and (directory/'会话摘要.md').is_file()
    return dict(real_journal_console_summary='PASS', normal_exit_affine_off='PASS')


def check_coordinates():
    maximum = 0.
    for matrix in (board.rotation(5), board.rotation(-5),
                   np.array([[1.02, .03, 15.], [-.02, .98, -9.], [0., 0., 1.]])):
        wire, roundtrip = board.quantized_command(matrix)
        cmd, length, payload = uart.parse_frame(wire)
        assert cmd == 2 and length == 25 and len(wire) == 30 and payload[-1] == 1
        q = struct.unpack('<6i', payload[:24])
        hw = np.array([[q[0], q[1], q[4]], [q[2], q[3], q[5]], [0., 0., 65536.]]) / 65536.
        # Independent point equation: FPGA v=1079-y; source y=1079-v'.
        for x, y in ((0., 0.), (1919., 1079.), (800., 200.)):
            hp = hw @ [x, 1079. - y, 1.]
            actual = np.array([hp[0], 1079. - hp[1], 1.])
            expected = matrix @ [x, y, 1.]
            maximum = max(maximum, float(np.abs(actual - expected).max()))
            assert np.allclose(actual, roundtrip @ [x, y, 1.], atol=1e-9)
    assert maximum < .04, maximum
    return dict(max_roundtrip_pixel_error=maximum)


class MemoryJournal:
    def __init__(self):
        self.entries = []

    def event(self, kind, **fields):
        self.entries.append(dict(kind=kind, **fields))


class MockSerial:
    def __init__(self, short=False):
        self.short = short
        self.rx = bytearray()
        self.commands = []

    def write(self, wire):
        cmd, _, _ = uart.parse_frame(wire)
        self.commands.append(cmd)
        if cmd == 5:
            value = (123 << 16) | 0x112
            data = value.to_bytes(4, 'little')
            self.rx.extend(b'\xaa\x55\x05\x04' + data + bytes([sum(data) & 255]))
        return len(wire) - int(self.short)

    def reset_input_buffer(self):
        self.rx.clear()

    def flush(self):
        pass

    def close(self):
        pass

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, count):
        value = bytes(self.rx[:count])
        del self.rx[:count]
        return value


def check_incremental_status():
    journal, connection = MemoryJournal(), MockSerial()
    monitor = board.StatusMonitor(0.)
    monitor.tick(connection, journal, 2.)
    reply = bytes(connection.rx)
    connection.rx[:] = reply[:4]
    monitor.tick(connection, journal, 2.05)
    assert monitor.deadline is not None
    connection.rx[:] = reply[4:]
    monitor.tick(connection, journal, 2.1)
    assert monitor.deadline is None and monitor.last_pub == 123
    for query, receive in ((4.2,4.3),(6.4,6.5)):
        monitor.tick(connection,journal,query)
        monitor.tick(connection,journal,receive)
    monitor.tick(connection,journal,8.6)
    try:
        monitor.tick(connection,journal,8.7)
    except uart.ToolError as exc:
        assert 'stalled' in str(exc)
    else:
        raise AssertionError('Stalled publish counter accepted')
    monitor = board.StatusMonitor(0.)
    monitor.tick(connection,journal,2.)
    connection.rx.clear()
    try:
        monitor.tick(connection,journal,3.6)
    except uart.ToolError as exc:
        assert 'timeout' in str(exc)
    else:
        raise AssertionError('Missing status response accepted')
    return dict(fragmented_rx='PASS', waiting_read_calls=0, stalled='rejected', timeout='rejected')


def check_serial():
    log, connection = MemoryJournal(), MockSerial()
    value = board.status(connection, log)
    assert value == (123 << 16) | 0x112
    assert connection.commands == [5] and log.entries[-1]['kind'] == 'rx_status'
    try:
        board.send(MockSerial(short=True), uart.frame(5), log, 'test_short')
    except uart.ToolError:
        pass
    else:
        raise AssertionError('Short write was accepted')
    rows = uart.load_csv(board.ROOT / '03_params' / 'real_parameters.csv')
    assert len(rows) == 1
    uart.parse_frame(uart.build_distortion({key: rows[0][key] for key in uart.DISTORTION}))
    return dict(status_parser='PASS', short_write='rejected', real_csv='encodes')


def run(record_package=False):
    output = io.StringIO()
    results = dict(python=sys.version, platform=platform.platform(), numpy=np.__version__,
                   opencv=cv2.__version__, pyserial=serial.__version__, hardware_connected=False)
    failed = False
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        print('Board package minimal software smoke checks; no camera/UART/PDS run.')
        started = time.monotonic()
        try:
            assert uart.main(['selftest']) == 0
            results['uart_U0_U5'] = 'PASS'
        except Exception as exc:
            results['uart_U0_U5'] = 'FAIL: ' + repr(exc)
            failed = True
        for name, check in [('sampling_direction', check_direction),
                            ('closed_loop_composition', check_composition),
                            ('step_limited_controller', check_step_controller),
                            ('raw_geometry_and_features', check_raw_and_quality),
                            ('polar_and_corner_limit', check_polar_and_corners),
                            ('cache_budget_and_freshness', check_cache_and_freshness),
                            ('worker_cancellation', check_worker_cancellation),
                            ('incremental_status_monitor', check_incremental_status),
                            ('camera_controls_and_anchors', check_camera_controls_with_blocked_estimator),
                            ('manual_retry_and_resume', check_manual_retry_and_resume),
                            ('default_control_response', check_default_response),
                            ('optional_ecc_cannot_veto_features', check_ecc_fallback),
                            ('recording_and_return_export', check_recording),
                            ('fixed_demo_and_capture', check_fixed_demo_capture),
                            ('manual_evidence_schedule', check_manual_evidence_schedule),
                            ('main_evidence_lifecycle', check_main_evidence_lifecycle),
                            ('fpga_y_and_q16', check_coordinates), ('serial_and_real_csv', check_serial)]:
            try:
                results[name] = dict(result='PASS', **check())
            except Exception as exc:
                results[name] = dict(result='FAIL', error=repr(exc))
                failed = True
            print(name, json.dumps(results[name], ensure_ascii=False))
        results['elapsed_seconds'] = time.monotonic() - started
        results['result'] = 'FAIL' if failed else 'PASS'
        print('OVERALL:', results['result'])
    target = (board.ROOT / '05_checks' if record_package else board.ROOT / 'sessions' /
              ('selftest_' + time.strftime('%Y%m%d_%H%M%S')))
    target.mkdir(exist_ok=True, parents=True)
    (target / 'host_smoke.log').write_text(output.getvalue(), encoding='utf-8')
    (target / 'host_smoke.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output.getvalue())
    return int(failed)


if __name__ == '__main__':
    sys.exit(run('--record-package' in sys.argv))
