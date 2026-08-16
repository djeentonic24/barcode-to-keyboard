# Config protocol (F4VE USART1 / future HID Feature Reports)

Same 64-byte payload on both transports. This Linux stand uses **USART1 on F4VE J6** at **115200 8N1** as the equivalent of USB HID Feature Reports on NUCLEO-C071RB.

Mode 1 (keyboard) and Mode 2 (config) do not run at once. `CMD_ENTER` pauses HID typing; `CMD_EXIT` resumes it.

## Frame (64 bytes)

| Offset | Size | Field |
|--------|------|--------|
| 0 | 2 | Magic `A5 5A` |
| 2 | 1 | Command |
| 3 | 1 | Sequence (echoed in ACK) |
| 4 | 1 | Payload length `n` (0–56) |
| 5 | `n` | Payload |
| 5+n … 61 | | Zero pad |
| 62 | 2 | CRC-16/MODBUS (poly `0xA001`, init `0xFFFF`) over bytes 0–61, little-endian |

## Commands

Host → device. ACK is `cmd | 0x80`. ACK payload always starts with a status byte (`0` = OK).

| cmd | Name | Request payload | ACK payload after status |
|-----|------|-----------------|--------------------------|
| 1 | PING | empty | `BKCFG` |
| 2 | ENTER | empty | empty |
| 3 | EXIT | empty | empty |
| 4 | GET_UART | empty | `u32le baud`, `u8 parity`, `u8 stop`, `u8 delay_ms` |
| 5 | SET_UART | same 7 bytes | empty |
| 6 | GET_LUT | `u8 offset` (0, 32, …, 224) | 32 LUT bytes |
| 7 | SET_LUT | `u8 offset` + 32 bytes | empty |
| 8 | RESTORE | empty | empty (RAM only) |
| 9 | COMMIT | empty | empty (writes internal Flash / EEPROM emulation) |

Parity: `0` none, `1` even, `2` odd. Stop bits: `1` or `2`. Baud: 9600–115200. Delay: 0–20 ms.

`RESTORE` reloads Appendix A defaults in RAM. `COMMIT` persists UART + LUT across reset.

## Host flow

1. PING → ENTER  
2. GET_UART / GET_LUT (Read Settings)  
3. SET_UART / SET_LUT (optional) → COMMIT (Save to Device)  
4. EXIT (Return to keyboard)
