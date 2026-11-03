"""Desktop host controller. Hardware is opened only by the Connect button."""
import base64,json,queue,threading,time,tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import cv2,numpy as np
from model import ROOT,load_calibration,affine,preflight,fixed_map
from control import covering_zoom
from protocol import Connection
from osd_monitor import calibration_rows
from resample import bilinear565,static_gamma565

class Application:
    def __init__(self,root):
        self.root=root;root.title('紫光 FPGA · 实时图像校正');root.geometry('1160x820')
        self.calibration=load_calibration();self.link=None;self.image=None
        self.results=queue.Queue();self.working=False;self.debounce=None;self.previous=None;self.queued_apply=False
        self.angle=tk.DoubleVar(value=0);self.zoom=tk.DoubleVar(value=1)
        self.tx=tk.DoubleVar(value=0);self.ty=tk.DoubleVar(value=0);self.shear=tk.DoubleVar(value=0)
        self.crop=tk.BooleanVar(value=True);self.adaptive=tk.BooleanVar(value=True);self.live=tk.BooleanVar(value=False)
        self.port=tk.StringVar(value='');self.note=tk.StringVar(value='离线模式 · 可先载入图像预览')
        self.performance=tk.StringVar(value='等待板端数据')
        main=ttk.Frame(root,padding=16);main.pack(fill='both',expand=True)
        bar=ttk.Frame(main);bar.pack(fill='x')
        ttk.Label(bar,text='串口').pack(side='left')
        self.ports=ttk.Combobox(bar,textvariable=self.port,width=14);self.ports.pack(side='left',padx=8)
        ttk.Button(bar,text='刷新',command=self.refresh).pack(side='left')
        ttk.Button(bar,text='连接 / 断开',command=self.connect).pack(side='left',padx=8)
        ttk.Button(bar,text='载入标定',command=self.load_calibration).pack(side='right')
        ttk.Button(bar,text='载入图像',command=self.load_image).pack(side='right',padx=8)
        controls=ttk.LabelFrame(main,text='画面变换',padding=12);controls.pack(fill='x',pady=14)
        for row,(label,var,lo,hi) in enumerate([('旋转角度',self.angle,-180,180),('缩放',self.zoom,.5,3),
                                                  ('水平平移',self.tx,-480,480),('垂直平移',self.ty,-270,270)]):
            ttk.Label(controls,text=label,width=12).grid(row=row,column=0,sticky='w',pady=3)
            ttk.Scale(controls,variable=var,from_=lo,to=hi,command=self.changed,length=650).grid(row=row,column=1,sticky='ew')
            ttk.Entry(controls,textvariable=var,width=12).grid(row=row,column=2,padx=10)
        controls.columnconfigure(1,weight=1)
        ttk.Checkbutton(controls,text='自动裁边',variable=self.crop,command=self.changed).grid(row=4,column=0,sticky='w',pady=8)
        options=ttk.Frame(controls);options.grid(row=4,column=1,sticky='w')
        ttk.Checkbutton(options,text='自适应亮度增强',variable=self.adaptive,command=self.changed).pack(side='left')
        ttk.Checkbutton(options,text='调整时自动发送',variable=self.live).pack(side='left',padx=20)
        ttk.Button(controls,text='应用到 FPGA',command=self.apply).grid(row=4,column=2)
        ttk.Button(controls,text='离线预览',command=self.preview).grid(row=5,column=2,pady=4)
        ttk.Label(controls,text='剪切').grid(row=5,column=0,sticky='w')
        ttk.Entry(controls,textvariable=self.shear,width=12).grid(row=5,column=1,sticky='w')
        pose_tools=ttk.Frame(controls);pose_tools.grid(row=6,column=0,columnspan=3,sticky='w',pady=(8,0))
        ttk.Button(pose_tools,text='锁定当前姿态并启用透视校正',
                   command=lambda:self.set_pose_map(True)).pack(side='left')
        ttk.Button(pose_tools,text='关闭姿态透视校正',
                   command=lambda:self.set_pose_map(False)).pack(side='left',padx=8)
        quality=ttk.LabelFrame(main,text='显示画质',padding=10);quality.pack(fill='x',pady=(0,10))
        levels=('关闭','柔和','标准','增强')
        ttk.Label(quality,text='降噪').pack(side='left')
        self.denoise_choice=tk.StringVar(value=levels[0])
        self.sharpen_choice=tk.StringVar(value=levels[0])
        ttk.Combobox(quality,state='readonly',width=8,values=levels,
                     textvariable=self.denoise_choice).pack(side='left',padx=(6,18))
        ttk.Label(quality,text='锐化').pack(side='left')
        ttk.Combobox(quality,state='readonly',width=8,values=levels,
                     textvariable=self.sharpen_choice).pack(side='left',padx=6)
        ttk.Button(quality,text='应用画质',command=self.apply_quality).pack(side='left',padx=14)
        ttk.Button(quality,text='HDMI 标定参数',command=self.apply_calibration_osd).pack(side='left',padx=6)
        self.preview_label=ttk.Label(main,text='载入 1920×1080 图像后，可比较原图与矫正结果',anchor='center')
        self.preview_label.pack(fill='both',expand=True)
        ttk.Label(main,textvariable=self.note,wraplength=1100).pack(fill='x',pady=(12,4))
        ttk.Label(main,textvariable=self.performance).pack(fill='x')
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh();self.root.after(100,self.poll_results);self.root.after(1000,self.poll_status)
    def refresh(self):
        from serial.tools.list_ports import comports
        ports=list(comports());names=[p.device for p in ports]
        self.ports['values']=names
        if self.port.get() not in names:
            preferred=next((p.device for p in ports if 'cp210' in (p.description or '').lower()),None)
            if preferred or names:self.port.set(preferred or names[0])
    def task(self,function,callback):
        if self.working:return
        self.working=True
        def execute():
            try:self.results.put((callback,function(),None))
            except Exception as error:self.results.put((callback,None,str(error)))
        threading.Thread(target=execute,daemon=True).start()
    def poll_results(self):
        try:
            while True:
                callback,result,error=self.results.get_nowait();self.working=False
                if error:self.note.set('操作未完成：'+error)
                else:callback(result)
                if self.queued_apply:
                    self.queued_apply=False
                    if self.link:self.root.after(0,self.apply)
        except queue.Empty:pass
        self.root.after(100,self.poll_results)
    def connect(self):
        if self.link:self.link.close();self.link=None;self.previous=None;self.note.set('已断开');return
        port=self.port.get()
        def action():
            link=Connection(port)
            try:status=link.status()
            except Exception:link.close();raise
            return link,status
        def done(result):
            self.link,status=result;self.previous=None;self.note.set('已连接 '+port);self.show_status(status)
        self.task(action,done)
    def set_pose_map(self,enabled):
        if not self.link:self.note.set('先连接 FPGA；姿态透视功能需要已启动的 BNO085');return
        link=self.link
        def done(status):
            if enabled:
                self.note.set('BNO085 姿态参考已锁定，FPGA 透视校正已启用')
            else:self.note.set('FPGA 姿态透视校正已关闭，恢复普通标定映射')
            self.show_status(status)
        self.task(lambda:link.set_pose_map(enabled),done)
    def apply_quality(self):
        if not self.link:self.note.set('先连接 FPGA');return
        levels={'关闭':0,'柔和':1,'标准':2,'增强':3}
        denoise=levels[self.denoise_choice.get()];sharpen=levels[self.sharpen_choice.get()]
        link=self.link
        self.task(lambda:link.set_quality(denoise,sharpen),self.show_status)
    def apply_calibration_osd(self):
        if not self.link:self.note.set('先连接 FPGA');return
        link=self.link;rows=calibration_rows(self.calibration)
        self.task(lambda:link.osd_update(rows,visible=True),self.show_status)
    def parameters(self):
        try:
            return dict(angle=float(self.angle.get()),zoom=float(self.zoom.get()),tx=float(self.tx.get()),
                        ty=float(self.ty.get()),shear=float(self.shear.get()))
        except (ValueError,tk.TclError):
            self.note.set('参数需要填写有效数字');return None
    def prepare(self,parameters,crop,adaptive):
        calibration=dict(self.calibration)
        if crop:parameters['zoom']=max(parameters['zoom'],covering_zoom(calibration,parameters['angle'],parameters['tx'],parameters['ty'],parameters['shear']))
        matrix=affine(**parameters);registers,report=preflight(calibration,matrix,adaptive)
        return registers,report,parameters
    def apply(self):
        if not self.link:self.note.set('先连接 FPGA；也可使用离线预览');return
        if self.working:self.queued_apply=True;return
        parameters=self.parameters();crop=self.crop.get();adaptive=self.adaptive.get();link=self.link
        if parameters is None:return
        def action():
            registers,report,p=self.prepare(parameters,crop,adaptive)
            return link.configure(registers),report,p
        def done(result):
            status,report,p=result;self.zoom.set(round(p['zoom'],4))
            self.note.set(f"已应用 · 角度 {p['angle']:.1f}° · 有效覆盖 {report['valid_fraction']:.1%} · 配置序号 {status['active_sequence']}")
            self.show_status(status)
        self.task(action,done)
    def changed(self,*_):
        if self.debounce:self.root.after_cancel(self.debounce)
        if self.live.get() and self.link:self.debounce=self.root.after(500,self.apply)
    def preview(self):
        if self.image is None:self.note.set('请先载入 1920×1080 图像');return
        parameters=self.parameters();crop=self.crop.get();adaptive=self.adaptive.get();image=self.image.copy()
        if parameters is None:return
        def action():
            registers,report,p=self.prepare(parameters,crop,adaptive)
            sx,sy,valid=fixed_map(registers)
            result=bilinear565(image,sx,sy,valid)
            if adaptive:result,mode=static_gamma565(result,valid)
            pair=np.hstack([image,result]);pair=cv2.resize(pair,(1100,309),interpolation=cv2.INTER_AREA)
            cv2.putText(pair,'Original',(15,28),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,220,255),2)
            cv2.putText(pair,'Corrected preview',(565,28),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,220,255),2)
            ok,png=cv2.imencode('.png',pair)
            return base64.b64encode(png).decode(),p,report
        def done(result):
            data,p,report=result;self.photo=tk.PhotoImage(data=data);self.preview_label.configure(image=self.photo,text='')
            self.zoom.set(round(p['zoom'],4));self.note.set(f"RGB565 离线预览 · 有效覆盖 {report['valid_fraction']:.1%} · Gamma 按静态场景收敛值显示")
        self.task(action,done)
    def load_image(self):
        path=filedialog.askopenfilename(filetypes=[('图像','*.png *.jpg *.bmp'),('所有文件','*')])
        if not path:return
        image=cv2.imread(path)
        if image is None or image.shape[:2]!=(1080,1920):messagebox.showerror('图像尺寸','需要 1920×1080 图像，与标定链路一致');return
        self.image=image;self.note.set('已载入 '+Path(path).name);self.preview()
    def load_calibration(self):
        path=filedialog.askopenfilename(filetypes=[('Brown4 标定','*.json')])
        if path:
            try:self.calibration=load_calibration(path);self.note.set('已载入标定 '+Path(path).name)
            except Exception as error:messagebox.showerror('标定文件',str(error))
    def show_status(self,status):
        now=time.monotonic();text=''
        if self.previous:
            timestamp,frames=self.previous;fps=((status['frames']-frames)&0xffffffff)/(now-timestamp)
            text=f'实际新帧 {fps:.2f} fps · '
        self.previous=(now,status['frames'])
        capacity=status['processing_capacity_fps']
        text+=f"累计 {status['frames']} 帧 · 处理能力 {capacity:.1f} fps" if capacity else '等待首帧'
        text+=f" · 片块越界 {status['overflow_tiles']} · 串口错误 {status['rx_errors']}"
        if status['pose_map_enabled']:
            text+=' · 姿态透视校正'+('重算中' if status['pose_map_busy'] else
                    '已生效' if status['pose_map_valid'] else
                    '等待姿态' if not status['pose_reference_valid'] else '姿态超出安全范围')
        self.performance.set(text)
        if status['core_fault'] or status['write_fault']:self.note.set('板端报告协议错误，请停止发送并保存状态用于排查')
    def poll_status(self):
        if self.link and not self.working:
            link=self.link;self.task(link.status,self.show_status)
        self.root.after(1000,self.poll_status)
    def close(self):
        if self.link:self.link.close()
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();Application(root);root.mainloop()
