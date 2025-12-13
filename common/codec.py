import struct
import pickle  

# Header: version (B), msg_type (B), action (B), seq (H), length (H), checksum (B)
HEADER_FMT = "!BBBHHB"

HEADER_SIZE = struct.calcsize(HEADER_FMT)

def encode_msg(version, msg_type, action, seq, payload):
    """Codifica uma mensagem com header e payload."""
    
    # 1. Serializar o dicionário diretamente para bytes binários
    body = pickle.dumps(payload)
    
    
    length = len(body)
    checksum = sum(body) % 256

    header = struct.pack(HEADER_FMT, version, msg_type, action, seq, length, checksum)
    
    # Retorna: Bytes do Header + Bytes do Payload (Binário)
    return header + body


def decode_msg(packet):
    """Decodifica uma mensagem recebida em bytes."""
    
    if len(packet) < HEADER_SIZE:
        # Se não tiver dados suficientes, retorna None ou levanta erro
        # (Ajustado para ser mais seguro em streams TCP)
        return None

    header = packet[:HEADER_SIZE]
    # Nota: No TCP, o resto pode não ter chegado ainda, mas 
    # a lógica de leitura no server já trata disso usando o 'length'
    
    version, msg_type, action, seq, length, checksum = struct.unpack(HEADER_FMT, header)
    
    # Verificar se temos o pacote completo
    if len(packet) < HEADER_SIZE + length:
        return None # Pacote incompleto

    payload_data = packet[HEADER_SIZE : HEADER_SIZE + length]

    if sum(payload_data) % 256 != checksum:
        raise ValueError("Checksum inválido")
    

    # 2. Deserializar os bytes binários de volta para dicionário
    try:
        data = pickle.loads(payload_data)
    except Exception as e:
        
        raise ValueError(f"Erro ao descodificar payload binário: {e}")

    return {
        "version": version,
        "msg_type": msg_type,
        "action": action,
        "seq": seq,
        "payload": data,
        "bytes_consumed": HEADER_SIZE + length # Ajuda no TCP stream
    }