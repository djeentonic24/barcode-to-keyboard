// ESP32 fake PDF417 scanner: UART to STM32 + ST7789 preview of the real PDF417.
// GPIO17 TX -> STM PA3. TFT: D18 SCK, D23 MOSI, D22 RES, D21 DC, D32 BLK, 3V3.

#include "aamva_payload.h"
#include "pdf417_bitmap.h"
#include "st7789_240.h"

static const int SCANNER_TX = 17;
static const int SCANNER_RX = 16;
static const int BOOT_BTN = 0;
static const int TFT_SCK = 18;
static const int TFT_MOSI = 23;
static const int TFT_RES = 22;
static const int TFT_DC = 21;
static const int TFT_BLK = 32;
static const uint32_t BAUD = 115200;

static const uint16_t COL_BG = 0xFFFF;
static const uint16_t COL_FG = 0x0000;

static St7789 tft(TFT_SCK, TFT_MOSI, TFT_DC, TFT_RES, TFT_BLK);
static bool btnWasUp = true;
static uint32_t scanCount = 0;

static bool aamvaField(const char *tag, char *out, size_t outLen) {
  const size_t tagLen = strlen(tag);
  const uint8_t *data = AAMVA_PAYLOAD;
  const size_t n = AAMVA_PAYLOAD_LEN;
  for (size_t i = 0; i + tagLen < n; ++i) {
    if (memcmp(data + i, tag, tagLen) != 0) {
      continue;
    }
    const uint8_t prev = i ? data[i - 1] : 0;
    const bool afterDl = i >= 2 && prev == 'L' && data[i - 2] == 'D';
    const bool delim = (i == 0) || prev == '\n' || prev == '\r' || prev == 0x1C ||
                       prev == 0x1D || prev == 0x1E || prev == 0x1F || prev == '@' ||
                       afterDl;
    if (!delim) {
      continue;
    }
    size_t o = 0;
    for (size_t j = i + tagLen; j < n && o + 1 < outLen; ++j) {
      uint8_t c = data[j];
      if (c == '\n' || c == '\r' || c == 0x1C || c == 0x1D || c == 0x1E ||
          c == 0x1F) {
        break;
      }
      if (c >= 0x20 && c <= 0x7E) {
        out[o++] = (char)c;
      }
    }
    out[o] = 0;
    return o > 0;
  }
  out[0] = 0;
  return false;
}

static void drawScreen(bool sent) {
  tft.fill(COL_BG);
  tft.text5x7(8, 6, "AAMVA PDF417", COL_FG, COL_BG);
  tft.text5x7(8, 16, sent ? "UART -> STM  SENT" : "BOOT or GUI = scan", COL_FG,
              COL_BG);

  const int sx = 1;
  const int sy = 5;
  const int16_t bw = (int16_t)(PDF417_WIDTH * sx);
  const int16_t bh = (int16_t)(PDF417_HEIGHT * sy);
  const int16_t bx = (int16_t)((240 - bw) / 2);
  const int16_t by = 30;
  tft.fillRect(bx - 4, by - 4, bw + 8, bh + 8, COL_FG);
  tft.fillRect(bx - 2, by - 2, bw + 4, bh + 4, COL_BG);
  tft.blitMono(bx, by, PDF417_WIDTH, PDF417_HEIGHT, PDF417_STRIDE, PDF417_BITS,
               sx, sy, COL_FG, COL_BG);

  char last[24], first[24], dl[24], line[42];
  aamvaField("DCS", last, sizeof(last));
  aamvaField("DAC", first, sizeof(first));
  aamvaField("DAQ", dl, sizeof(dl));
  snprintf(line, sizeof(line), "%s %s", first, last);
  tft.text5x7(8, 168, line, COL_FG, COL_BG);
  snprintf(line, sizeof(line), "DL %s", dl);
  tft.text5x7(8, 180, line, COL_FG, COL_BG);
  snprintf(line, sizeof(line), "%u bytes  scan %lu", AAMVA_PAYLOAD_LEN,
           (unsigned long)scanCount);
  tft.text5x7(8, 192, line, COL_FG, COL_BG);
  tft.text5x7(8, 216, "GPIO17 -> STM PA3", COL_FG, COL_BG);
}

static void sendScan() {
  ++scanCount;
  Serial2.write(AAMVA_PAYLOAD, AAMVA_PAYLOAD_LEN);
  Serial2.flush();
  Serial.printf("scan %u bytes on GPIO17 -> STM PA3\n", AAMVA_PAYLOAD_LEN);
  drawScreen(true);
}

void setup() {
  pinMode(BOOT_BTN, INPUT_PULLUP);
  Serial.begin(115200);
  Serial2.begin(BAUD, SERIAL_8N1, SCANNER_RX, SCANNER_TX);
  tft.begin();
  drawScreen(false);
  Serial.println("ESP scanner + ST7789 ready.");
  Serial.println("Trigger: BOOT or send 's'.");
}

void loop() {
  bool up = digitalRead(BOOT_BTN) == HIGH;
  if (btnWasUp && !up) {
    delay(30);
    if (digitalRead(BOOT_BTN) == LOW) {
      sendScan();
      while (digitalRead(BOOT_BTN) == LOW) {
        delay(10);
      }
    }
  }
  btnWasUp = up;

  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == 's' || c == 'S' || c == '\n' || c == '\r') {
      sendScan();
      while (Serial.available() > 0) {
        (void)Serial.read();
      }
      break;
    }
  }
}
