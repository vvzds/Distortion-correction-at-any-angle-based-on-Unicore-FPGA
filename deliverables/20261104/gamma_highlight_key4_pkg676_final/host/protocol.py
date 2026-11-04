"""Protocol v1 transport; no implicit hardware discovery or serial-port opening."""
import binascii,struct,time

MAGIC=0x554E4401
CMD_SHARPEN=0x30
CMD_DENOISE=0x32
CMD_OSD_ROW=0x34
CMD_OSD_VISIBLE=0x35
def parse_quality_ack(payload,command,requested_level):
    if len(payload)!=48: raise ValueError('Wrong quality ACK length')
    magic,schema,source,level,result=struct.unpack('<4sBBBB',payload[:8])
    if magic!=b'QACK' or schema!=1: raise ValueError('Unsupported quality ACK format')
    if source!=command or level!=requested_level: raise ValueError('Quality ACK does not match request')
    if result!=0 or payload[8:]!=bytes(40): raise ValueError('Quality ACK has invalid result/reserved bytes')
    return {'command':source,'level':level}
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
                  pose_map_enabled=bool(v[9]&64),pose_reference_valid=bool(v[9]&128),
                  pose_map_busy=bool(v[9]&256),pose_capture_generation=(v[9]>>9)&255,
                  pose_map_valid=bool(v[9]&(1<<17)),
                  key1_lock_requested=bool(v[9]&(1<<18)),
                  processing_capacity_fps=(125000000/v[3] if v[3] else None))
    return result

class Connection:
    def __init__(self,port,baud=115200):
        import serial
        self.serial=serial.Serial(port,baudrate=baud,timeout=0.005,write_timeout=1)
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
        seq=self.next_sequence();self.serial.write(packet(0x20,seq))
        return parse_status(self._receive(0xa0,seq))
    def osd_line(self,row,text):
        if not 0<=row<4:raise ValueError('Calibration OSD row must be 0..3')
        rendered=text.upper().encode('ascii','strict')
        if len(rendered)>48 or any(c<32 or c>126 for c in rendered):
            raise ValueError('OSD supports at most 48 printable ASCII characters')
        payload=bytes([row])+rendered.ljust(48,b' ')
        self.serial.write(packet(CMD_OSD_ROW,self.next_sequence(),payload))
    def osd_enable(self,enabled):
        self.serial.write(packet(CMD_OSD_VISIBLE,self.next_sequence(),bytes([bool(enabled)])))
    def osd_update(self,rows,visible=True):
        self.osd_rows(rows)
        self.osd_enable(visible)
        return self.status()

    def osd_rows(self,rows):
        """Send cached calibration rows; row writes have no per-command ACK."""
        for row,text in rows.items():self.osd_line(row,text)
        return {'osd_rows_sent':len(rows),'osd_rows_confirmed':False}
    def set_quality(self,denoise,sharpen,timeout=1.):
        if (type(denoise) is not int or type(sharpen) is not int
                or not 0<=denoise<=3 or not 0<=sharpen<=3):
            raise ValueError('Denoise and sharpen levels must be integers 0..3')
        confirmed=[]
        for command,level,name in ((CMD_DENOISE,denoise,'denoise'),
                                   (CMD_SHARPEN,sharpen,'sharpen')):
            try:
                sequence=self.next_sequence()
                request=packet(command,sequence,bytes([level]))
                if self.serial.write(request)!=len(request):
                    raise RuntimeError('Serial write was incomplete')
                payload=self._receive(command|0x80,sequence,timeout=timeout)
                parse_quality_ack(payload,command,level)
            except Exception as error:
                accepted=', '.join(f'{item} confirmed' for item in confirmed) or 'none'
                raise RuntimeError(f'Quality command not fully confirmed; {accepted}; '
                                   f'{name} is unknown: {error}') from error
            confirmed.append(name)
        return {'quality_acknowledged':True,'denoise':denoise,'sharpen':sharpen}
    def frame_state(self):
        seq=self.next_sequence();self.serial.write(packet(0x21,seq))
        payload=self._receive(0xa1,seq,timeout=.3)
        if len(payload)!=48:raise ValueError('Wrong smooth telemetry length')
        values=struct.unpack('<12I',payload)
        if values[0]!=0x534d5432 or values[11]!=0x00020001:
            raise ValueError('Clean smooth firmware required; do not use the old marker firmware')
        return dict(frames=values[1], registers=list(struct.unpack('<6i',payload[8:32])),
                    gamma=values[9], flags=values[10],
                    pose_map_enabled=bool(values[10]&(1<<6)),
                    key1_lock_requested=bool(values[10]&(1<<18)),version=values[11])
    def set_target(self,registers):
        seq=self.next_sequence()
        self.serial.write(packet(0x10,seq,struct.pack('<16i',*registers)))
        return seq
    def set_pose_map(self,enabled=True,timeout=2.0):
        """Capture the current BNO085 orientation and enable FPGA projective mapping."""
        before=self.status()
        self.serial.write(packet(0x26,self.next_sequence(),bytes([1 if enabled else 0])))
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            status=self.status()
            captured=(not enabled or status['pose_capture_generation'] !=
                      before['pose_capture_generation'])
            if status['pose_map_enabled']==bool(enabled) and captured and (
                    not enabled or (status['pose_reference_valid'] and status['pose_map_valid'] and
                                    not status['pose_map_busy'])):
                return status
            time.sleep(.05)
        raise TimeoutError('FPGA pose-map command did not become active')
    def configure(self,registers,timeout=1.5):
        # Avoid false acknowledgement after a 16-bit sequence wrap or reconnect.
        previous=self.status()
        seq=self.next_sequence()
        while seq in (previous['active_sequence'],previous['pending_sequence']):
            seq=self.next_sequence()
        self.serial.write(packet(0x10,seq,struct.pack('<16i',*registers)))
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            status=self.status()
            if status['active_sequence']==seq: return status
            if status['core_fault'] or status['write_fault']: raise RuntimeError(status)
            time.sleep(.02)
        raise TimeoutError('Configuration was not activated at a frame boundary')
