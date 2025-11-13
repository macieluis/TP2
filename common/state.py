import os, struct, threading

COUNTER_FILE = "navemae/data/mission_counter.bin"
_lock = threading.Lock()

def _ensure_dir():
    os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)

def _read_counter():
    """Lê o contador binário do disco."""
    if not os.path.exists(COUNTER_FILE):
        return 0
    with open(COUNTER_FILE, "rb") as f:
        data = f.read(4)
        return struct.unpack(">I", data)[0]  # inteiro 4 bytes, big-endian

def _write_counter(value):
    """Guarda o contador em formato binário (4 bytes)."""
    _ensure_dir()
    with open(COUNTER_FILE, "wb") as f:
        f.write(struct.pack(">I", value))

def get_next_mission_id():
    """Incrementa e devolve o próximo ID de missão persistente."""
    with _lock:
        value = _read_counter() + 1
        _write_counter(value)
        return f"M-{value:03d}"
