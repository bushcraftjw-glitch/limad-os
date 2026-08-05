from __future__ import annotations

SBOX = (
0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16)
INV_SBOX = [0] * 256
for i, v in enumerate(SBOX):
    INV_SBOX[v] = i


def _xtime(value: int) -> int:
    return ((value << 1) ^ (0x11B if value & 0x80 else 0)) & 0xFF


def _mul(a: int, b: int) -> int:
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        high = a & 0x80
        a = (a << 1) & 0xFF
        if high:
            a ^= 0x1B
        b >>= 1
    return result


def _expand_key(key: bytes) -> list[int]:
    if len(key) != 16:
        raise ValueError("AES-128 erwartet 16 Byte Schlüssel.")
    expanded = list(key)
    generated = 16
    rcon = 1
    while generated < 176:
        temp = expanded[-4:]
        if generated % 16 == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[x] for x in temp]
            temp[0] ^= rcon
            rcon = _xtime(rcon)
        for i in range(4):
            expanded.append(expanded[generated - 16] ^ temp[i])
            generated += 1
    return expanded


def _add_round_key(state: list[int], expanded: list[int], round_index: int) -> None:
    offset = round_index * 16
    for i in range(16):
        state[i] ^= expanded[offset + i]


def _inv_shift_rows(state: list[int]) -> None:
    row1 = [state[1], state[5], state[9], state[13]]
    row2 = [state[2], state[6], state[10], state[14]]
    row3 = [state[3], state[7], state[11], state[15]]
    row1 = row1[-1:] + row1[:-1]
    row2 = row2[-2:] + row2[:-2]
    row3 = row3[-3:] + row3[:-3]
    state[1], state[5], state[9], state[13] = row1
    state[2], state[6], state[10], state[14] = row2
    state[3], state[7], state[11], state[15] = row3


def _inv_sub_bytes(state: list[int]) -> None:
    for i in range(16):
        state[i] = INV_SBOX[state[i]]


def _inv_mix_columns(state: list[int]) -> None:
    for column in range(4):
        i = column * 4
        a0, a1, a2, a3 = state[i:i + 4]
        state[i] = _mul(a0, 14) ^ _mul(a1, 11) ^ _mul(a2, 13) ^ _mul(a3, 9)
        state[i + 1] = _mul(a0, 9) ^ _mul(a1, 14) ^ _mul(a2, 11) ^ _mul(a3, 13)
        state[i + 2] = _mul(a0, 13) ^ _mul(a1, 9) ^ _mul(a2, 14) ^ _mul(a3, 11)
        state[i + 3] = _mul(a0, 11) ^ _mul(a1, 13) ^ _mul(a2, 9) ^ _mul(a3, 14)


def decrypt_block(block: bytes, key: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError("AES-Block muss 16 Byte lang sein.")
    state = list(block)
    expanded = _expand_key(key)
    _add_round_key(state, expanded, 10)
    for round_index in range(9, 0, -1):
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
        _add_round_key(state, expanded, round_index)
        _inv_mix_columns(state)
    _inv_shift_rows(state)
    _inv_sub_bytes(state)
    _add_round_key(state, expanded, 0)
    return bytes(state)


def decrypt_cbc(data: bytes, key: bytes, iv: bytes) -> bytes:
    if len(data) % 16:
        raise ValueError("AES-CBC-Datenlänge ist kein Vielfaches von 16.")
    if len(iv) != 16:
        raise ValueError("AES-CBC-IV muss 16 Byte lang sein.")

    # JWPUB-Dateien können viele Megabyte verschlüsselte HTML-Blöcke enthalten.
    # Die ursprüngliche reine Python-Implementierung ist korrekt, aber auf großen
    # Publikationen sehr langsam. Nutze deshalb OpenSSL über python-cryptography,
    # sofern es auf dem System vorhanden ist. Der portable Python-Code bleibt als
    # Rückfallweg erhalten.
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return decryptor.update(data) + decryptor.finalize()
    except (ImportError, ModuleNotFoundError):
        pass

    # Auf LiMaD/Bazzite ist OpenSSL systemweit vorhanden. Dieser zweite
    # beschleunigte Weg verhindert, dass ein großer Studienleitfaden beim
    # ersten Import minutenlang in der portablen Python-Routine hängt.
    try:
        import subprocess
        completed = subprocess.run(
            ["openssl", "enc", "-d", "-aes-128-cbc", "-nopad", "-K", key.hex(), "-iv", iv.hex()],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=120,
        )
        return completed.stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    result = bytearray()
    previous = iv
    expanded = _expand_key(key)
    for offset in range(0, len(data), 16):
        block = data[offset:offset + 16]
        state = list(block)
        _add_round_key(state, expanded, 10)
        for round_index in range(9, 0, -1):
            _inv_shift_rows(state)
            _inv_sub_bytes(state)
            _add_round_key(state, expanded, round_index)
            _inv_mix_columns(state)
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
        _add_round_key(state, expanded, 0)
        plain = bytes(state)
        result.extend(a ^ b for a, b in zip(plain, previous))
        previous = block
    return bytes(result)
