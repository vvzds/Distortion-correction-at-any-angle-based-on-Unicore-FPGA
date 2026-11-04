from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'HDMI_DDR3_OV5640_test.fdc'
marker=b'# Independent correction project constraints'
if marker not in p.read_bytes():
    with p.open('ab') as f:
        f.write(b'''\n# Independent correction project constraints
# Board UART pin evidence: prior same-board C63 project, B24 RX / C24 TX.
define_attribute {p:uart_rx} {PAP_IO_DIRECTION} {INPUT}
define_attribute {p:uart_rx} {PAP_IO_LOC} {B24}
define_attribute {p:uart_rx} {PAP_IO_VCCIO} {3.3}
define_attribute {p:uart_rx} {PAP_IO_STANDARD} {LVCMOS33}
define_attribute {p:uart_tx} {PAP_IO_DIRECTION} {OUTPUT}
define_attribute {p:uart_tx} {PAP_IO_LOC} {C24}
define_attribute {p:uart_tx} {PAP_IO_VCCIO} {3.3}
define_attribute {p:uart_tx} {PAP_IO_STANDARD} {LVCMOS33}
define_attribute {p:uart_tx} {PAP_IO_DRIVE} {4}
define_attribute {p:uart_tx} {PAP_IO_SLEW} {SLOW}
# Only the asynchronous input-to-first-synchronizer path is excepted. The
# second stage and UART state machine remain timed in the DDR clock domain.
set_false_path -from [get_ports {uart_rx}]
set_max_delay {8.0} -to [get_ports {uart_tx}]
# Reserve 0.4ns for implementation variation on 125MHz application logic.
set_clock_uncertainty {0.4} -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {ddrphy_sysclk}] -setup
''')
