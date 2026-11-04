"""Export ordinary static plots from the measured held-out image report."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'reports/real_image_quality.json').read_text(encoding='utf-8'))['images']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
x=np.arange(5)
for dx,key,label,color in [(-.25,'original','Original','#8a939d'),(0,'fixed_corrected','FPGA bit model','#007f84'),(.25,'float_reference','Float reference','#edab40')]:
    axes[0].bar(x+dx,[z[key]['rms_px'] for z in data],width=.23,label=label,color=color)
axes[0].set_xticks(x,[f'Pose {i}' for i in range(31,36)])
axes[0].set_ylabel('Checker-line RMS residual (pixels)');axes[0].set_ylim(0,1.4)
axes[0].legend(frameon=False);axes[0].grid(axis='y',alpha=.15);axes[0].set_axisbelow(True)
for key,label,color in [('original_sfr','Original','#8a939d'),('corrected_sfr','FPGA bit model','#007f84'),('reference_sfr','Float reference','#edab40')]:
    axes[1].plot(x,[z[key]['median_mtf50_cycles_per_pixel'] for z in data],'o-',label=label,color=color)
axes[1].set_xticks(x,[f'Pose {i}' for i in range(31,36)])
axes[1].set_ylabel('Median estimated MTF50 (cycles/pixel)');axes[1].set_ylim(.10,.20)
axes[1].grid(alpha=.15);axes[1].legend(frameon=False)
fig.suptitle('5 held-out camera images | Offline RGB565 model | Gamma off',fontweight='bold')
fig.savefig(ROOT/'reports/real_images/quality_summary.png',dpi=180)
fig.savefig(ROOT/'reports/real_images/quality_summary.svg')
plt.close(fig)
fig,axes=plt.subplots(1,5,figsize=(15,3.5),layout='constrained',sharey=True)
for i,(axis,z) in enumerate(zip(axes,data)):
    for key,label,color in [('corrected_sfr','Fixed','#007f84'),('reference_sfr','Float','#edab40')]:
        item=z[key];axis.plot(item['frequencies'],item['median_sfr'],label=label,color=color)
    axis.axhline(.5,color='black',lw=.7,ls='--');axis.set_title(f'Pose {i+31}')
    axis.set_xlim(0,.5);axis.set_ylim(0,1.1);axis.grid(alpha=.15);axis.set_xlabel('cycles/pixel')
axes[0].set_ylabel('Median estimated SFR');axes[0].legend(frameon=False)
fig.suptitle('Slanted checker-edge estimate (not a certified ISO12233 measurement)',fontsize=12)
fig.savefig(ROOT/'reports/real_images/sfr_curves.png',dpi=180);plt.close(fig)
