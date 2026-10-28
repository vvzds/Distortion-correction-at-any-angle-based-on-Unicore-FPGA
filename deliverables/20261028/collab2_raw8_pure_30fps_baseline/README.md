# RAW8 pure-path board baseline (2026-10-28)

The attached `RAW8_1080p30_complete_original.zip` is the user-supplied, unmodified complete PDS project. Its SHA256 is `A8E9C797628A149E2E7BEC89C35C551F08879D62541B7CE96022240FDC26767F`. The ZIP contains the PDS project, RTL, IP, FDC, build scripts, route report, and bitstream. The bitstream within the ZIP is `basic_1.3_RAW8_R2/generate_bitstream/hdmi_ddr_ov5640_top.sbit`, SHA256 `AF961A846F09BCBA0828F649A04EE3C798D32D82606CFCD2B51F0B1326E12612`.

This bitstream differs from the previously tested `D:\FPGA PDS\ww\s_1080p30_.sbit` (SHA256 `014DDC2B4B834EC5194AAAC5085A7B609A3D43F7FC0A5D8D21A8E49E06EF8547`). Do not use the earlier `s_` board measurement as evidence for this source package.

## Hardware observation

The user programmed the AF961A bitstream into SRAM. With continuous movement in front of the camera, Hagibis captured 751 frames at 1920x1080 MJPEG 30 fps in a 25-second command window. Every consecutive frame had a different SHA256 after conversion to 320x180 grayscale: 750 transitions and zero repeated-frame runs. Each of the 24 interior full seconds had 30 changes; the first second had 29 because its first sample has no predecessor, and the final 1/30-second boundary sample had one. The 29.960/s quotient from dividing by 751/30 seconds is an endpoint convention, not evidence of a missing frame. This confirms 30 distinct visible HDMI frames per complete second in this test window.

`af961a_motion_framehash.txt` is the raw FFmpeg `framehash` output. Recalculate it with `python ../collab2_c50_camera_path_probe/analyze_framehash.py af961a_motion_framehash.txt`. Capture settings were `-f dshow -video_size 1920x1080 -framerate 30 -vcodec mjpeg -i video=Hagibis -t 25 -vf scale=320:180,format=gray -f framehash`.

The included post-route timing report states `All Constraints Met`; its slow-corner DDR clock WNS/WHS are `+3.476/+0.133 ns`. The source `reg_config.v` has the same 263 register write values as the C50 board-test source, so this is a relevant camera-configuration baseline for C50. The pure project has no distortion correction engine, and its frame-buffer controller may reuse the last completed frame on an HDMI boundary. The no-repeat observation is output evidence; independent VSYNC, DDR frame-completion, and display-slot counters are still needed to prove no internal drop under all operating conditions.

## Next integration gate

Preserve this source and bitstream as the 30 fps straight-through fallback. Integrate the repository's distortion mapping, bilinear sampler, DDR read cache, and frame ownership contracts into a separate candidate. Run full-frame accuracy and concurrent DDR traffic simulation, complete PDS route at 125 MHz with positive setup and hold slack, then repeat board measurements with motion. The C50 board evidence currently shows 48.0648 completed correction writes/s but only 18.056 distinct visible changes/s over 25 seconds; optimizing only arithmetic publication speed will not close that gap.
