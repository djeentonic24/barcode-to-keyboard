// ESP32 fake barcode scanner.
// TX = GPIO17 -> STM32 USART2_RX (PA3). Common GND.
// USB on ESP is only for power / serial monitor.

static const int SCANNER_TX = 17;
static const int SCANNER_RX = 16;  // unused, but keep UART2 complete
static const uint32_t BAUD = 115200;

static const uint8_t SAMPLE[] = {
    '@', '\n', 0x1E, '\r',
    'A', 'N', 'S', 'I', ' ', '6', '3', '6', '0', '0', '0', '0', '9',
    '\n', 'D', 'C', 'S', 'D', 'O', 'E',
    '\n', 'D', 'A', 'C', 'J', 'O', 'H', 'N',
    '\n', 'D', 'A', 'G', '1', '2', '3', ' ', 'M', 'A', 'I', 'N',
    0x1D, 'Z', 'V', '\r'};

void setup() {
  Serial.begin(115200);
  Serial2.begin(BAUD, SERIAL_8N1, SCANNER_RX, SCANNER_TX);
  delay(500);
  Serial.println("ESP scanner sim ready. Sending every 3s.");
}

void loop() {
  Serial2.write(SAMPLE, sizeof(SAMPLE));
  Serial2.flush();
  Serial.printf("sent %u bytes\n", (unsigned)sizeof(SAMPLE));
  delay(3000);
}
