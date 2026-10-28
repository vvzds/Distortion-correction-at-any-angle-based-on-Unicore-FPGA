"""Cached image registration and a single-flight worker. No UART access here."""
import math
import threading
import time

import cv2
import numpy as np


class ObservationError(ValueError):
    pass


def homogeneous(matrix):
    return np.vstack((matrix, [0., 0., 1.])) if matrix.shape == (2, 3) else matrix.copy()


def validate_geometry(matrix, shape, max_angle=45., min_overlap=.35):
    """Reject bad *raw* observations before the controller reduces their size."""
    matrix = homogeneous(np.asarray(matrix, dtype=float))
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ObservationError('raw_nonfinite_or_shape')
    if not np.allclose(matrix[2], [0., 0., 1.], atol=1e-8):
        raise ObservationError('raw_not_affine')
    singular = np.linalg.svd(matrix[:2, :2], compute_uv=False)
    if np.linalg.det(matrix[:2, :2]) <= 0 or singular.min() < .7 or singular.max() > 1.4:
        raise ObservationError('raw_scale_or_reflection')
    angle = abs(math.degrees(math.atan2(matrix[1, 0], matrix[0, 0])))
    if angle > max_angle:
        raise ObservationError('raw_rotation_jump')
    height, width = shape[:2]
    corners = np.float32([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]])
    polygon = cv2.transform(corners[None], matrix[:2].astype(np.float32))[0]
    intersection, _ = cv2.intersectConvexConvex(polygon, corners)
    overlap = max(0., float(intersection)) / max(1., float(cv2.contourArea(polygon)))
    if overlap < min_overlap:
        raise ObservationError('raw_insufficient_overlap')
    return overlap


def match_quality(source, destination, inliers, matrix, shape,
                  minimum=12, min_ratio=.45, max_rms=4.):
    selected = np.asarray(inliers).ravel().astype(bool)
    count = int(selected.sum())
    ratio = count / max(1, len(selected))
    if count < minimum or ratio < min_ratio:
        raise ObservationError('orb_too_few_inliers')
    src, dst = source[selected], destination[selected]
    errors = cv2.transform(src[None].astype(np.float32), matrix[:2].astype(np.float32))[0] - dst
    rms = float(np.sqrt(np.mean(np.sum(errors ** 2, axis=1))))
    height, width = shape[:2]
    span = np.ptp(src, axis=0)
    coverage = float(span[0] * span[1] / (width * height))
    cells = {(min(3, int(x * 4 / width)), min(2, int(y * 3 / height))) for x, y in src}
    if rms > max_rms:
        raise ObservationError('orb_reprojection_error')
    if coverage < .10 or len(cells) < 4:
        raise ObservationError('orb_clustered_features')
    return dict(matches=len(selected), inliers=count, inlier_ratio=ratio,
                reprojection_rms_px=rms, feature_coverage=coverage, occupied_cells=len(cells))


class RegistrationEstimator:
    """Reference ORB/pyramids are cached per anchor; recovery reuses one match."""
    def __init__(self):
        self.anchor = None
        self.orb = cv2.ORB_create(nfeatures=3000)
        self.reference_cache = {}
        self.cache_builds = 0

    def estimate(self, job, cancelled):
        started = time.monotonic()
        deadline = started + job['budget']

        def checkpoint():
            if cancelled():
                raise ObservationError('cancelled')
            if time.monotonic() > deadline:
                raise ObservationError('estimation_budget_exceeded')

        if self.anchor != job['generation']:
            self.anchor = job['generation']
            self.reference_cache = {}
            self.reference = job['reference']
            small = cv2.resize(self.reference, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
            self.reference_keypoints, self.reference_descriptors = self.orb.detectAndCompute(small, None)
            self.cache_builds += 1
        checkpoint()
        current = job['gray']
        small_current = cv2.resize(current, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
        keypoints, descriptors = self.orb.detectAndCompute(small_current, None)
        if descriptors is None or self.reference_descriptors is None:
            raise ObservationError('orb_no_features')
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        pairs = matcher.knnMatch(self.reference_descriptors, descriptors, k=2)
        reverse_pairs = matcher.knnMatch(descriptors, self.reference_descriptors, k=2)
        reverse_matches = {pair[0].queryIdx: pair[0].trainIdx for pair in reverse_pairs
                           if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance}
        good = [pair[0] for pair in pairs if len(pair) == 2
                and pair[0].distance < .75 * pair[1].distance
                and reverse_matches.get(pair[0].trainIdx) == pair[0].queryIdx]
        if len(good) < 12:
            raise ObservationError('orb_too_few_matches')
        # Full-resolution points: reference -> current is the sampling delta.
        source = np.float32([self.reference_keypoints[m.queryIdx].pt for m in good]) / .5
        destination = np.float32([keypoints[m.trainIdx].pt for m in good]) / .5
        coarse, inliers = cv2.estimateAffinePartial2D(source, destination, method=cv2.RANSAC,
                                                     ransacReprojThreshold=4.)
        if coarse is None or inliers is None:
            raise ObservationError('orb_ransac_failed')
        metrics = match_quality(source, destination, inliers, coarse, current.shape)
        coarse = homogeneous(coarse)
        validate_geometry(coarse, current.shape)
        checkpoint()
        scales = list(dict.fromkeys([job['scale'], .125, .5]))
        best_confidence = 0.
        for scale in scales:
            checkpoint()
            if scale not in self.reference_cache:
                self.reference_cache[scale] = cv2.resize(
                    self.reference, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            small_cur = cv2.resize(current, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            # Preserve the previously measured ECC direction. Its current-
            # template form handles newly exposed black borders better here.
            warp = np.linalg.inv(coarse)[:2].astype(np.float32).copy()
            warp[:, 2] *= scale
            try:
                confidence, refined = cv2.findTransformECC(
                    small_cur, self.reference_cache[scale], warp, cv2.MOTION_AFFINE,
                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 1e-4), None, 5)
            except cv2.error:
                continue
            checkpoint()
            if not math.isfinite(confidence):
                continue
            reverse = homogeneous(refined.astype(float))
            reverse[:2, 2] /= scale
            if abs(np.linalg.det(reverse[:2, :2])) < 1e-6:
                continue
            matrix = np.linalg.inv(reverse)
            overlap = validate_geometry(matrix, current.shape)
            # A high ECC value alone must not override the feature geometry.
            refined_metrics = match_quality(source, destination, inliers, matrix, current.shape)
            best_confidence = max(best_confidence, float(confidence))
            if confidence >= job['confidence_min']:
                return dict(delta=matrix, confidence=float(confidence),
                            quality=dict(**refined_metrics, overlap=overlap, ecc_scale=scale,
                                         reference_cache_builds=self.cache_builds))
        raise ObservationError('ecc_low_confidence_or_failed: %.4f' % best_confidence)


class EstimationWorker:
    """One active job, no backlog. Manual commands invalidate in-flight results."""
    def __init__(self, estimator=None):
        self.estimator = estimator or RegistrationEstimator()
        self.condition = threading.Condition()
        self.job = None
        self.result = None
        self.busy = False
        self.token = 0
        self.stopped = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, job):
        with self.condition:
            if self.stopped or self.busy or self.result is not None:
                return False
            self.job = dict(job, token=self.token)
            self.busy = True
            self.condition.notify()
            return True

    def poll(self):
        with self.condition:
            result, self.result = self.result, None
            return result

    def invalidate(self):
        with self.condition:
            self.token += 1
            self.result = None

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.job is not None or self.stopped)
                if self.stopped:
                    return
                job, self.job = self.job, None
            started = time.monotonic()
            def cancelled():
                with self.condition:
                    return self.stopped or self.token != job['token']
            result = dict(generation=job['generation'], frame=job['frame'],
                          captured_monotonic=job['stamp'], started_monotonic=started,
                          sent_matrix=job['sent_matrix'], delta=None, confidence=0.)
            try:
                result.update(self.estimator.estimate(job, cancelled))
            except Exception as exc:
                result['error'] = str(exc)
            result['finished_monotonic'] = time.monotonic()
            result['estimate_ms'] = 1000 * (result['finished_monotonic'] - started)
            with self.condition:
                if not self.stopped and job['token'] == self.token:
                    self.result = result
                self.busy = False

    def close(self):
        with self.condition:
            self.stopped = True
            self.condition.notify_all()
        # OpenCV calls cannot be forcibly cancelled safely in a thread. The
        # worker is daemonized; late results never perform any serial writes.
        self.thread.join(timeout=.1)


def result_rejection(result, generation, now, ready_at, max_age, budget):
    if result['generation'] != generation:
        return 'obsolete_anchor'
    if result['captured_monotonic'] < ready_at:
        return 'before_settle_deadline'
    if now - result['captured_monotonic'] > max_age:
        return 'stale_decoded_frame'
    if result['finished_monotonic'] - result['started_monotonic'] > budget:
        return 'estimation_budget_exceeded'
    return result.get('error')
