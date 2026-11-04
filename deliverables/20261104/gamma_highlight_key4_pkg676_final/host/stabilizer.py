"""Visual reference lock for the FPGA inverse-affine sampler.

Image registration returns D: reference display -> current display. UART frame
history estimates A_seen at the configured capture delay, so the absolute
target is A_seen @ D. Video pixels contain no feedback metadata.
"""
import math
import time

import cv2
import numpy as np

from model import compile_registers, fixed_map


def matrix_from_registers(calibration, registers):
    c, r = calibration, registers
    return np.array([[r[0]*c['fx']/2**28, r[1]*c['fx']/2**28, r[2]*c['fx']/2**20+c['cx']],
                     [r[3]*c['fy']/2**28, r[4]*c['fy']/2**28, r[5]*c['fy']/2**20+c['cy']],
                     [0., 0., 1.]])


class FrameTimeline:
    """UART published-frame history; capture transport delay is configurable.

    This is an estimated time association, not an embedded frame identifier.
    Refuse old/unknown history rather than integrating a residual blindly.
    """
    def __init__(self, delay=.12):
        from collections import deque
        self.delay = delay
        self.items = deque(maxlen=300)

    def append(self, stamp, count, matrix):
        if not self.items or count != self.items[-1][1]:
            self.items.append((stamp, count, homogeneous(matrix)))

    def seen(self, capture_stamp):
        stamp = capture_stamp-self.delay
        eligible = [item for item in self.items if item[0] <= stamp]
        if not eligible or stamp-eligible[-1][0] > .15:
            return None
        return eligible[-1][2].copy()


class SmoothTarget:
    """Frame-rate target progression independent of feature-estimation timing."""
    def __init__(self, matrix, response=.08, max_speed=700.):
        self.current = homogeneous(matrix)
        self.target = self.current.copy()
        self.response, self.max_speed = response, max_speed

    def advance(self, dt):
        dt = min(.05, max(0., dt))
        desired = interpolate_affine(self.current, self.target, 1-np.exp(-dt/self.response))
        distance = corner_distance(self.current, desired)
        limit = self.max_speed*dt
        if distance > limit and distance:
            desired = interpolate_affine(self.current, desired, limit/distance)
        self.current = desired
        return desired.copy()


class ShapeStabilizer:
    """Fast roll/translation, slowly varying bounded affine stretch.

    Constrain the ABSOLUTE reconstructed target, never the displayed residual:
    the residual includes compensation already rendered by the FPGA. The
    symmetric log stretch is relative to the fixed reference crop. Broad,
    reliable feature support is required before changing scale/shear.
    """
    def __init__(self, base, limit=.02, response=.8, rate=.015):
        self.base = homogeneous(base)
        self.base_inverse = np.linalg.inv(self.base)
        self.log_stretch = np.zeros((2, 2))
        self.limit, self.response, self.rate = limit, response, rate

    def constrain(self, target, quality, dt):
        target = homogeneous(target)
        relative = target@self.base_inverse
        u, singular, vt = np.linalg.svd(relative[:2, :2])
        rotation = u@vt
        if not np.isfinite(singular).all() or singular.min() <= 0 or np.linalg.det(rotation) <= 0:
            raise ValueError('Invalid affine shape')
        raw_log = vt.T@np.diag(np.log(singular))@vt
        supported = (quality.get('coverage', 0) >= .25 and
                     quality.get('cells', 0) >= 6 and
                     quality.get('inliers', 0) >= 45 and
                     quality.get('inlier_ratio', 0) >= .65 and
                     quality.get('rms_px', float('inf')) <= 2.5)
        desired = self.log_stretch.copy()
        if supported:
            values, vectors = np.linalg.eigh(raw_log)
            # Small fit fluctuations should not turn into visible breathing.
            values = np.sign(values)*np.maximum(0., np.abs(values)-.003)
            bound = np.log1p(self.limit)
            desired = vectors@np.diag(np.clip(values, -bound, bound))@vectors.T
        dt = min(.1, max(0., dt))
        step = (desired-self.log_stretch)*(1-np.exp(-dt/self.response))
        norm = np.linalg.norm(step, ord=2)
        if norm > self.rate*dt and norm:
            step *= self.rate*dt/norm
        self.log_stretch += step
        values, vectors = np.linalg.eigh(self.log_stretch)
        stretch = vectors@np.diag(np.exp(values))@vectors.T
        result = target.copy()
        result[:2, :2] = rotation@stretch@self.base[:2, :2]
        center = np.array([959.5, 539.5])
        # Preserve the target's center displacement when constraining shape.
        result[:2, 2] = target[:2, :2]@center+target[:2, 2]-result[:2, :2]@center
        return result, dict(supported=bool(supported),
                            raw_relative_scales=singular.tolist(),
                            applied_relative_scales=np.exp(values).tolist())


def homogeneous(matrix):
    matrix = np.asarray(matrix, dtype=float)
    return np.vstack((matrix, [0., 0., 1.])) if matrix.shape == (2, 3) else matrix.copy()


def _add(a, b):
    return a[0]+b[0], a[1]+b[1]


def _mul(a, b):
    products = np.array([a[0]*b[0], a[0]*b[1], a[1]*b[0], a[1]*b[1]])
    return products.min(axis=0), products.max(axis=0)


def _scale(a, value):
    return _mul(a, (value, value))


def _square(a):
    return (np.where((a[0] <= 0) & (a[1] >= 0), 0, np.minimum(a[0]**2, a[1]**2)),
            np.maximum(a[0]**2, a[1]**2))


def fast_guard(calibration, matrix):
    """Conservative derivative-interval bounds for every 64x32 output tile.

Checks a normalized-coordinate envelope and source-patch capacity. The 4 px
padding covers fixed-point truncation in the supported calibration domain.
This is a capacity guard, not a DDR timing or valid-view guarantee.
"""
    c, a = calibration, homogeneous(matrix)
    if not np.isfinite(a).all() or not np.allclose(a[2], [0, 0, 1]):
        raise ValueError('Non-finite/non-affine command')
    singular = np.linalg.svd(a[:2, :2], compute_uv=False)
    if np.linalg.det(a[:2, :2]) <= 0 or singular.min() < .12 or singular.max() > 1.8:
        raise ValueError('Affine scale/reflection outside tracking envelope')
    # Quantized coefficients, exactly the values used by the RTL normalizer.
    registers = compile_registers(c, a[:2], False)
    n = np.array([[registers[0]/2**28, registers[1]/2**28, registers[2]/2**20],
                  [registers[3]/2**28, registers[4]/2**28, registers[5]/2**20]])
    yy, xx = np.mgrid[0:1080:32, 0:1920:64]
    xx, yy = xx.ravel(), yy.ravel()
    hh = np.minimum(31, 1079-yy)
    xs = np.array([n[0, 0]*(xx+dx)+n[0, 1]*(yy+dy)+n[0, 2]
                   for dx, dy in [(0, 0), (63, 0), (0, hh), (63, hh)]])
    ys = np.array([n[1, 0]*(xx+dx)+n[1, 1]*(yy+dy)+n[1, 2]
                   for dx, dy in [(0, 0), (63, 0), (0, hh), (63, hh)]])
    if max(np.abs(xs).max(), np.abs(ys).max()) > 1.49:
        raise ValueError('Transform exceeds supported normalized camera plane')
    x, y = (xs.min(axis=0)-2e-6, xs.max(axis=0)+2e-6), (ys.min(axis=0)-2e-6, ys.max(axis=0)+2e-6)
    x2, y2 = _square(x), _square(y)
    r2 = _add(x2, y2)
    radial = _add((1., 1.), _add(_scale(r2, c['k1']), _scale(_square(r2), c['k2'])))
    q = _add((2*c['k1'], 2*c['k1']), _scale(r2, 4*c['k2']))
    jxx = _add(radial, _add(_mul(x2, q), _add(_scale(y, 2*c['p1']), _scale(x, 6*c['p2']))))
    jyy = _add(radial, _add(_mul(y2, q), _add(_scale(x, 2*c['p2']), _scale(y, 6*c['p1']))))
    jxy = _add(_mul(_mul(x, y), q), _add(_scale(x, 2*c['p1']), _scale(y, 2*c['p2'])))
    magnitude = lambda interval: np.maximum(np.abs(interval[0]), np.abs(interval[1]))
    dx, dy = x[1]-x[0], y[1]-y[0]
    # Include x alignment (up to 15 px), y alignment (1 px) and bilinear neighbors.
    width = 16*np.ceil((np.ceil(c['fx']*(magnitude(jxx)*dx+magnitude(jxy)*dy))+21)/16)
    height = np.ceil(c['fy']*(magnitude(jxy)*dx+magnitude(jyy)*dy))+7
    if width.max() > 256 or height.max() > 256:
        raise ValueError(f'Patch guard requires {width.max():.0f}x{height.max():.0f}, capacity 256x256')
    return dict(max_patch_width_bound=int(width.max()), max_patch_height_bound=int(height.max()))


class ReferenceTracker:
    """Absolute ORB anchor + forward/backward LK between anchor matches."""
    def __init__(self, width=800):
        self.width = width
        self.orb = cv2.ORB_create(nfeatures=1500, fastThreshold=12, edgeThreshold=24)
        self.reference = None
        self.last_global = 0.
        self.previous = None
        self.anchor_points = self.points = None

    def gray(self, frame):
        image = cv2.resize(frame, (self.width, self.width*9//16), interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def anchor(self, frame):
        self.reference = self.gray(frame)
        self.scale = self.width/1920.
        mask = np.full_like(self.reference, 255)
        mask[:max(10, int(20*self.scale)), :] = 0
        self.keypoints, self.descriptors = self.orb.detectAndCompute(self.reference, mask)
        if self.descriptors is None or len(self.keypoints) < 40:
            self.reference = None
            raise ValueError('Too few reference features: point at a textured, stationary scene')
        self.previous = None
        self.anchor_points = self.points = None
        self.last_global = 0.
        return len(self.keypoints)

    def _global(self, gray):
        mask = np.full_like(gray, 255)
        mask[:max(10, int(20*self.scale)), :] = 0
        keypoints, descriptors = self.orb.detectAndCompute(gray, mask)
        if descriptors is None:
            raise ValueError('No scene features')
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        forward = matcher.knnMatch(self.descriptors, descriptors, k=2)
        reverse = matcher.knnMatch(descriptors, self.descriptors, k=2)
        back = {p[0].queryIdx: p[0].trainIdx for p in reverse if len(p)==2 and p[0].distance < .78*p[1].distance}
        good = [p[0] for p in forward if len(p)==2 and p[0].distance < .78*p[1].distance
                and back.get(p[0].trainIdx)==p[0].queryIdx]
        if len(good) < 18:
            raise ValueError('Reference lost: insufficient matching features')
        return (np.float32([self.keypoints[m.queryIdx].pt for m in good]),
                np.float32([keypoints[m.trainIdx].pt for m in good]))

    def estimate(self, frame, now=None):
        now = time.monotonic() if now is None else now
        if self.reference is None:
            raise ValueError('Reference not locked')
        gray = self.gray(frame)
        method = 'LK'
        source = destination = None
        if self.previous is not None and self.points is not None and now-self.last_global < .6:
            next_points, status, _ = cv2.calcOpticalFlowPyrLK(self.previous, gray, self.points[:, None], None,
                winSize=(25, 25), maxLevel=3, criteria=(3, 20, .015))
            if next_points is not None:
                reverse, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, self.previous, next_points, None,
                    winSize=(25, 25), maxLevel=3, criteria=(3, 20, .015))
                if reverse is not None:
                    keep = status.ravel().astype(bool) & back_status.ravel().astype(bool)
                    keep &= np.linalg.norm(reverse[:, 0]-self.points, axis=1) < .8
                    source, destination = self.anchor_points[keep], next_points[keep, 0]
        if source is None or len(source) < 30:
            source, destination = self._global(gray)
            self.last_global = now
            method = 'ORB'
        matrix, inliers = cv2.estimateAffine2D(source, destination, method=cv2.RANSAC,
            ransacReprojThreshold=1.8, maxIters=2000, confidence=.995, refineIters=10)
        if matrix is None or inliers is None:
            raise ValueError('Affine fit failed')
        selected = inliers.ravel().astype(bool)
        src, dst = source[selected], destination[selected]
        # Subpixel photometric refinement only when initialized by a robust
        # feature fit; reject refinements that disagree with the matched scene.
        if method == 'ORB' and len(src) >= 18:
            before = np.sqrt(np.mean(np.sum((cv2.transform(src[None], matrix)[0]-dst)**2, axis=1)))
            try:
                score, refined = cv2.findTransformECC(self.reference, gray, matrix.astype(np.float32),
                    cv2.MOTION_AFFINE, (3, 12, 1e-4), None, 5)
                after = np.sqrt(np.mean(np.sum((cv2.transform(src[None], refined)[0]-dst)**2, axis=1)))
                if score > .75 and after <= before+.25 and np.linalg.det(refined[:2,:2]) > 0:
                    matrix = refined.astype(float)
                    method = 'ORB+ECC'
            except cv2.error:
                pass
        errors = cv2.transform(src[None], matrix)[0]-dst
        rms = float(np.sqrt(np.mean(np.sum(errors**2, axis=1))))/self.scale
        span = np.ptp(src, axis=0) if len(src) else np.zeros(2)
        coverage = float(span.prod()/gray.size)
        cells = {(min(3, int(x*4/gray.shape[1])), min(2, int(y*3/gray.shape[0]))) for x,y in src}
        if len(src) < 18 or selected.mean() < .5 or coverage < .12 or len(cells) < 5 or rms > 4:
            self.previous = None
            raise ValueError(f'Unreliable scene: {len(src)} inliers, coverage {coverage:.2f}, RMS {rms:.1f}px')
        if np.linalg.det(matrix[:2, :2]) <= 0:
            raise ValueError('Reflected/ambiguous fit')
        self.previous, self.anchor_points, self.points = gray, src, dst
        # OpenCV resize maps pixel centers: p_small=s*p_full+(s-1)/2.
        # Conjugate by this map; dividing translation alone biases a 180deg
        # result by roughly 1.4 full-resolution pixels at analysis width 800.
        offset = np.array([(self.scale-1)/2, (gray.shape[0]/1080.-1)/2])
        matrix[:, 2] = (matrix[:, 2]+(matrix[:2,:2]-np.eye(2))@offset)/self.scale
        return homogeneous(matrix), dict(method=method, inliers=len(src), coverage=coverage,
                                          rms_px=rms, inlier_ratio=float(selected.mean()), cells=len(cells))


def interpolate_affine(start, target, fraction):
    """Polar interpolation avoids collapsing the image on 180-degree changes."""
    start, target = homogeneous(start), homogeneous(target)
    def polar(a):
        u, s, vt = np.linalg.svd(a[:2, :2])
        rotation = u@vt
        return math.atan2(rotation[1, 0], rotation[0, 0]), vt.T@np.diag(s)@vt
    angle, stretch = polar(start)
    target_angle, target_stretch = polar(target)
    delta = (target_angle-angle+math.pi)%(2*math.pi)-math.pi
    theta = angle+fraction*delta
    rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    result = np.eye(3)
    result[:2, :2] = rotation@((1-fraction)*stretch+fraction*target_stretch)
    center = np.array([959.5, 539.5])
    start_center = start[:2, :2]@center+start[:2, 2]
    end_center = target[:2, :2]@center+target[:2, 2]
    result[:2, 2] = start_center+fraction*(end_center-start_center)-result[:2, :2]@center
    return result


def corner_distance(a, b):
    points = np.array([[0., 0., 1.], [1919., 0., 1.], [1919., 1079., 1.], [0., 1079., 1.]])
    return float(np.linalg.norm((points@(homogeneous(a)-homogeneous(b)).T)[:, :2], axis=1).max())
