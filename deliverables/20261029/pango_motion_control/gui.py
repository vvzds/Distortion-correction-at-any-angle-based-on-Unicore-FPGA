"""Desktop host controller. Hardware is opened only by the Connect button."""
import base64,json,math,queue,threading,time,tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import cv2,numpy as np
from model import ROOT,load_calibration,affine,preflight,fixed_map,compile_registers
from control import covering_zoom
from motion import motion_pose,update_latency_estimate,verify_trajectory
from protocol import Connection
from resample import bilinear565,static_gamma565

class Application:
    def __init__(self,root):
        self.root=root;root.title('紫光 FPGA · 实时图像校正');root.geometry('1160x820')
        self.calibration=load_calibration();self.link=None;self.image=None
        self.results=queue.Queue();self.working=False;self.debounce=None;self.previous=None;self.queued_apply=False
        self.motion_running=False;self.motion_profile=None;self.motion_start=None
        self.motion_latency_ms=None;self.motion_commands=0;self.motion_cancel=None
        self.angle=tk.DoubleVar(value=0);self.zoom=tk.DoubleVar(value=1)
        self.tx=tk.DoubleVar(value=0);self.ty=tk.DoubleVar(value=0);self.shear=tk.DoubleVar(value=0)
        self.motion_amplitude=tk.DoubleVar(value=45);self.motion_tilt=tk.DoubleVar(value=0.10)
        self.motion_period=tk.DoubleVar(value=6);self.motion_lead=tk.DoubleVar(value=0)
        self.crop=tk.BooleanVar(value=True);self.adaptive=tk.BooleanVar(value=True);self.live=tk.BooleanVar(value=False)
        self.port=tk.StringVar(value='COM11');self.note=tk.StringVar(value='离线模式 · 可先载入图像预览')
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
        motion=ttk.LabelFrame(main,text='连续动态仿射',padding=10);motion.pack(fill='x',pady=(0,10))
        for column,(label,var,width) in enumerate([
                ('旋转幅值°',self.motion_amplitude,8),('倾斜幅值',self.motion_tilt,8),
                ('往返周期 s',self.motion_period,8),('额外提前 ms',self.motion_lead,8)]):
            ttk.Label(motion,text=label).grid(row=0,column=column*2,sticky='w',padx=(0,4))
            ttk.Entry(motion,textvariable=var,width=width).grid(row=0,column=column*2+1,sticky='w',padx=(0,12))
        self.motion_button=ttk.Button(motion,text='启动平滑运动',command=self.start_motion)
        self.motion_button.grid(row=0,column=8,padx=(8,0))
        ttk.Button(motion,text='停止',command=self.stop_motion).grid(row=0,column=9,padx=6)
        self.motion_note=tk.StringVar(value='启动前会预检完整往返轨迹；旋转和倾斜沿正弦曲线平滑往返')
        ttk.Label(motion,textvariable=self.motion_note,wraplength=1020).grid(row=1,column=0,columnspan=10,sticky='w',pady=(8,0))
        self.preview_label=ttk.Label(main,text='载入 1920×1080 图像后，可比较原图与矫正结果',anchor='center')
        self.preview_label.pack(fill='both',expand=True)
        ttk.Label(main,textvariable=self.note,wraplength=1100).pack(fill='x',pady=(12,4))
        ttk.Label(main,textvariable=self.performance).pack(fill='x')
        for variable in (self.angle,self.zoom,self.tx,self.ty,self.shear):
            variable.trace_add('write',self.changed)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh();self.root.after(10,self.poll_results);self.root.after(1000,self.poll_status)
    def refresh(self):
        from serial.tools.list_ports import comports
        self.ports['values']=[p.device for p in comports()]
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
                if error:
                    self.note.set('操作未完成：'+error)
                    if callback==self.motion_command_done:
                        self.stop_motion();self.motion_note.set('动态运动因 FPGA/串口错误停止：'+error)
                else:callback(result)
                if self.queued_apply:
                    self.queued_apply=False
                    if self.link:self.root.after(0,self.apply)
        except queue.Empty:pass
        self.root.after(10,self.poll_results)
    def connect(self):
        if self.link:
            self.stop_motion();self.link.close();self.link=None;self.previous=None;self.note.set('已断开');return
        port=self.port.get()
        def action():
            link=Connection(port)
            try:status=link.status()
            except Exception:link.close();raise
            return link,status
        def done(result):
            self.link,status=result;self.previous=None;self.note.set('已连接 '+port);self.show_status(status)
        self.task(action,done)
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
        if self.motion_running:self.stop_motion()
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
    def start_motion(self):
        if not self.link:self.note.set('先连接 FPGA，再启动动态仿射');return
        if self.working:self.note.set('当前操作完成后再启动动态仿射');return
        parameters=self.parameters()
        if parameters is None:return
        try:
            amplitude=float(self.motion_amplitude.get())
            tilt_amplitude=float(self.motion_tilt.get())
            period=float(self.motion_period.get())
            extra_lead=float(self.motion_lead.get())
        except (ValueError,tk.TclError):
            self.note.set('动态参数需要填写有效数字');return
        if not 0<=amplitude<=180 or not 0<=tilt_amplitude<=0.75 or not 1<=period<=120 or not 0<=extra_lead<=200:
            self.note.set('动态范围：旋转 0–180°，倾斜 0–0.75，周期 1–120 秒，额外提前 0–200 毫秒');return
        minimum_period=max(1.0,2*math.pi*amplitude/90.0,2*math.pi*tilt_amplitude/0.5)
        if period<minimum_period:
            self.note.set(f'为保持每个 30 fps 画面间隔不超过约 3°，当前幅值的周期至少需要 {minimum_period:.1f} 秒');return
        link=self.link;crop=self.crop.get();adaptive=self.adaptive.get();calibration=self.calibration
        cancel=threading.Event();self.motion_cancel=cancel
        self.motion_note.set('正在验证完整往返轨迹与 patch 余量，验证通过后开始运动')
        def action():
            report=verify_trajectory(calibration,parameters['angle'],amplitude,
                parameters['zoom'],parameters['tx'],parameters['ty'],parameters['shear'],
                tilt_amplitude,crop,adaptive,cancel=cancel)
            if cancel.is_set():raise RuntimeError('动态轨迹预检已取消')
            p=dict(parameters);p['zoom']=report['zoom']
            registers=compile_registers(calibration,
                affine(p['angle'],p['zoom'],p['tx'],p['ty'],p['shear']),adaptive)
            status,sent_at,active_estimate_at=link.configure_timed(registers,poll_interval=.005)
            latency=(active_estimate_at-sent_at)*1000.0
            return report,p,status,latency,active_estimate_at,amplitude,tilt_amplitude,period,extra_lead
        def done(result):
            if cancel.is_set():return
            report,p,status,latency,origin,amplitude,tilt_amplitude,period,extra_lead=result
            self.zoom.set(round(p['zoom'],4))
            self.motion_profile=dict(center=p['angle'],amplitude=amplitude,
                shear=p['shear'],tilt=tilt_amplitude,period=period,extra_lead=extra_lead,
                tx=p['tx'],ty=p['ty'],zoom=p['zoom'],adaptive=adaptive,calibration=calibration)
            self.motion_latency_ms=latency;self.motion_start=origin
            self.motion_running=True;self.motion_commands=0
            self.motion_note.set(
                f"運行中 · 轨迹预检 {report['samples']} 点 · patch 最大 "
                f"{report['max_patch_width']}×{report['max_patch_height']} · "
                f"共同缩放 {report['zoom']:.3f} · 生效延迟 {latency:.0f} ms · "
                f"额外提前 {extra_lead:.0f} ms")
            self.show_status(status);self.root.after(10,self.motion_tick)
        self.task(action,done)
    def motion_tick(self):
        if not self.motion_running or not self.link:return
        if self.working:
            self.root.after(10,self.motion_tick);return
        p=self.motion_profile;now=time.monotonic()
        lead=(self.motion_latency_ms or 0.0)+p['extra_lead']
        angle,shear=motion_pose(now-self.motion_start,p['center'],p['amplitude'],
            p['shear'],p['tilt'],p['period'],lead)
        try:
            registers=compile_registers(p['calibration'],
                affine(angle,p['zoom'],p['tx'],p['ty'],shear),p['adaptive'])
        except Exception as error:
            self.stop_motion();self.motion_note.set('动态参数停止：'+str(error));return
        link=self.link
        def action():
            status,sent_at,active_estimate_at=link.configure_timed(registers,poll_interval=.005)
            return status,(active_estimate_at-sent_at)*1000.0,angle,shear
        self.task(action,self.motion_command_done)
    def motion_command_done(self,result):
        status,latency,angle,shear=result
        if status['core_fault'] or status['write_fault'] or status['overflow_tiles']:
            self.stop_motion()
            self.motion_note.set('动态运动因板端错误或 patch 越界停止，请保存状态并检查参数')
            self.show_status(status);return
        self.motion_latency_ms=update_latency_estimate(self.motion_latency_ms,latency)
        self.motion_commands+=1;self.show_status(status)
        p=self.motion_profile
        if self.motion_running:
            self.motion_note.set(
                f"运行动画 · 当前 {angle:.1f}° · 倾斜 {shear:.3f} · "
                f"生效延迟 {self.motion_latency_ms:.0f} ms · "
                f"额外提前 {p['extra_lead']:.0f} ms · 已更新 {self.motion_commands} 次")
            self.root.after(5,self.motion_tick)
    def stop_motion(self):
        if self.motion_cancel:self.motion_cancel.set()
        self.motion_running=False;self.motion_profile=None;self.motion_start=None
        self.motion_note.set('动态运动已停止；画面保持最后一次成功应用的变换')
    def changed(self,*_):
        if self.motion_running:
            self.stop_motion()
            self.motion_note.set('参数已改变，动态运动已停止；请重新预检后启动')
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
            text=f'校正帧发布 {fps:.2f} fps · '
        self.previous=(now,status['frames'])
        capacity=status['processing_capacity_fps']
        text+=f"累计发布 {status['frames']} 帧 · 处理能力 {capacity:.1f} fps" if capacity else '等待首帧'
        text+=f" · 片块越界 {status['overflow_tiles']} · 串口错误 {status['rx_errors']}"
        self.performance.set(text)
        if status['core_fault'] or status['write_fault']:self.note.set('板端报告协议错误，请停止发送并保存状态用于排查')
    def poll_status(self):
        if self.link and not self.working and not self.motion_running:
            link=self.link;self.task(link.status,self.show_status)
        self.root.after(1000,self.poll_status)
    def close(self):
        self.stop_motion()
        if self.link:self.link.close()
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();Application(root);root.mainloop()
