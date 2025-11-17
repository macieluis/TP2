# common/codec.py
import struct
import json

# Header: version (B), msg_type (B), action (B), seq (H), length (H), checksum (B)
HEADER_FMT = "!BBBHHB"
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def encode_msg(version, msg_type, action, seq, payload):
    body = json.dumps(payload).encode("utf-8")
    length = len(body)              # <-- agora é o tamanho REAL (uint16)
    checksum = sum(body) % 256

    header = struct.pack(HEADER_FMT, version, msg_type, action, seq, length, checksum)
    return header + body


def decode_msg(packet):
    if len(packet) < HEADER_SIZE:
        raise ValueError("Pacote demasiado pequeno para header")

    header = packet[:HEADER_SIZE]
    payload = packet[HEADER_SIZE:]

    version, msg_type, action, seq, length, checksum = struct.unpack(HEADER_FMT, header)

    if len(payload) != length:
        raise ValueError(f"Comprimento inválido (esperado {length}, recebido {len(payload)})")

    if sum(payload) % 256 != checksum:
        raise ValueError("Checksum inválido")

    data = json.loads(payload.decode("utf-8"))
    return {
        "version": version,
        "msg_type": msg_type,
        "action": action,
        "seq": seq,
        "payload": data,
    }

