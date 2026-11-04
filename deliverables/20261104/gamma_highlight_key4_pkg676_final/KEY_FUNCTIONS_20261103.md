# FPGA Function Keys

The feature-switch candidate adds the five active-low MES2L676-100HP buttons
to the 1080p30 quality-fusion project. Each input is synchronized and debounced
on the 125 MHz control clock. The default debounce interval is 20 ms. Reset
remains dedicated to system reset.

| Button | Function | Power-on state / behavior |
|---|---|---|
| KEY0 | Toggle Brown radial/tangential distortion terms | Enabled; disabling zeros k1, k2, p1, and p2 while retaining the calibrated projection and affine control. |
| KEY1 | Toggle live BNO085 pose mapping | Disabled; enabling captures the current valid BNO085 pose as the reference and composes the live IMU map with the last accepted host matrix, including crop/zoom and affine terms. Video remains live. A host `0x26` enable/disable command updates the same state. |
| KEY2 | Toggle adaptive Gamma | Enabled; the host may still configure Gamma mode, while this key can force linear output. |
| KEY3 | Cycle quality presets | Starts in host-controlled mode, then DN1, DN1+SH1, DN2+SH1, and back to host-controlled mode. A host denoise/sharpen command immediately returns control to the host. |
| KEY4 | Toggle OSD visibility | Starts hidden; the FPGA OSD comes up with the bundled OV5640 calibration preloaded. On host connection, only the selected calibration values replace those rows. A host OSD visibility command sets the same state and takes priority. |

Function state is sampled at the corrected-frame boundary. The display filters
already latch denoise/sharpen levels at HDMI VS, and OSD visibility already
latches at display VS. Default OSD characters are initialization values in the
existing overlay row store; no image buffer, DDR transaction, or pixel pipeline
stage is added.

KEY1 and host `0x26` update one shared affine-enable state. When enabled, the
IMU map always starts from the latest host `0x10` configuration; a host matrix
update is therefore retained while the key is active. When disabled, the latest
host configuration is passed through unchanged. The GUI sends the calibrated
matrix, quality profile and OSD cache automatically on connect. Brown
coefficients and Gamma remain independently controlled by their keys.

The current KEY4 OSD uses only rows 0..3: FX/FY, CX/CY, K1/K2, and P1/P2.
Rows 4..7 are not part of the current overlay.

Board pin assignments follow the MES2L676-100HP resource list: KEY0=C22,
KEY1=C23, KEY2=B22, KEY3=A22, KEY4=B20. All are 3.3 V LVCMOS33, active-low,
with pull-ups enabled in the FPGA constraints.

The RTL simulation checks debounce, one-event-per-press behavior, power-on
defaults, the reference-capture toggle, quality preset cycling, and host/key
priority. PDS routing and board validation remain separate acceptance steps;
this change does not claim board FPS or image-quality validation.
