"""Exact RGB565/Q0.8 bilinear model of the FPGA pixel datapath."""
import numpy as np

def pack565(bgr):
    bgr=bgr.astype(np.uint16)
    return ((bgr[:,:,2]>>3)<<11)|((bgr[:,:,1]>>2)<<5)|(bgr[:,:,0]>>3)

def unpack565(pixel):
    r=(pixel>>11)&31;g=(pixel>>5)&63;b=pixel&31
    return np.stack([(b<<3)|(b>>2),(g<<2)|(g>>4),(r<<3)|(r>>2)],axis=-1).astype(np.uint8)

def static_gamma565(image,valid):
    """Steady-scene preview; hardware uses preceding-frame mean/highlight stats."""
    p=pack565(image).astype(np.int64)
    r=(p>>11)&31;g=(p>>5)&63;b=p&31
    luminance=((r+g+b)*8)>>2
    mean=float(luminance[valid].mean()) if valid.any() else 128.
    bright_fraction=float(np.mean(luminance[valid]>=220)) if valid.any() else 0.
    mode=1 if mean<70 else 2 if mean>190 else 3 if bright_fraction>1/16 else 0
    if mode in (1,2):
        gamma=.6 if mode==1 else 1.6
        lut5=np.rint(31*(np.arange(32)/31)**gamma).astype(np.int64)
        lut6=np.rint(63*(np.arange(64)/63)**gamma).astype(np.int64)
        p=(lut5[r]<<11)|(lut6[g]<<5)|lut5[b]
    elif mode==3:
        lut5=np.arange(32,dtype=np.int64);lut6=np.arange(64,dtype=np.int64)
        for lut in (lut5,lut6):
            maximum=len(lut)-1;knee=round(maximum*.75)
            x=np.arange(knee+1,maximum+1)
            lut[knee+1:]=np.rint(knee+(maximum-knee)*((x-knee)/(maximum-knee))**1.6).astype(np.int64)
        p=(lut5[r]<<11)|(lut6[g]<<5)|lut5[b]
    return unpack565(p),mode

def bilinear565(image,sx,sy,valid,fixed=True):
    """Coordinates are Q16 for fixed=True, float64 pixel units otherwise."""
    source=pack565(image).astype(np.int64)
    if fixed:
        x=np.clip(sx>>16,0,1919);y=np.clip(sy>>16,0,1079)
        wx=(sx>>8)&255;wy=(sy>>8)&255;unit=256
    else:
        x=np.clip(np.floor(sx).astype(int),0,1919);y=np.clip(np.floor(sy).astype(int),0,1079)
        wx=sx-np.floor(sx);wy=sy-np.floor(sy);unit=1.
    x1=np.minimum(x+1,1919);y1=np.minimum(y+1,1079)
    p=[source[y,x],source[y,x1],source[y1,x],source[y1,x1]]
    result=np.zeros(x.shape,dtype=np.int64)
    for shift,mask in [(11,31),(5,63),(0,31)]:
        a,b,c,d=[(z>>shift)&mask for z in p]
        h0=a*(unit-wx)+b*wx;h1=c*(unit-wx)+d*wx
        total=h0*(unit-wy)+h1*wy
        channel=((total+32768)>>16) if fixed else np.floor(total+.5).astype(np.int64)
        result|=channel<<shift
    return unpack565(np.where(valid,result,0))
