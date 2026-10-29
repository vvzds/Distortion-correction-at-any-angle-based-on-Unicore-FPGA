"""Direct-command upper computer for FPGA Brown4 plus affine correction."""
import argparse
import queue
import threading
import tkinter as tk
from tkinter import ttk

from command_affine import AffineCommander, Pose
from model import ROOT, load_calibration
from protocol import Connection


SPEEDS = {
    'Slow': (45., 300., .25, .4),
    'Normal': (180., 900., .7, 1.),
    'Fast': (540., 1800., 1.5, 2.),
}


class App:
    def __init__(self, root, args):
        self.root, self.args = root, args
        root.title('FPGA affine control')
        root.geometry('620x360')
        self.events = queue.Queue()
        self.commander = None
        self.busy = False
        self.closing = False
        self.port = tk.StringVar(value=args.port)
        self.speed = tk.StringVar(value='Normal')
        self.state = tk.StringVar(value='Disconnected')
        self.values = {
            'angle': tk.StringVar(value='0'),
            'zoom': tk.StringVar(value='2.0'),
            'tx': tk.StringVar(value='0'),
            'ty': tk.StringVar(value='0'),
            'shear': tk.StringVar(value='0'),
        }
        panel = ttk.Frame(root, padding=14)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='UART').grid(row=0, column=0, sticky='w')
        ttk.Entry(panel, textvariable=self.port, width=12).grid(row=0, column=1, sticky='w')
        self.connect_button = ttk.Button(panel, text='Connect', command=self.connect)
        self.connect_button.grid(row=0, column=2, padx=8)
        ttk.Button(panel, text='Disconnect', command=self.disconnect).grid(row=0, column=3)
        labels = [('angle', 'Rotation (deg)'), ('zoom', 'Crop zoom'),
                  ('tx', 'Horizontal shift (px)'), ('ty', 'Vertical shift (px)'),
                  ('shear', 'Affine shear')]
        for row, (key, label) in enumerate(labels, 1):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky='w', pady=5)
            entry = ttk.Entry(panel, textvariable=self.values[key], width=18)
            entry.grid(row=row, column=1, sticky='w')
            entry.bind('<Return>', lambda _event: self.apply())
        ttk.Label(panel, text='Speed').grid(row=6, column=0, sticky='w', pady=5)
        ttk.Combobox(panel, textvariable=self.speed, values=list(SPEEDS), state='readonly',
                     width=15).grid(row=6, column=1, sticky='w')
        ttk.Button(panel, text='Apply target', command=self.apply).grid(row=6, column=2, padx=8)
        ttk.Button(panel, text='Reset', command=self.reset).grid(row=6, column=3)
        ttk.Label(panel, textvariable=self.state, wraplength=580).grid(
            row=7, column=0, columnspan=4, sticky='w', pady=(20, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def task(self, operation):
        if self.busy:
            return
        self.busy = True
        def run():
            try:
                operation()
                self.events.put(None)
            except Exception as exc:
                self.events.put(str(exc))
        threading.Thread(target=run, daemon=True).start()

    def connect(self):
        if self.commander is not None:
            return
        port = self.port.get()
        def open_link():
            link = Connection(port)
            try:
                commander = AffineCommander(link, load_calibration(self.args.calibration))
                commander.start()
            except Exception:
                link.close()
                raise
            self.commander = commander
        self.task(open_link)

    def disconnect(self):
        if self.commander is None:
            return
        def close_link():
            commander, self.commander = self.commander, None
            commander.close()
        self.task(close_link)

    def apply(self):
        if self.commander is None:
            self.state.set('Connect to the FPGA first')
            return
        try:
            pose = Pose(**{key: float(value.get()) for key, value in self.values.items()})
            pose.validate()
            speeds = SPEEDS[self.speed.get()]
            self.commander.set_speed(*speeds)
            self.commander.set_target(pose)
        except (ValueError, KeyError) as exc:
            self.state.set(str(exc))

    def reset(self):
        for key, value in Pose().__dict__.items():
            self.values[key].set(str(value))
        self.apply()

    def poll(self):
        try:
            while True:
                error = self.events.get_nowait()
                self.busy = False
                if error:
                    self.state.set(error)
                if self.closing and self.commander is None and not error:
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        if self.commander is not None:
            status = self.commander.snapshot()
            if status['error']:
                self.state.set(status['error'])
            else:
                self.state.set(f"Applied {status['current'].angle:.1f} deg, "
                               f"target {status['target'].angle:.1f} deg | "
                               f"published {status['frames']} | commands {status['commands_sent']}")
        elif not self.busy and self.state.get() == 'Disconnected':
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.commander is None:
            self.root.destroy()
            return
        self.closing = True
        def stop():
            self.commander.close()
            self.commander = None
        self.task(stop)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM9')
    parser.add_argument('--calibration', default=str(ROOT/'calibration/ov5640_1080p.json'))
    args = parser.parse_args()
    root = tk.Tk()
    App(root, args)
    root.mainloop()


if __name__ == '__main__':
    main()
