#pragma once

#include <stdint.h>

#define SETTINGS_MAGIC 0x31474C42UL /* BLG1 */
#define SETTINGS_VER 1

#pragma pack(push, 1)
typedef struct {
  uint32_t magic;
  uint16_t version;
  uint32_t baud;
  uint8_t parity;
  uint8_t stop;
  uint8_t delayMs;
  uint8_t lut[256];
  uint32_t crc;
} Persist;
#pragma pack(pop)
