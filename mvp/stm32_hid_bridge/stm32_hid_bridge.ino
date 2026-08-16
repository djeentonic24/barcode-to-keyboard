// STM32F4VE UART -> USB HID keyboard MVP
// Arduino_Core_STM32: Black F407VE, USB support = HID Keyboard
// Scanner UART: USART2  PA3=RX  PA2=TX (TX unused)
// USB Mini (PA11/PA12) -> PC. Open Notepad, then send a scan.

#include <Keyboard.h>

static const uint32_t UART_BAUD = 115200;
static const uint16_t INTER_CHAR_MS = 5;
static const size_t BUF_SIZE = 3072;

static uint8_t buf[BUF_SIZE];
static volatile size_t head = 0;
static volatile size_t tail = 0;

static uint8_t lut[256];

static void lutInit() {
  memset(lut, 0, sizeof(lut));  // 0 = ignore
  for (int c = 0x20; c <= 0x7E; ++c) {
    lut[c] = (uint8_t)c;
  }
  lut[0x0A] = '\n';  // LF  -> Enter
  lut[0x0D] = '\n';  // CR  -> Enter
  lut[0x1C] = '\t';  // FS
  lut[0x1D] = '\t';  // GS
  lut[0x1E] = '\t';  // RS
  lut[0x1F] = '\t';  // US
}

static bool pushByte(uint8_t b) {
  size_t next = (head + 1) % BUF_SIZE;
  if (next == tail) {
    return false;
  }
  buf[head] = b;
  head = next;
  return true;
}

static bool popByte(uint8_t *out) {
  if (tail == head) {
    return false;
  }
  *out = buf[tail];
  tail = (tail + 1) % BUF_SIZE;
  return true;
}

void setup() {
  lutInit();
  Serial2.begin(UART_BAUD);  // PA2/PA3 on Black F407VE
  Keyboard.begin();
}

void loop() {
  while (Serial2.available() > 0) {
    (void)pushByte((uint8_t)Serial2.read());
  }

  uint8_t raw;
  if (!popByte(&raw)) {
    return;
  }

  uint8_t mapped = lut[raw];
  if (mapped == 0) {
    return;
  }

  Keyboard.write(mapped);
  if (INTER_CHAR_MS > 0) {
    delay(INTER_CHAR_MS);
  }
}
