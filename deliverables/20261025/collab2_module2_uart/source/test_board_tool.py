"""独立组包预期和安全门禁自测，不打开串口/视频。"""
import importlib.util,struct,sys,unittest
from pathlib import Path
W=Path(__file__).resolve().parent
sys.path.insert(0,str(W))
import board_validation as b

class Tests(unittest.TestCase):
    def test_status_normal(self):
        s=b.decode_status(0x12340312)
        self.assertEqual(s,dict(raw='12340312',fw=18,params_valid=1,busy=1,pub_count=0x1234))
    def test_status_unknown_refused(self):
        for x in (0,0x11,0x13,0xffffffff):
            with self.subTest(x=x),self.assertRaises(ValueError):b.decode_status(x)
    def test_reserved_refused(self):
        for bit in range(10,16):
            with self.subTest(bit=bit),self.assertRaises(ValueError):b.decode_status((1<<bit)|18)
    def test_publication_wrap(self):
        self.assertEqual(b.pub_delta(2,65534),4)
        self.assertEqual(b.pub_delta(0,0),0)
        self.assertEqual(b.pub_delta(65535,65534),1)
    def test_publication_reset_refused(self):
        with self.assertRaises(ValueError):b.pub_delta(1,100)
    def test_query_exact(self):self.assertEqual(b.tool.frame(5),bytes.fromhex('aa55050000'))
    def test_distortion_manual_wire(self):
        values=dict(fx=1000,fy=1001,cx=960,cy=540,k1=-.125,k2=.25,p1=0,p2=0)
        payload=struct.pack('<8i',65536000,65601536,62914560,35389440,-8192,16384,0,0)
        expected=bytes.fromhex('aa550120')+payload+bytes([sum(payload)&255])
        self.assertEqual(b.tool.build_distortion(values),expected)
    def test_affine_tail(self):
        values=dict(a11=1,a12=0,a21=0,a22=1,tx=24,ty=0)
        payload=struct.pack('<6i',65536,0,0,65536,24*65536,0)+b'\x01'
        expected=bytes.fromhex('aa550219')+payload+bytes([sum(payload)&255])
        self.assertEqual(b.tool.build_affine(values,enable=1),expected)
    def test_all_gamma_channels(self):
        lut=bytes(range(256))
        for ch in range(3):
            with self.subTest(ch=ch):
                self.assertEqual(b.tool.build_gamma(ch,list(lut)),bytes([170,85,3,ch])+lut+b'\x80')
    def test_mode(self):
        self.assertEqual(b.tool.build_mode(0),bytes.fromhex('aa5504040000000000'))
        self.assertEqual(b.tool.build_mode(1),bytes.fromhex('aa5504040100000001'))
    def test_packet_reference_hashes(self):
        self.assertEqual(b.sha(W/'reference/parameters/real_0x01.bin'),'1ac17c4bea8947d1e4a84f50a7eaaf46c0b1d90dd4b8e8ba880bc01e0a09537a')
        self.assertEqual(b.sha(W/'reference/parameters/identity_0x01.bin'),'c1fab7ced10d33faa93c4cd9db0310c0984a919f6e11ac27b685fa56d6983a9d')
    def test_bad_checksum_refused(self):
        p=bytearray(b.tool.build_mode(1));p[-1]^=1
        with self.assertRaises(b.tool.ToolError):b.tool.parse_frame(bytes(p))
    def test_legacy_affine_length_refused(self):
        with self.assertRaises(b.tool.ToolError):b.tool.parse_frame(bytes.fromhex('aa550218')+b'\x00'*25)
    def test_translate_extended_limit(self):
        values=dict(a11=1,a12=0,a21=0,a22=1,tx=4096,ty=-4096)
        self.assertEqual(b.tool.parse_frame(b.tool.build_affine(values,enable=1))[0],2)
        values['tx']=4096+1/65536
        with self.assertRaises(b.tool.ToolError):b.tool.build_affine(values,enable=1)

if __name__=='__main__':unittest.main(verbosity=2)
