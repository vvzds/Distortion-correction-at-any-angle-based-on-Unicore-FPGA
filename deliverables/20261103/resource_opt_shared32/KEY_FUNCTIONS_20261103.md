# FPGA Function Keys

The feature-switch candidate adds the five active-low MES2L676-100HP buttons
to the 1080p30 quality-fusion project. Each input is synchronized and debounced
on the 125 MHz control clock. The default debounce interval is 20 ms. Reset
remains dedicated to system reset.

| Button | Function | Power-on state / behavior |
|---|---|---|
| KEY0 | Toggle Brown radial/tangential distortion terms | Enabled; disabling zeros k1, k2, p1, and p2 while retaining the calibrated projection and affine control. |
| KEY1 | Toggle live BNO085 pose mapping | Disabled; enabling captures the current valid BNO085 pose as the reference and composes the live IMU map with the current host matrix and crop/zoom settings. Video remains live. A host `0x26` enable/disable command updates the same state. |
| KEY2 | Toggle adaptive Gamma | Enabled; the host may still configure Gamma mode, while this key can force linear output. |
| KEY3 | Cycle quality presets | Starts in host-controlled mode, then DN1, DN1+SH1, DN2+SH1, and back to host-controlled mode. A host denoise/sharpen command immediately returns control to the host. |
| KEY4 | Toggle OSD visibility | Starts hidden; a host OSD visibility command sets the same state and takes priority. |

Function state is sampled at the corrected-frame boundary. The display filters
already latch denoise/sharpen levels at HDMI VS, and OSD visibility already
latches at display VS. No image buffer or DDR transaction is added.

KEY1 controls only the automatic IMU pose mapping. When it is off, the IMU map
falls back to the latest host configuration. Host `0x10` affine/projective
matrices remain effective in both KEY1 states; this keeps GUI and host-only
affine commands independent of the IMU switch. The `default_config.vh` values
remain the calibrated no-extra-transform startup map. Brown coefficients and
Gamma remain independently controlled by their keys.

Board pin assignments follow the MES2L676-100HP resource list: KEY0=C22,
KEY1=C23, KEY2=B22, KEY3=A22, KEY4=B20. All are 3.3 V LVCMOS33, active-low,
with pull-ups enabled in the FPGA constraints.

The RTL simulation checks debounce, one-event-per-press behavior, power-on
defaults, the reference-capture toggle, quality preset cycling, and host/key
priority. PDS routing and board validation remain separate acceptance steps;
this change does not claim board FPS or image-quality validation.
