(() => {
  const pinNames = {
    1: ["3V3", "3v3"],
    2: ["5V", "5v"],
    3: ["GPIO2 / SDA1", "gpio"],
    4: ["5V", "5v"],
    5: ["GPIO3 / SCL1", "gpio"],
    6: ["GND", "gnd"],
    7: ["GPIO4", "gpio"],
    8: ["GPIO14 / TXD", "gpio"],
    9: ["GND", "gnd"],
    10: ["GPIO15 / RXD", "gpio"],
    11: ["GPIO17", "gpio"],
    12: ["GPIO18", "gpio"],
    13: ["GPIO27", "gpio"],
    14: ["GND", "gnd"],
    15: ["GPIO22", "gpio"],
    16: ["GPIO23", "gpio"],
    17: ["3V3", "3v3"],
    18: ["GPIO24", "gpio"],
    19: ["GPIO10 / MOSI", "gpio"],
    20: ["GND", "gnd"],
    21: ["GPIO9 / MISO", "gpio"],
    22: ["GPIO25", "gpio"],
    23: ["GPIO11 / SCLK", "gpio"],
    24: ["GPIO8 / CE0", "gpio"],
    25: ["GND", "gnd"],
    26: ["GPIO7 / CE1", "gpio"],
    27: ["GPIO0 / ID_SD", "gpio"],
    28: ["GPIO1 / ID_SC", "gpio"],
    29: ["GPIO5", "gpio"],
    30: ["GND", "gnd"],
    31: ["GPIO6", "gpio"],
    32: ["GPIO12", "gpio"],
    33: ["GPIO13", "gpio"],
    34: ["GND", "gnd"],
    35: ["GPIO19", "gpio"],
    36: ["GPIO16", "gpio"],
    37: ["GPIO26", "gpio"],
    38: ["GPIO20", "gpio"],
    39: ["GND", "gnd"],
    40: ["GPIO21", "gpio"]
  };

  function makePiPins() {
    const pins = [];
    for (let row = 0; row < 20; row += 1) {
      const odd = row * 2 + 1;
      const even = odd + 1;
      const y = 42 + row * 14;
      const [oddName, oddRole] = pinNames[odd];
      const [evenName, evenRole] = pinNames[even];
      pins.push({ id: "p" + String(odd).padStart(2, "0"), number: odd, name: oddName, role: oddRole, x: 8, y, side: "left" });
      pins.push({ id: "p" + String(even).padStart(2, "0"), number: even, name: evenName, role: evenRole, x: 222, y, side: "right" });
    }
    return pins;
  }

  function dipPins(names, width, height) {
    const pins = [];
    const rows = names.length / 2;
    const gap = (height - 54) / Math.max(rows - 1, 1);
    for (let i = 0; i < rows; i += 1) {
      const leftNum = i + 1;
      const rightNum = names.length - i;
      const y = 36 + i * gap;
      const left = names[leftNum - 1];
      const right = names[rightNum - 1];
      pins.push({ id: "p" + leftNum, number: leftNum, name: left.name, role: left.role, x: 0, y, side: "left" });
      pins.push({ id: "p" + rightNum, number: rightNum, name: right.name, role: right.role, x: width, y, side: "right" });
    }
    return pins;
  }

  const ahctNames = [
    { name: "/1OE", role: "control" },
    { name: "1A", role: "input" },
    { name: "1Y", role: "output" },
    { name: "/2OE", role: "control" },
    { name: "2A", role: "input" },
    { name: "2Y", role: "output" },
    { name: "GND", role: "gnd" },
    { name: "3Y", role: "output" },
    { name: "3A", role: "input" },
    { name: "/3OE", role: "control" },
    { name: "4Y", role: "output" },
    { name: "4A", role: "input" },
    { name: "/4OE", role: "control" },
    { name: "VCC", role: "5v" }
  ];

  const COMPONENTS = {
    pi40: {
      title: "Raspberry Pi 40-pin",
      palette: "Pi 40-pin header",
      kind: "rect",
      width: 230,
      height: 330,
      subtitle: "Physical pin numbering",
      pins: makePiPins()
    },
    ahct125: {
      title: "SN74AHCT125N",
      palette: "SN74AHCT125N",
      kind: "dip",
      width: 170,
      height: 230,
      subtitle: "Quad 3-state buffer",
      pins: dipPins(ahctNames, 170, 230)
    },
    apa106: {
      title: "APA106-F8",
      palette: "APA106 LED",
      kind: "led",
      width: 120,
      height: 110,
      subtitle: "Addressable RGB",
      pins: [
        { id: "din", name: "DIN", role: "input", x: 0, y: 55, side: "left" },
        { id: "dout", name: "DOUT", role: "output", x: 120, y: 55, side: "right" },
        { id: "vdd", name: "VDD", role: "5v", x: 40, y: 110, side: "bottom" },
        { id: "gnd", name: "GND", role: "gnd", x: 80, y: 110, side: "bottom" }
      ]
    },
    resistor: {
      title: "Resistor",
      palette: "Resistor",
      kind: "resistor",
      width: 120,
      height: 50,
      subtitle: "Set value in component label",
      pins: [
        { id: "a", name: "A", role: "passive", x: 0, y: 25, side: "left" },
        { id: "b", name: "B", role: "passive", x: 120, y: 25, side: "right" }
      ]
    },
    capacitor: {
      title: "Capacitor",
      palette: "Capacitor",
      kind: "capacitor",
      width: 70,
      height: 80,
      subtitle: "Non-polar / decoupling",
      pins: [
        { id: "a", name: "A", role: "passive", x: 35, y: 0, side: "top" },
        { id: "b", name: "B", role: "passive", x: 35, y: 80, side: "bottom" }
      ]
    },
    bus5: {
      title: "+5V BUS",
      palette: "+5V bus",
      kind: "bus",
      width: 280,
      height: 50,
      subtitle: "Power distribution",
      pins: Array.from({ length: 14 }, (_, i) => ({
        id: "t" + (i + 1),
        name: String(i + 1),
        role: "5v",
        x: 10 + i * 20,
        y: 50,
        side: "bottom"
      }))
    },
    busg: {
      title: "GND BUS",
      palette: "GND bus",
      kind: "bus",
      width: 280,
      height: 50,
      subtitle: "Ground distribution",
      pins: Array.from({ length: 14 }, (_, i) => ({
        id: "t" + (i + 1),
        name: String(i + 1),
        role: "gnd",
        x: 10 + i * 20,
        y: 50,
        side: "bottom"
      }))
    },
    node: {
      title: "Junction",
      palette: "Junction node",
      kind: "node",
      width: 56,
      height: 56,
      subtitle: "Generic connection point",
      pins: [
        { id: "l", name: "L", role: "passive", x: 0, y: 28, side: "left" },
        { id: "r", name: "R", role: "passive", x: 56, y: 28, side: "right" },
        { id: "t", name: "T", role: "passive", x: 28, y: 0, side: "top" },
        { id: "b", name: "B", role: "passive", x: 28, y: 56, side: "bottom" }
      ]
    }
  };

  window.BLOOM_COMPONENTS = COMPONENTS;
})();
