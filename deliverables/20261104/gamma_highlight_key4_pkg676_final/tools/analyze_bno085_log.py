"""Offline BNO probe log analysis. No devices or video files opened.

Compares quaternion body increments with measured body gyro; distinguishes
sensor->world convention from its inverse using motion, not Euler angles.
It cannot infer actual physical mounting without operator axis observations.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from imu import signed_us, load_mount
from bno085 import quaternion_rotation


def rotation_vector(r):
    from math import acos
    angle=acos(float(np.clip((np.trace(r)-1)/2,-1,1)))
    skew=np.array([r[2,1]-r[1,2],r[0,2]-r[2,0],r[1,0]-r[0,1]])
    if angle<1e-6:return skew/2
    if angle>2.8:raise ValueError('Too large inter-sample rotation for local gyro comparison')
    return skew*angle/(2*np.sin(angle))


def analyze(records,mount):
    pairs=[];latest=None;valid=[];generations=set()
    for state in records:
        if state.get('seen')!=3:continue
        generations.add(state['generation'])
        if latest and (state['generation']!=latest['generation'] or
                       signed_us(state['now'],latest['now'])<0):latest=None
        if latest is None or state['angle_us']!=latest['angle_us']:
            valid.append(state)
            if latest:
                dt=signed_us(state['angle_us'],latest['angle_us'])
                gyro=np.deg2rad((np.array(state['gyro'])+np.array(latest['gyro']))/2)
                if .002<=dt<=.05 and 5<=np.rad2deg(np.linalg.norm(gyro))<=500:
                    a=quaternion_rotation(latest['quaternion']);b=quaternion_rotation(state['quaternion'])
                    normal=rotation_vector(a.T@b)/dt
                    inverse=rotation_vector(a@b.T)/dt
                    pairs.append((gyro,normal,inverse))
            latest=state
    result=dict(samples=len(records),unique_poses=len(valid),generations=sorted(generations),
                gyro_comparison_pairs=len(pairs),hardware_access=False)
    if len(valid)>=2:
        span=signed_us(valid[-1]['angle_us'],valid[0]['angle_us'])
        if span>0 and len(generations)==1:
            result['sensor_pose_hz']=((valid[-1]['packets']-valid[0]['packets'])&0xffffff)/span
        gyro=np.array([s['gyro'] for s in valid]);camera=gyro@mount.T
        result['sensor_gyro_rms_deg_s']=np.sqrt(np.mean(gyro**2,axis=0)).tolist()
        result['camera_gyro_rms_deg_s']=np.sqrt(np.mean(camera**2,axis=0)).tolist()
        result['sensor_max_age_ms']=max(signed_us(s['now'],s['angle_us'])*1000 for s in valid)
        result['errors_first_last']=[valid[0]['errors'],valid[-1]['errors']]
    if len(pairs)>=10:
        values=np.array(pairs)
        score=lambda x:float(np.sqrt(np.mean(np.sum(x*x,axis=1))))
        normal=score(values[:,1]-values[:,0]);inverse=score(values[:,2]-values[:,0])
        speed=score(values[:,0])
        result.update(normal_gyro_rms_error_rad_s=normal,inverse_gyro_rms_error_rad_s=inverse,
                      gyro_rms_rad_s=speed)
        if normal<.25*speed and normal<inverse*.5:
            result['convention']='sensor_to_world_supported_by_motion'
        elif inverse<.25*speed and inverse<normal*.5:
            result['convention']='world_to_sensor_suspected_STOP_and_review_adapter'
        else:result['convention']='inconclusive_check_motion_time_alignment_bias'
    else:result['convention']='insufficient_motion_pairs'
    result['physical_mount_verified']=False
    result['note']='Requires signed single-axis operator trials. This comparison cannot prove optical mounting, exact latency or image quality.'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('log',type=Path)
    p.add_argument('--mount',type=Path,default=ROOT/'calibration/bno085_mount.json')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    data=json.loads(a.log.read_text(encoding='utf-8-sig'))
    records=data.get('records',[])
    _,mount=load_mount(a.mount)
    result=analyze(records,mount)
    text=json.dumps(result,indent=2)
    print(text)
    if a.output:
        if a.output.exists():p.error('Use a new output file')
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(text,encoding='utf-8')


if __name__=='__main__':main()
