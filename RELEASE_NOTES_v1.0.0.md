# BloomCircuit v1.0.0

First public release of BloomCircuit.

BloomCircuit is a lightweight offline circuit-layout app for makers. It uses a shared 2.54 mm breadboard/perfboard grid so boards, built-in parts, custom parts, pins, and wires all live in the same physical coordinate system.

## Highlights

- Offline browser-based editor for Raspberry Pi and PC
- Raspberry Pi desktop/application launcher
- 10 px = 2.54 mm physical snap grid
- Perfboard, stripboard, breadboard, and breadboard-with-rails underlays
- 47 built-in components reworked onto the breadboard grid
- Component rotation and exact percentage scaling
- Visual Component Maker with embedded real-part images
- Click/drag pin placement snapped to breadboard holes
- Component-maker zoom from 25% to 800% plus Fit
- Visible component cutout/footprint outline
- Click-pin-to-click-pin wiring
- 5V, 3V3, GND, DATA, and OTHER wire types
- Endpoint notes for voltage, scope, waveform, and signal documentation
- Endpoint edit buttons moved inward along wires for visibility
- Save/load project JSON
- Portable custom component packs
- Etch View
- Millimeter SVG export for laser/fabrication workflows
- Happy Jarz starter circuit template

## How to run BloomCircuit

### Windows PC

1. Download **Source code (zip)** from this release.
2. **Extract the ZIP first** to a normal folder. Do not run `index.html` directly from inside the ZIP.
3. Open Command Prompt in the extracted BloomCircuit folder.
4. Start the local server:

```bat
py -m http.server 8080
```

If `py` is not available, try:

```bat
python -m http.server 8080
```

5. Open this address in your browser:

```text
http://localhost:8080
```

BloomCircuit's entry file is `index.html`, but it is designed to be served through the tiny local HTTP server above. Double-clicking `index.html` directly can prevent its CSS/JavaScript from loading correctly.

### Raspberry Pi

From a cloned copy of the repository:

```bash
cd ~/BloomCircuit
git pull
bash install_pi.sh
```

Then open **BloomCircuit** from the desktop icon/application menu, or run:

```bash
bloomcircuit
```

Once installed, BloomCircuit runs locally and does not require an internet connection.

## License

BloomCircuit is free and open source under the MIT License.

Verify component pinouts and wiring against the actual hardware and datasheets before powering a circuit.
