from pathlib import Path
import math,json,unittest,uuid
import numpy as np
from quality_review import edge_scale,convert_mtf,eligibility
from calibration_entry import verify_binding,sha
from snapshot_audit import decode,audit

ROOT=Path(__file__).resolve().parent
class ReviewTests(unittest.TestCase):
    def grid(self,J=None):
        x,y=np.meshgrid(np.arange(11)*25.,np.arange(8)*25.)
        p=np.stack([x,y],-1)
        return p@(np.eye(2)*4 if J is None else np.array(J)).T+np.array([100.,50.])
    def test_analytic_scale(self):
        self.assertAlmostEqual(edge_scale(self.grid(),3,5)['normal_px_per_mm'],4.,places=12)
    def test_rotation(self):
        t=.2;J=np.array([[math.cos(t),-math.sin(t)],[math.sin(t),math.cos(t)]])*4
        s=edge_scale(self.grid(J),3,5)
        self.assertAlmostEqual(s['normal_px_per_mm'],4.,places=12)
        self.assertAlmostEqual(s['slant_deg_from_vertical'],math.degrees(t),places=10)
    def test_shear_normal_not_euclidean_spacing(self):
        s=edge_scale(self.grid([[4,2],[0,4]]),3,5)
        self.assertAlmostEqual(s['normal_px_per_mm'],4/math.sqrt(1.25),places=12)
        self.assertNotAlmostEqual(s['normal_px_per_mm'],4.)
    def test_resampling_invariance(self):
        self.assertAlmostEqual(convert_mtf(.2,4),convert_mtf(.1,8),places=12)
    def test_mtf_reject(self):
        for x,y in [(float('nan'),4),(.6,4),(-.1,4),(.2,0),(.2,float('inf'))]:
            with self.subTest(x=x,y=y):
                with self.assertRaises(ValueError):convert_mtf(x,y)
    def test_grid_reject(self):
        for g in [np.zeros((8,11,2)),self.grid()*float('nan')]:
            with self.assertRaises(ValueError):edge_scale(g,3,5)
        with self.assertRaises(ValueError):edge_scale(self.grid(),3,0)
    def test_unknown_cannot_pass(self):
        self.assertEqual(eligibility({})['status'],'NOT_COMPARABLE')
        self.assertEqual(eligibility(dict(exposure_readback_verified='yes'))['status'],'NOT_COMPARABLE')
    def test_complete_is_not_accepted(self):
        required=eligibility({})['missing'];r=eligibility({k:True for k in required})
        self.assertEqual(r['status'],'ELIGIBLE_FOR_REVIEW');self.assertEqual(r['quality_acceptance'],'NOT_EVALUATED')
    def test_real_provenance(self):
        d=json.loads((ROOT/'real_scale_review/review.json').read_text(encoding='utf-8'))
        self.assertEqual(d['frames_verified'],9);self.assertEqual(len(d['measurements']),12)
        self.assertEqual(d['eligibility']['status'],'NOT_COMPARABLE');self.assertFalse(d['new_capture'])
    def test_repository_binding(self):
        r=verify_binding(Path('C:/Users/叶翔/Documents/Codex/fpga-main'))
        self.assertEqual(len(r),2)
    def test_tampered_binding(self):
        root=ROOT/'evidence'/('binding_'+uuid.uuid4().hex[:8]);(root/'calibration').mkdir(parents=True)
        (root/'calibration/calibrate.py').write_bytes(b'changed')
        with self.assertRaises(ValueError):verify_binding(root)
    def test_degenerate_scale(self):
        with self.assertRaises(ValueError):edge_scale(self.grid([[0,0],[0,4]]),3,5)
    def test_snapshot_decode(self):
        b=bytes.fromhex('a3 c1 a1 23 40 fe 34 00 10 04 00 04 10 05 20')
        d=decode(b)
        self.assertEqual(d['exposure_line_sixteenths'],0x12340)
        self.assertEqual(d['gain_raw'],0x234)
        self.assertEqual(d['awb_gain_raw']['B'],0x520);self.assertIsNone(d['exposure_ms'])
    def test_snapshot_reject_auto(self):
        with self.assertRaises(ValueError):decode(bytes(15))
        with self.assertRaises(ValueError):decode(bytes(14))
    def test_snapshot_changes(self):
        b='a3c101234002340010040004100520'
        d=dict(evidence_kind='REAL_BOARD_READBACK',before_snapshot_hex=b,after_snapshot_hex=b,
            bitstream_sha256='a'*64,snapshot_transport_evidence_sha256='b'*64,
            snapshot_valid_before=True,snapshot_valid_after=True)
        self.assertEqual(audit(d)['status'],'REGISTER_STABILITY_VERIFIED')
        d['after_snapshot_hex']=b[:-2]+'21'
        with self.assertRaises(ValueError):audit(d)
    def test_snapshot_not_synthetic(self):
        with self.assertRaises(ValueError):audit(dict(evidence_kind='SYNTHETIC'))

if __name__=='__main__':unittest.main(verbosity=2)
