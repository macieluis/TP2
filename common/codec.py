import struct, json

def encode_msg(version, msg_type, action, seq, payload):
    body = json.dumps(payload).encode("utf-8")
    length = len(body) % 256
    checksum = sum(body) % 256
    header = struct.pack("!BBBHBBB", version, msg_type, action, seq >> 8, seq & 0xFF, length, checksum)
    return header + body

def decode_msg(packet):
    header = packet[:8]
    payload = packet[8:]
    version, msg_type, action, seq_hi, seq_lo, length, checksum = struct.unpack("!BBBHBBB", header)
    seq = (seq_hi << 8) | seq_lo
    if sum(payload) % 256 != checksum:
        raise ValueError("Checksum inválido")
    data = json.loads(payload.decode("utf-8"))
    return {
        "version": version,
        "msg_type": msg_type,
        "action": action,
        "seq": seq,
        "payload": data
    }

