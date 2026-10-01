from pathlib import Path

path = Path("components.js")
text = path.read_text()

marker = "\n  function picoPins() {\n"
if marker not in text:
    raise SystemExit("picoPins marker not found")

helper = r'''
  function esp32S3SuperMiniPins() {
    const left = [
      ["TX / UART0 TX","uart"],["RX / UART0 RX","uart"],["GPIO1","gpio"],["GPIO2","gpio"],["GPIO3","gpio"],
      ["GPIO4","gpio"],["GPIO5","gpio"],["GPIO6","gpio"],["GPIO7","gpio"],["GPIO38","gpio"],["GPIO37","gpio"],
      ["GPIO34","gpio"],["GPIO33","gpio"],["GPIO21","gpio"],["GPIO18","gpio"],["GPIO17","gpio"],["GPIO16","gpio"],
      ["GPIO15","gpio"],["GPIO14","gpio"]
    ];
    const right = [
      ["5V","5v"],["GND","gnd"],["3V3 OUT","3v3"],["GPIO13","gpio"],["GPIO12","gpio"],
      ["GPIO11","gpio"],["GPIO10","gpio"],["GPIO9","gpio"],["GPIO8","gpio"],["GPIO36","gpio"],["GPIO35","gpio"],
      ["GPIO48","gpio"],["GPIO47","gpio"],["GPIO46","gpio"],["GPIO45","gpio"],["GPIO42","gpio"],["GPIO41","gpio"],
      ["GPIO40","gpio"],["GPIO39","gpio"]
    ];
    const w = 220, h = 410, pins = [];
    left.forEach((p,i) => pins.push(pin("l"+(i+1), p[0], p[1], 0, 34+i*19, "left")));
    right.forEach((p,i) => pins.push(pin("r"+(i+1), p[0], p[1], w, 34+i*19, "right")));
    pins.push(pin("batp","B+ LiPo","power",82,h,"bottom"));
    pins.push(pin("batm","B- LiPo","gnd",138,h,"bottom"));
    return pins;
  }
'''

text = text.replace(marker, "\n" + helper + marker, 1)

registry_marker = '''    pico: {
      title:"Raspberry Pi Pico", palette:"Raspberry Pi Pico", category:"Controllers", kind:"rect", width:210, height:390,
'''
if registry_marker not in text:
    raise SystemExit("registry marker not found")

entry = '''    esp32s3_supermini_hw747: {
      title:"ESP32-S3 SuperMini HW-747", palette:"ESP32-S3 SuperMini HW-747", category:"Controllers", kind:"rect", width:220, height:410,
      subtitle:"HW-747 V0.0.2 • USB-C • LiPo charge pads", keywords:["esp32","s3","supermini","hw-747","wifi","bluetooth","lipo","battery","usb-c"], pins:esp32S3SuperMiniPins()
    },
'''

text = text.replace(registry_marker, entry + registry_marker, 1)
path.write_text(text)
