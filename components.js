(() => {
  "use strict";

  const registry = {};

  const roleNames = new Set(["5v","3v3","gnd","gpio","input","output","control","power","passive","analog","i2c","spi","uart","pwm","nc"]);

  function pin(id, name, role, x, y, side, number) {
    return { id, name, role: roleNames.has(role) ? role : "passive", x, y, side, ...(number ? { number } : {}) };
  }

  function linearPins(items, width, height, side) {
    const out = [];
    const vertical = side === "left" || side === "right";
    const span = vertical ? height : width;
    const inset = 18;
    const step = items.length > 1 ? (span - inset * 2) / (items.length - 1) : 0;
    items.forEach((item, i) => {
      const pos = inset + i * step;
      const x = side === "left" ? 0 : side === "right" ? width : pos;
      const y = side === "top" ? 0 : side === "bottom" ? height : pos;
      out.push(pin(item.id || "p" + (i + 1), item.name || String(i + 1), item.role || "passive", x, y, side, item.number));
    });
    return out;
  }

  function dipPins(names, width = 170, height = 230) {
    const pins = [];
    const rows = names.length / 2;
    const gap = (height - 54) / Math.max(rows - 1, 1);
    for (let i = 0; i < rows; i += 1) {
      const leftNum = i + 1;
      const rightNum = names.length - i;
      const y = 36 + i * gap;
      const left = names[leftNum - 1];
      const right = names[rightNum - 1];
      pins.push(pin("p" + leftNum, left.name, left.role || "passive", 0, y, "left", leftNum));
      pins.push(pin("p" + rightNum, right.name, right.role || "passive", width, y, "right", rightNum));
    }
    return pins;
  }

  function genericDip(count) {
    const names = Array.from({ length: count }, (_, i) => ({ name: "PIN " + (i + 1), role: "passive" }));
    return dipPins(names, 160, Math.max(150, 50 + (count / 2) * 22));
  }

  function twoPinHorizontal(leftName = "A", rightName = "B", leftRole = "passive", rightRole = "passive", width = 120, height = 50) {
    return [
      pin("a", leftName, leftRole, 0, height / 2, "left"),
      pin("b", rightName, rightRole, width, height / 2, "right")
    ];
  }

  function module4(names, roles) {
    return [
      pin("p1", names[0], roles[0], 0, 35, "left", 1),
      pin("p2", names[1], roles[1], 0, 70, "left", 2),
      pin("p3", names[2], roles[2], 160, 35, "right", 3),
      pin("p4", names[3], roles[3], 160, 70, "right", 4)
    ];
  }

  function makeBus(role, title) {
    return {
      title,
      palette: title,
      category: "Power & Wiring",
      kind: "bus",
      width: 280,
      height: 50,
      subtitle: "Distribution rail",
      keywords: ["rail","bus","power","breadboard"],
      pins: Array.from({ length: 14 }, (_, i) =>
        pin("t" + (i + 1), String(i + 1), role, 10 + i * 20, 50, "bottom")
      )
    };
  }

  const piPinNames = {
    1:["3V3","3v3"],2:["5V","5v"],3:["GPIO2 / SDA1","gpio"],4:["5V","5v"],5:["GPIO3 / SCL1","gpio"],6:["GND","gnd"],
    7:["GPIO4","gpio"],8:["GPIO14 / TXD","gpio"],9:["GND","gnd"],10:["GPIO15 / RXD","gpio"],11:["GPIO17","gpio"],12:["GPIO18","gpio"],
    13:["GPIO27","gpio"],14:["GND","gnd"],15:["GPIO22","gpio"],16:["GPIO23","gpio"],17:["3V3","3v3"],18:["GPIO24","gpio"],
    19:["GPIO10 / MOSI","gpio"],20:["GND","gnd"],21:["GPIO9 / MISO","gpio"],22:["GPIO25","gpio"],23:["GPIO11 / SCLK","gpio"],24:["GPIO8 / CE0","gpio"],
    25:["GND","gnd"],26:["GPIO7 / CE1","gpio"],27:["GPIO0 / ID_SD","gpio"],28:["GPIO1 / ID_SC","gpio"],29:["GPIO5","gpio"],30:["GND","gnd"],
    31:["GPIO6","gpio"],32:["GPIO12","gpio"],33:["GPIO13","gpio"],34:["GND","gnd"],35:["GPIO19","gpio"],36:["GPIO16","gpio"],
    37:["GPIO26","gpio"],38:["GPIO20","gpio"],39:["GND","gnd"],40:["GPIO21","gpio"]
  };

  function makePiPins() {
    const pins = [];
    for (let row = 0; row < 20; row += 1) {
      const odd = row * 2 + 1;
      const even = odd + 1;
      const y = 42 + row * 14;
      pins.push(pin("p" + String(odd).padStart(2,"0"), piPinNames[odd][0], piPinNames[odd][1], 8, y, "left", odd));
      pins.push(pin("p" + String(even).padStart(2,"0"), piPinNames[even][0], piPinNames[even][1], 222, y, "right", even));
    }
    return pins;
  }

  function esp32Pins() {
    const left = [
      ["3V3","3v3"],["EN","control"],["GPIO36 / VP","gpio"],["GPIO39 / VN","gpio"],["GPIO34","gpio"],["GPIO35","gpio"],
      ["GPIO32","gpio"],["GPIO33","gpio"],["GPIO25","gpio"],["GPIO26","gpio"],["GPIO27","gpio"],["GPIO14","gpio"],
      ["GPIO12","gpio"],["GND","gnd"],["GPIO13","gpio"]
    ];
    const right = [
      ["VIN / 5V","5v"],["GND","gnd"],["GPIO23","gpio"],["GPIO22","gpio"],["GPIO1 / TX0","uart"],["GPIO3 / RX0","uart"],
      ["GPIO21","gpio"],["GND","gnd"],["GPIO19","gpio"],["GPIO18","gpio"],["GPIO5","gpio"],["GPIO17","gpio"],
      ["GPIO16","gpio"],["GPIO4","gpio"],["GPIO2","gpio"]
    ];
    const h = 300, w = 210, pins = [];
    left.forEach((p,i)=>pins.push(pin("l"+(i+1),p[0],p[1],0,34+i*18,"left",i+1)));
    right.forEach((p,i)=>pins.push(pin("r"+(i+1),p[0],p[1],w,34+i*18,"right",30-i)));
    return pins;
  }

  function picoPins() {
    const namesL = [
      ["GP0","gpio"],["GP1","gpio"],["GND","gnd"],["GP2","gpio"],["GP3","gpio"],["GP4","gpio"],["GP5","gpio"],["GND","gnd"],["GP6","gpio"],["GP7","gpio"],
      ["GP8","gpio"],["GP9","gpio"],["GND","gnd"],["GP10","gpio"],["GP11","gpio"],["GP12","gpio"],["GP13","gpio"],["GND","gnd"],["GP14","gpio"],["GP15","gpio"]
    ];
    const namesR = [
      ["VBUS","5v"],["VSYS","power"],["GND","gnd"],["3V3_EN","control"],["3V3 OUT","3v3"],["ADC_VREF","analog"],["GP28 / ADC2","gpio"],["GND","gnd"],["GP27 / ADC1","gpio"],["GP26 / ADC0","gpio"],
      ["RUN","control"],["GP22","gpio"],["GND","gnd"],["GP21","gpio"],["GP20","gpio"],["GP19","gpio"],["GP18","gpio"],["GND","gnd"],["GP17","gpio"],["GP16","gpio"]
    ];
    const w=210,h=390,pins=[];
    namesL.forEach((p,i)=>pins.push(pin("p"+(i+1),p[0],p[1],0,30+i*18,"left",i+1)));
    namesR.forEach((p,i)=>pins.push(pin("p"+(40-i),p[0],p[1],w,30+i*18,"right",40-i)));
    return pins;
  }

  const ahctNames = [
    {name:"/1OE",role:"control"},{name:"1A",role:"input"},{name:"1Y",role:"output"},{name:"/2OE",role:"control"},
    {name:"2A",role:"input"},{name:"2Y",role:"output"},{name:"GND",role:"gnd"},{name:"3Y",role:"output"},
    {name:"3A",role:"input"},{name:"/3OE",role:"control"},{name:"4Y",role:"output"},{name:"4A",role:"input"},
    {name:"/4OE",role:"control"},{name:"VCC",role:"5v"}
  ];

  Object.assign(registry, {
    pi40: {
      title:"Raspberry Pi 40-pin", palette:"Raspberry Pi 40-pin", category:"Controllers", kind:"rect", width:230, height:330,
      subtitle:"Physical pin numbering", keywords:["pi","raspberry","gpio","header","spi","i2c"], pins:makePiPins()
    },
    esp32dev: {
      title:"ESP32 DevKit / WROOM-32", palette:"ESP32 DevKit", category:"Controllers", kind:"rect", width:210, height:300,
      subtitle:"Common 30-pin DevKit layout", keywords:["esp32","wroom","wifi","bluetooth","microcontroller"], pins:esp32Pins()
    },
    pico: {
      title:"Raspberry Pi Pico", palette:"Raspberry Pi Pico", category:"Controllers", kind:"rect", width:210, height:390,
      subtitle:"40-pin Pico/Pico W", keywords:["pico","rp2040","rp2350","microcontroller"], pins:picoPins()
    },
    arduino_nano: {
      title:"Arduino Nano", palette:"Arduino Nano", category:"Controllers", kind:"rect", width:190, height:300,
      subtitle:"Generic Nano pin map", keywords:["arduino","nano","atmega328"], pins:[
        ...linearPins([
          {id:"d1",name:"D1/TX",role:"uart"},{id:"d0",name:"D0/RX",role:"uart"},{id:"rst1",name:"RESET",role:"control"},
          {id:"gnd1",name:"GND",role:"gnd"},{id:"d2",name:"D2",role:"gpio"},{id:"d3",name:"D3 PWM",role:"pwm"},
          {id:"d4",name:"D4",role:"gpio"},{id:"d5",name:"D5 PWM",role:"pwm"},{id:"d6",name:"D6 PWM",role:"pwm"},
          {id:"d7",name:"D7",role:"gpio"},{id:"d8",name:"D8",role:"gpio"},{id:"d9",name:"D9 PWM",role:"pwm"},
          {id:"d10",name:"D10",role:"gpio"},{id:"d11",name:"D11/MOSI",role:"spi"},{id:"d12",name:"D12/MISO",role:"spi"}
        ],190,300,"left"),
        ...linearPins([
          {id:"d13",name:"D13/SCK",role:"spi"},{id:"v33",name:"3V3",role:"3v3"},{id:"aref",name:"AREF",role:"analog"},
          {id:"a0",name:"A0",role:"analog"},{id:"a1",name:"A1",role:"analog"},{id:"a2",name:"A2",role:"analog"},
          {id:"a3",name:"A3",role:"analog"},{id:"a4",name:"A4/SDA",role:"i2c"},{id:"a5",name:"A5/SCL",role:"i2c"},
          {id:"a6",name:"A6",role:"analog"},{id:"a7",name:"A7",role:"analog"},{id:"v5",name:"5V",role:"5v"},
          {id:"rst2",name:"RESET",role:"control"},{id:"gnd2",name:"GND",role:"gnd"},{id:"vin",name:"VIN",role:"power"}
        ],190,300,"right")
      ]
    },

    bus5: makeBus("5v","+5V BUS"),
    bus33: makeBus("3v3","+3V3 BUS"),
    busg: makeBus("gnd","GND BUS"),
    node: {
      title:"Junction", palette:"Junction node", category:"Power & Wiring", kind:"node", width:56, height:56,
      subtitle:"Generic connection point", keywords:["junction","splice","node"], pins:[
        pin("l","L","passive",0,28,"left"),pin("r","R","passive",56,28,"right"),pin("t","T","passive",28,0,"top"),pin("b","B","passive",28,56,"bottom")
      ]
    },
    terminal2: {
      title:"2-Pin Screw Terminal", palette:"Screw terminal 2-pin", category:"Connectors", kind:"rect", width:120, height:70,
      subtitle:"Generic 5.08 mm terminal", keywords:["terminal","screw","power"], pins:twoPinHorizontal("1","2","passive","passive",120,70)
    },
    terminal3: {
      title:"3-Pin Screw Terminal", palette:"Screw terminal 3-pin", category:"Connectors", kind:"rect", width:140, height:80,
      subtitle:"Generic terminal", keywords:["terminal","screw"], pins:linearPins([
        {id:"p1",name:"1"},{id:"p2",name:"2"},{id:"p3",name:"3"}
      ],140,80,"bottom")
    },
    jstph2: {
      title:"JST-PH 2.0 2-pin", palette:"JST-PH 2-pin", category:"Connectors", kind:"rect", width:120, height:65,
      subtitle:"Battery / small power connector", keywords:["jst","ph","2.0","battery"], pins:twoPinHorizontal("+","-","power","gnd",120,65)
    },
    header2: {
      title:"2-Pin Header", palette:"Header 1x2", category:"Connectors", kind:"rect", width:90, height:55,
      subtitle:"2.54 mm", keywords:["header","dupont"], pins:twoPinHorizontal("1","2","passive","passive",90,55)
    },
    header3: {
      title:"3-Pin Header", palette:"Header 1x3", category:"Connectors", kind:"rect", width:110, height:60,
      subtitle:"2.54 mm", keywords:["header","dupont"], pins:linearPins([{id:"p1",name:"1"},{id:"p2",name:"2"},{id:"p3",name:"3"}],110,60,"bottom")
    },
    header4: {
      title:"4-Pin Header", palette:"Header 1x4", category:"Connectors", kind:"rect", width:130, height:60,
      subtitle:"2.54 mm", keywords:["header","dupont"], pins:linearPins([{id:"p1",name:"1"},{id:"p2",name:"2"},{id:"p3",name:"3"},{id:"p4",name:"4"}],130,60,"bottom")
    },
    barrel: {
      title:"DC Barrel Jack", palette:"DC barrel jack", category:"Connectors", kind:"rect", width:130, height:75,
      subtitle:"Generic switched jack", keywords:["barrel","dc","power","jack"], pins:[
        pin("v","V+","power",0,25,"left"),pin("g","GND","gnd",0,55,"left"),pin("sw","SW","passive",130,40,"right")
      ]
    },

    resistor: {
      title:"Resistor", palette:"Resistor", category:"Passives", kind:"resistor", width:120, height:50, defaultValue:"1K",
      subtitle:"Double-click to set value", keywords:["ohm","resistance"], pins:twoPinHorizontal()
    },
    capacitor: {
      title:"Ceramic Capacitor", palette:"Ceramic capacitor", category:"Passives", kind:"capacitor", width:70, height:80, defaultValue:"104",
      subtitle:"Non-polar / decoupling", keywords:["cap","ceramic","104","decoupling"], pins:[
        pin("a","A","passive",35,0,"top"),pin("b","B","passive",35,80,"bottom")
      ]
    },
    electrolytic: {
      title:"Electrolytic Capacitor", palette:"Electrolytic capacitor", category:"Passives", kind:"capacitor", width:80, height:90, defaultValue:"100uF",
      subtitle:"Polarized", keywords:["capacitor","electrolytic","bulk"], pins:[
        pin("plus","+","power",30,90,"bottom"),pin("minus","-","gnd",55,90,"bottom")
      ]
    },
    diode: {
      title:"Diode", palette:"Diode", category:"Passives", kind:"rect", width:120, height:55,
      subtitle:"Generic diode", keywords:["rectifier","flyback","1n4007","1n4148"], pins:twoPinHorizontal("A","K","passive","passive",120,55)
    },
    pot: {
      title:"Potentiometer", palette:"Potentiometer", category:"Passives", kind:"rect", width:130, height:85, defaultValue:"10K",
      subtitle:"3-pin variable resistor", keywords:["pot","variable","knob"], pins:[
        pin("a","A","passive",0,30,"left"),pin("w","WIPER","analog",65,85,"bottom"),pin("b","B","passive",130,30,"right")
      ]
    },

    led2: {
      title:"LED", palette:"Standard LED", category:"Lights & Displays", kind:"led", width:100, height:90,
      subtitle:"2-pin LED", keywords:["light","diode"], pins:[
        pin("a","ANODE +","power",30,90,"bottom"),pin("k","CATHODE -","gnd",70,90,"bottom")
      ]
    },
    rgb4: {
      title:"RGB LED 4-pin", palette:"RGB LED 4-pin", category:"Lights & Displays", kind:"led", width:130, height:105,
      subtitle:"Common anode/cathode", keywords:["rgb","led"], pins:[
        pin("r","R","pwm",0,45,"left"),pin("common","COMMON","power",45,105,"bottom"),pin("g","G","pwm",85,105,"bottom"),pin("b","B","pwm",130,45,"right")
      ]
    },
    apa106: {
      title:"APA106-F8", palette:"APA106 addressable LED", category:"Lights & Displays", kind:"led", width:120, height:110,
      subtitle:"Addressable RGB", keywords:["apa106","ws2812","addressable","neopixel","rgb"], pins:[
        pin("din","DIN","input",0,55,"left"),pin("dout","DOUT","output",120,55,"right"),pin("vdd","VDD","5v",40,110,"bottom"),pin("gnd","GND","gnd",80,110,"bottom")
      ]
    },
    oled_i2c: {
      title:"OLED I2C Display", palette:"OLED I2C 4-pin", category:"Lights & Displays", kind:"rect", width:160, height:105,
      subtitle:"Generic SSD1306-style module", keywords:["oled","display","ssd1306","i2c"], pins:linearPins([
        {id:"gnd",name:"GND",role:"gnd"},{id:"vcc",name:"VCC",role:"power"},{id:"scl",name:"SCL",role:"i2c"},{id:"sda",name:"SDA",role:"i2c"}
      ],160,105,"bottom")
    },

    ahct125: {
      title:"SN74AHCT125N", palette:"SN74AHCT125N", category:"ICs & Logic", kind:"dip", width:170, height:230,
      subtitle:"Quad 3-state buffer / level shift", keywords:["74ahct125","level","shift","buffer"], pins:dipPins(ahctNames,170,230)
    },
    dip8: { title:"Generic DIP-8", palette:"Generic DIP-8", category:"ICs & Logic", kind:"dip", width:160, height:150, subtitle:"Editable label", keywords:["ic","chip"], pins:genericDip(8) },
    dip14:{ title:"Generic DIP-14",palette:"Generic DIP-14",category:"ICs & Logic",kind:"dip",width:160,height:205,subtitle:"Editable label",keywords:["ic","chip"],pins:genericDip(14) },
    dip16:{ title:"Generic DIP-16",palette:"Generic DIP-16",category:"ICs & Logic",kind:"dip",width:160,height:225,subtitle:"Editable label",keywords:["ic","chip"],pins:genericDip(16) },
    dip28:{ title:"Generic DIP-28",palette:"Generic DIP-28",category:"ICs & Logic",kind:"dip",width:170,height:355,subtitle:"Editable label",keywords:["ic","chip"],pins:genericDip(28) },

    pushbutton: {
      title:"Momentary Pushbutton", palette:"Pushbutton", category:"Switches & Controls", kind:"rect", width:120, height:75,
      subtitle:"Normally-open", keywords:["button","momentary","switch"], pins:twoPinHorizontal("A","B","passive","passive",120,75)
    },
    spst: {
      title:"SPST Switch", palette:"SPST switch", category:"Switches & Controls", kind:"rect", width:120, height:70,
      subtitle:"On/off", keywords:["toggle","switch","spst"], pins:twoPinHorizontal("COM","OUT","passive","passive",120,70)
    },
    spdt: {
      title:"SPDT Switch", palette:"SPDT switch", category:"Switches & Controls", kind:"rect", width:140, height:90,
      subtitle:"Single pole double throw", keywords:["toggle","switch","spdt"], pins:[
        pin("com","COM","passive",0,45,"left"),pin("a","A","passive",140,25,"right"),pin("b","B","passive",140,65,"right")
      ]
    },
    dpdt: {
      title:"DPDT Switch", palette:"DPDT switch", category:"Switches & Controls", kind:"rect", width:160, height:120,
      subtitle:"Double pole double throw", keywords:["toggle","switch","dpdt"], pins:[
        pin("1","1","passive",0,25,"left"),pin("2","2 COM","passive",0,60,"left"),pin("3","3","passive",0,95,"left"),
        pin("4","4","passive",160,25,"right"),pin("5","5 COM","passive",160,60,"right"),pin("6","6","passive",160,95,"right")
      ]
    },
    touchpad: {
      title:"Capacitive Touch Pad", palette:"Capacitive touch pad", category:"Switches & Controls", kind:"rect", width:140, height:75,
      subtitle:"Generic touch electrode", keywords:["touch","capacitive","sensor"], pins:[pin("sig","SIGNAL","input",140,38,"right")]
    },

    motor: {
      title:"DC Motor", palette:"DC motor", category:"Motors & Sound", kind:"rect", width:120, height:80,
      subtitle:"2-wire motor", keywords:["motor","dc"], pins:twoPinHorizontal("+","-","power","gnd",120,80)
    },
    servo: {
      title:"3-Wire Servo", palette:"Servo 3-wire", category:"Motors & Sound", kind:"rect", width:145, height:90,
      subtitle:"Signal / V+ / GND", keywords:["servo","pwm","sg90","mg90"], pins:linearPins([
        {id:"sig",name:"SIGNAL",role:"pwm"},{id:"v",name:"V+",role:"power"},{id:"g",name:"GND",role:"gnd"}
      ],145,90,"bottom")
    },
    speaker: {
      title:"Speaker", palette:"Speaker", category:"Motors & Sound", kind:"rect", width:120, height:75,
      subtitle:"2-wire speaker", keywords:["audio","speaker","sound"], pins:twoPinHorizontal("+","-","output","gnd",120,75)
    },
    buzzer: {
      title:"Buzzer", palette:"Buzzer", category:"Motors & Sound", kind:"rect", width:110, height:70,
      subtitle:"Active/passive buzzer", keywords:["sound","piezo"], pins:twoPinHorizontal("+","-","power","gnd",110,70)
    },

    battery1s: {
      title:"1x 18650 Battery", palette:"18650 battery 1S", category:"Power", kind:"rect", width:150, height:75,
      subtitle:"Single cell", keywords:["battery","18650","li-ion"], pins:twoPinHorizontal("+","-","power","gnd",150,75)
    },
    battery2s: {
      title:"2x 18650 Holder", palette:"18650 holder 2-cell", category:"Power", kind:"rect", width:170, height:85,
      subtitle:"Check series/parallel wiring", keywords:["battery","18650","holder"], pins:twoPinHorizontal("+","-","power","gnd",170,85)
    },
    boost: {
      title:"DC-DC Boost Module", palette:"Boost converter", category:"Power", kind:"rect", width:170, height:105,
      subtitle:"IN+/IN- to OUT+/OUT-", keywords:["boost","converter","step-up","power"], pins:module4(["IN+","IN-","OUT+","OUT-"],["power","gnd","power","gnd"])
    },
    buck: {
      title:"DC-DC Buck Module", palette:"Buck converter", category:"Power", kind:"rect", width:170, height:105,
      subtitle:"Step-down converter", keywords:["buck","converter","step-down","power"], pins:module4(["IN+","IN-","OUT+","OUT-"],["power","gnd","power","gnd"])
    },
    tp4056: {
      title:"TP4056 Charger Module", palette:"TP4056 Li-ion charger", category:"Power", kind:"rect", width:180, height:125,
      subtitle:"Common protected/unprotected module", keywords:["charger","lithium","usb","tp4056"], pins:[
        pin("in+","IN+","5v",0,35,"left"),pin("in-","IN-","gnd",0,90,"left"),
        pin("b+","B+","power",180,25,"right"),pin("b-","B-","gnd",180,50,"right"),
        pin("out+","OUT+","power",180,80,"right"),pin("out-","OUT-","gnd",180,105,"right")
      ]
    },

    i2c4: {
      title:"Generic I2C Module", palette:"Generic I2C module", category:"Sensors & Modules", kind:"rect", width:160, height:100,
      subtitle:"VCC / GND / SDA / SCL", keywords:["sensor","i2c","module"], pins:linearPins([
        {id:"v",name:"VCC",role:"power"},{id:"g",name:"GND",role:"gnd"},{id:"sda",name:"SDA",role:"i2c"},{id:"scl",name:"SCL",role:"i2c"}
      ],160,100,"bottom")
    },
    spi6: {
      title:"Generic SPI Module", palette:"Generic SPI module", category:"Sensors & Modules", kind:"rect", width:190, height:105,
      subtitle:"VCC/GND/SCK/MOSI/MISO/CS", keywords:["sensor","spi","module"], pins:linearPins([
        {id:"v",name:"VCC",role:"power"},{id:"g",name:"GND",role:"gnd"},{id:"sck",name:"SCK",role:"spi"},
        {id:"mosi",name:"MOSI",role:"spi"},{id:"miso",name:"MISO",role:"spi"},{id:"cs",name:"CS",role:"spi"}
      ],190,105,"bottom")
    },
    uart4: {
      title:"Generic UART Module", palette:"Generic UART module", category:"Sensors & Modules", kind:"rect", width:160, height:100,
      subtitle:"VCC / GND / TX / RX", keywords:["serial","uart","module"], pins:linearPins([
        {id:"v",name:"VCC",role:"power"},{id:"g",name:"GND",role:"gnd"},{id:"tx",name:"TX",role:"uart"},{id:"rx",name:"RX",role:"uart"}
      ],160,100,"bottom")
    },
    relay1: {
      title:"1-Channel Relay Module", palette:"Relay module 1-ch", category:"Sensors & Modules", kind:"rect", width:180, height:130,
      subtitle:"Logic side + COM/NO/NC", keywords:["relay","module","switch"], pins:[
        pin("v","VCC","5v",0,25,"left"),pin("g","GND","gnd",0,55,"left"),pin("in","IN","input",0,90,"left"),
        pin("com","COM","passive",180,25,"right"),pin("no","NO","passive",180,65,"right"),pin("nc","NC","passive",180,105,"right")
      ]
    }
  });

  function normalizeDefinition(id, def) {
    if (!id || !/^[a-z0-9_-]+$/i.test(id)) throw new Error("Component id must use letters, numbers, _ or -.");
    if (!def || typeof def !== "object") throw new Error("Component definition is missing.");
    const width = Math.max(50, Math.min(500, Number(def.width) || 140));
    const height = Math.max(40, Math.min(600, Number(def.height) || 90));
    const pins = Array.isArray(def.pins) ? def.pins.slice(0, 80).map((p, i) => ({
      id: String(p.id || "p" + (i + 1)),
      name: String(p.name || p.id || "P" + (i + 1)).slice(0, 40),
      role: roleNames.has(p.role) ? p.role : "passive",
      x: Math.max(0, Math.min(width, Number(p.x) || 0)),
      y: Math.max(0, Math.min(height, Number(p.y) || 0)),
      side: ["left","right","top","bottom"].includes(p.side) ? p.side : "left",
      ...(Number.isFinite(Number(p.number)) ? { number: Number(p.number) } : {})
    })) : [];
    if (!pins.length) throw new Error("Component needs at least one pin.");
    return {
      title: String(def.title || id).slice(0, 80),
      palette: String(def.palette || def.title || id).slice(0, 80),
      category: String(def.category || "Custom").slice(0, 50),
      kind: ["rect","dip","led","resistor","capacitor","bus","node"].includes(def.kind) ? def.kind : "rect",
      width, height,
      subtitle: String(def.subtitle || "").slice(0, 120),
      keywords: Array.isArray(def.keywords) ? def.keywords.map(String).slice(0, 20) : [],
      defaultValue: String(def.defaultValue || "").slice(0, 50),
      imageData: typeof def.imageData === "string" && def.imageData.startsWith("data:image/") ? def.imageData : "",
      pins
    };
  }

  function registerComponent(id, def, overwrite = true) {
    if (!overwrite && registry[id]) throw new Error("Component id already exists: " + id);
    registry[id] = normalizeDefinition(id, def);
    return registry[id];
  }

  function registerPack(pack, overwrite = true) {
    if (!pack || typeof pack !== "object" || !Array.isArray(pack.components)) {
      throw new Error("Invalid BloomCircuit component pack.");
    }
    let count = 0;
    pack.components.forEach(item => {
      if (!item || !item.id || !item.definition) return;
      registerComponent(String(item.id), item.definition, overwrite);
      count += 1;
    });
    return count;
  }

  function exportPack(ids) {
    const selected = ids && ids.length ? ids : Object.keys(registry);
    return {
      format: "BloomCircuitComponentPack",
      version: 1,
      name: "BloomCircuit component pack",
      components: selected.filter(id => registry[id]).map(id => ({ id, definition: registry[id] }))
    };
  }

  window.BloomLibrary = {
    components: registry,
    registerComponent,
    registerPack,
    exportPack,
    normalizeDefinition,
    roles: Array.from(roleNames).sort()
  };
  window.BLOOM_COMPONENTS = registry;
})();
