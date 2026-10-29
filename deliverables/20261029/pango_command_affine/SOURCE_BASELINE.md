# Candidate provenance

This candidate starts from the supplied `备选一号(1).zip` archive, SHA256
`E8B28110B715841023632C3706857AE77DA56EC0CEBF967CC58A2D609B5835C5`.
The separately supplied original software release has SHA256
`188BBFBB9A4F7E85B7E898A47F8D9A9A3F996F906038F332F266F93334132A44`.
The former contains the latter's original bitstream as well as the Clean Smooth v2
bitstream and host reference-lock improvements. The new command interface uses
the Clean Smooth v2 bitstream, SHA256
`DC936F510F9EB2487931B89BD63DA4EFDB3C0CB81937C5B2D8F34A205AC1B099`.

The original camera, Brown4 map, DDR, HDMI and FPGA smoothing RTL are unchanged
in this host-only candidate. The original release bitstream remains in `release/`.
Command-host files, documentation, the offline test and its receipt were added;
`README.md` points to the new entry. The original manifest is retained as
`DELIVERY_SHA256_baseline.json`, and the full package manifest is regenerated.
