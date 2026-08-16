// STM32F4VE: Mode 1 UART→HID, Mode 2 config on USART1 (J6) — same frames as future HID Feature Reports.
// Scanner: USART2 PA3. Config: USART1 PA9/PA10 @ 115200 8N1. Mini-USB = HID BarcodeHID.

#include <EEPROM.h>
#include <Keyboard.h>
#include "persist.h"

static const uint32_t CFG_BAUD = 115200;
static const size_t BUF_SIZE = 3072;

static uint8_t buf[BUF_SIZE];
static volatile size_t head = 0;
static volatile size_t tail = 0;

static uint8_t lut[256];
static uint32_t scanBaud = 115200;
static uint8_t scanParity = 0;  // 0N 1E 2O
static uint8_t scanStop = 1;
static uint8_t interCharMs = 5;
static bool configMode = false;
static uint32_t lastRxMs = 0;
static uint32_t lastKeyMs = 0;
static const uint32_t UART_IDLE_MS = 5;

static const uint8_t FRAME = 64;
static const uint8_t CMD_PING = 1, CMD_ENTER = 2, CMD_EXIT = 3;
static const uint8_t CMD_GET_UART = 4, CMD_SET_UART = 5;
static const uint8_t CMD_GET_LUT = 6, CMD_SET_LUT = 7;
static const uint8_t CMD_RESTORE = 8, CMD_COMMIT = 9;
static const uint8_t ACK = 0x80;

static void lutDefaults() {
  memset(lut, 0, sizeof(lut));
  for (int c = 0x20; c <= 0x7E; ++c) {
    lut[c] = (uint8_t)c;
  }
  lut[0x0A] = '\n';
  lut[0x0D] = '\n';
  lut[0x1C] = '\t';
  lut[0x1D] = '\t';
  lut[0x1E] = '\t';
  lut[0x1F] = '\t';
}

static uint32_t crc32(const uint8_t *p, size_t n) {
  uint32_t c = 0xFFFFFFFFUL;
  for (size_t i = 0; i < n; ++i) {
    c ^= p[i];
    for (int b = 0; b < 8; ++b) {
      c = (c & 1) ? (c >> 1) ^ 0xEDB88320UL : (c >> 1);
    }
  }
  return ~c;
}

static void persistGather(Persist *s) {
  memset(s, 0, sizeof(*s));
  s->magic = SETTINGS_MAGIC;
  s->version = SETTINGS_VER;
  s->baud = scanBaud;
  s->parity = scanParity;
  s->stop = scanStop;
  s->delayMs = interCharMs;
  memcpy(s->lut, lut, 256);
  s->crc = crc32((uint8_t *)s, sizeof(*s) - 4);
}

static bool persistValid(const Persist *s) {
  if (s->magic != SETTINGS_MAGIC || s->version != SETTINGS_VER) {
    return false;
  }
  return s->crc == crc32((const uint8_t *)s, sizeof(*s) - 4);
}

static void eepromLoad() {
  Persist s;
  uint8_t *p = (uint8_t *)&s;
  for (size_t i = 0; i < sizeof(s); ++i) {
    p[i] = EEPROM.read((int)i);
  }
  if (!persistValid(&s) || s.baud < 9600 || s.baud > 115200 || s.delayMs > 20) {
    lutDefaults();
    scanBaud = 115200;
    scanParity = 0;
    scanStop = 1;
    interCharMs = 5;
    return;
  }
  scanBaud = s.baud;
  scanParity = s.parity;
  scanStop = s.stop ? s.stop : 1;
  interCharMs = s.delayMs;
  memcpy(lut, s.lut, 256);
}

static void eepromSave() {
  Persist s;
  persistGather(&s);
  const uint8_t *p = (const uint8_t *)&s;
  for (size_t i = 0; i < sizeof(s); ++i) {
    EEPROM.update((int)i, p[i]);
  }
}

static uint32_t serialConfig() {
  if (scanParity == 1) {
    return scanStop == 2 ? SERIAL_8E2 : SERIAL_8E1;
  }
  if (scanParity == 2) {
    return scanStop == 2 ? SERIAL_8O2 : SERIAL_8O1;
  }
  return scanStop == 2 ? SERIAL_8N2 : SERIAL_8N1;
}

static void applyScannerUart() {
  Serial2.end();
  Serial2.begin(scanBaud, serialConfig());
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

static uint16_t crc16(const uint8_t *p, size_t n) {
  uint16_t c = 0xFFFF;
  for (size_t i = 0; i < n; ++i) {
    c ^= p[i];
    for (int b = 0; b < 8; ++b) {
      c = (c & 1) ? (uint16_t)((c >> 1) ^ 0xA001) : (uint16_t)(c >> 1);
    }
  }
  return c;
}

static void sendAck(uint8_t cmd, uint8_t seq, uint8_t status, const uint8_t *pl,
                    uint8_t n) {
  uint8_t f[64];
  memset(f, 0, sizeof(f));
  f[0] = 0xA5;
  f[1] = 0x5A;
  f[2] = cmd | ACK;
  f[3] = seq;
  f[4] = (uint8_t)(1 + n);
  f[5] = status;
  if (n && pl) {
    memcpy(f + 6, pl, n);
  }
  uint16_t c = crc16(f, 62);
  f[62] = (uint8_t)c;
  f[63] = (uint8_t)(c >> 8);
  Serial.write(f, 64);
}

static void handleFrame(const uint8_t *f) {
  if (f[0] != 0xA5 || f[1] != 0x5A) {
    return;
  }
  uint16_t got = (uint16_t)f[62] | ((uint16_t)f[63] << 8);
  if (crc16(f, 62) != got) {
    return;
  }
  uint8_t cmd = f[2];
  uint8_t seq = f[3];
  uint8_t n = f[4];
  const uint8_t *pl = f + 5;
  if (n > 56) {
    sendAck(cmd, seq, 1, NULL, 0);
    return;
  }

  switch (cmd) {
    case CMD_PING: {
      const uint8_t id[] = {'B', 'K', 'C', 'F', 'G'};
      sendAck(cmd, seq, 0, id, 5);
      break;
    }
    case CMD_ENTER:
      configMode = true;
      head = tail = 0;
      sendAck(cmd, seq, 0, NULL, 0);
      break;
    case CMD_EXIT:
      configMode = false;
      head = tail = 0;
      sendAck(cmd, seq, 0, NULL, 0);
      break;
    case CMD_GET_UART: {
      uint8_t out[7];
      out[0] = (uint8_t)scanBaud;
      out[1] = (uint8_t)(scanBaud >> 8);
      out[2] = (uint8_t)(scanBaud >> 16);
      out[3] = (uint8_t)(scanBaud >> 24);
      out[4] = scanParity;
      out[5] = scanStop;
      out[6] = interCharMs;
      sendAck(cmd, seq, 0, out, 7);
      break;
    }
    case CMD_SET_UART: {
      if (n < 7) {
        sendAck(cmd, seq, 1, NULL, 0);
        break;
      }
      uint32_t baud = (uint32_t)pl[0] | ((uint32_t)pl[1] << 8) | ((uint32_t)pl[2] << 16) |
                      ((uint32_t)pl[3] << 24);
      if (baud < 9600 || baud > 115200 || pl[6] > 20) {
        sendAck(cmd, seq, 2, NULL, 0);
        break;
      }
      scanBaud = baud;
      scanParity = pl[4];
      scanStop = pl[5] ? pl[5] : 1;
      interCharMs = pl[6];
      applyScannerUart();
      sendAck(cmd, seq, 0, NULL, 0);
      break;
    }
    case CMD_GET_LUT: {
      if (n < 1) {
        sendAck(cmd, seq, 1, NULL, 0);
        break;
      }
      uint8_t off = pl[0];
      if (off > 224) {
        sendAck(cmd, seq, 2, NULL, 0);
        break;
      }
      sendAck(cmd, seq, 0, lut + off, 32);
      break;
    }
    case CMD_SET_LUT: {
      if (n < 33) {
        sendAck(cmd, seq, 1, NULL, 0);
        break;
      }
      uint8_t off = pl[0];
      if (off > 224) {
        sendAck(cmd, seq, 2, NULL, 0);
        break;
      }
      memcpy(lut + off, pl + 1, 32);
      sendAck(cmd, seq, 0, NULL, 0);
      break;
    }
    case CMD_RESTORE:
      lutDefaults();
      scanBaud = 115200;
      scanParity = 0;
      scanStop = 1;
      interCharMs = 5;
      applyScannerUart();
      sendAck(cmd, seq, 0, NULL, 0);
      break;
    case CMD_COMMIT:
      eepromSave();
      sendAck(cmd, seq, 0, NULL, 0);
      break;
    default:
      sendAck(cmd, seq, 3, NULL, 0);
      break;
  }
}

static void pollConfig() {
  static uint8_t acc[64];
  static uint8_t have = 0;
  while (Serial.available() > 0) {
    uint8_t b = (uint8_t)Serial.read();
    if (have == 0 && b != 0xA5) {
      continue;
    }
    if (have == 1 && b != 0x5A) {
      have = (b == 0xA5) ? 1 : 0;
      if (have) {
        acc[0] = 0xA5;
      }
      continue;
    }
    acc[have++] = b;
    if (have == 64) {
      handleFrame(acc);
      have = 0;
    }
  }
}

void setup() {
  lutDefaults();
  eepromLoad();
  Serial.begin(CFG_BAUD);
  applyScannerUart();
  Keyboard.begin();
}

void loop() {
  pollConfig();

  // Copy IRQ RX into the 3 KB burst buffer. Never delay() here: a 5 ms stall
  // overflows the core USART FIFO (64–1024 B) and drops the PDF417 payload.
  while (Serial2.available() > 0) {
    if (!pushByte((uint8_t)Serial2.read())) {
      break;
    }
    lastRxMs = millis();
  }

  if (configMode) {
    return;
  }

  if (head == tail) {
    return;
  }
  // Wait until the UART burst is idle so HID USB waits cannot overrun RX.
  if ((millis() - lastRxMs) < UART_IDLE_MS) {
    return;
  }
  if (interCharMs > 0 && lastKeyMs != 0 && (millis() - lastKeyMs) < interCharMs) {
    return;
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
  lastKeyMs = millis();
}
