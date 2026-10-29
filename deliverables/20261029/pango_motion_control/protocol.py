"""Protocol v1 transport; no implicit hardware discovery or serial-port opening."""
import binascii,struct,time

MAGIC=0x554E4401
def packet(command,sequence,payload=b''):
    if len(payload)>64: raise ValueError('Payload too large')
    body=struct.pack('<BBBH',1,command,len(payload),sequence&0xffff)+payload
    return b'\xaa\x55'+body+struct.pack('<H',binascii.crc_hqx(body,0xffff))

def decode(data):
    if len(data)<9 or data[:2]!=b'\xaa\x55': raise ValueError('Invalid header')
    version,command,length,sequence=struct.unpack('<BBBH',data[2:7])
    if version!=1 or len(data)!=length+9: raise ValueError('Invalid length/version')
    if binascii.crc_hqx(data[2:-2],0xffff)!=struct.unpack('<H',data[-2:])[0]:
        raise ValueError('CRC mismatch')
    return command,sequence,data[7:-2]

def parse_status(payload):
    if len(payload)!=48: raise ValueError('Wrong status length')
    v=struct.unpack('<12I',payload)
    if v[0]!=MAGIC: raise ValueError('Unexpected firmware identity')
    keys=['frames','cycles','read_wait','write_wait','read_beats','invalid_pixels','overflow_tiles','flags','rx_errors','valid_packets']
    result=dict(zip(keys,v[2:]))
    result.update(active_sequence=v[1]&65535,pending_sequence=v[1]>>16,
                  busy=bool(v[9]&1),pending=bool(v[9]&2),
                  core_fault=bool(v[9]&4),write_fault=bool(v[9]&8),gamma_mode=(v[9]>>4)&3,
                  processing_capacity_fps=(125000000/v[3] if v[3] else None))
    return result

class Connection:
    def __init__(self,port,baud=115200):
        import serial
        self.serial=serial.Serial(port,baudrate=baud,timeout=0.05,write_timeout=1)
        self.sequence=int(time.monotonic()*1000)&65535
    def close(self): self.serial.close()
    def next_sequence(self):
        self.sequence=(self.sequence+1)&65535
        return self.sequence
    def _receive(self,command,sequence,timeout=1.):
        deadline=time.monotonic()+timeout;data=bytearray()
        while time.monotonic()<deadline:
            data.extend(self.serial.read(max(1,self.serial.in_waiting)))
            while True:
                start=data.find(b'\xaa\x55')
                if start<0:
                    data[:]=data[-1:] if data[-1:]==b'\xaa' else b'';break
                del data[:start]
                if len(data)<7: break
                length=data[4]
                if length>64: del data[0];continue
                if len(data)<length+9: break
                candidate=bytes(data[:length+9]);del data[:length+9]
                try: cmd,seq,payload=decode(candidate)
                except ValueError: continue
                if cmd==command and seq==sequence: return payload
        raise TimeoutError('No matching FPGA response; check firmware, cable and port')
    def status(self):
        result,_,_=self.status_timed()
        return result
    def status_timed(self):
        seq=self.next_sequence();sent_at=time.monotonic()
        self.serial.write(packet(0x20,seq))
        payload=self._receive(0xa0,seq)
        received_at=time.monotonic()
        return parse_status(payload),sent_at,received_at
    def configure(self,registers,timeout=1.5):
        status,_,_=self.configure_timed(registers,timeout)
        return status
    def configure_timed(self,registers,timeout=1.5):
        # Avoid false acknowledgement after a 16-bit sequence wrap or reconnect.
        previous=self.status()
        seq=self.next_sequence()
        while seq in (previous['active_sequence'],previous['pending_sequence']):
            seq=self.next_sequence()
        sent_at=time.monotonic()
        self.serial.write(packet(0x10,seq,struct.pack('<16i',*registers)))
        deadline=time.monotonic()+timeout
        last_sample_at=sent_at
        while time.monotonic()<deadline:
            status,query_sent_at,response_at=self.status_timed()
            sample_at=(query_sent_at+response_at)/2.0
            if status['active_sequence']==seq:
                applied_at=(last_sample_at+sample_at)/2.0
                return status,sent_at,applied_at
            if status['core_fault'] or status['write_fault']: raise RuntimeError(status)
            last_sample_at=sample_at
            time.sleep(.02)
        raise TimeoutError('Configuration was not activated at a frame boundary')
