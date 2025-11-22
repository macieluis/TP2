# 🚀 TP2 - Simulação de Missão Espacial (Comunicações por Computador)

Este projeto simula um sistema de comunicação distribuído entre uma **Nave-Mãe** e vários **Rovers** numa missão planetária. O objetivo é demonstrar a implementação de protocolos aplicacionais fiáveis sobre UDP e monitorização contínua sobre TCP.

O sistema é composto por quatro componentes principais:
1.  **MissionLink (UDP):** Protocolo fiável (com retransmissões e ACKs) para envio de missões e comandos críticos.
2.  **TelemetryStream (TCP):** Protocolo para envio contínuo de estado (bateria, posição, velocidade).
3.  **API de Observação (HTTP/Flask):** Interface centralizada para monitorização e comando externo.
4.  **Ground Control (Web):** Interface gráfica para o operador controlar a frota e visualizar o progresso.

---

## 🛠️ Pré-requisitos e Instalação

O projeto utiliza **Python 3** e requer um ambiente virtual para gerir as dependências (`flask`, `flask-cors`).

### 1. Configurar o Ambiente (Apenas na primeira vez)

Abre um terminal na pasta raiz do projeto e executa:

```bash
# 1. Criar o ambiente virtual
python3 -m venv venv

# 2. Ativar o ambiente (Mac/Linux)
source venv/bin/activate
# (No Windows seria: venv\Scripts\activate)

# 3. Instalar dependências
pip install flask flask-cors

Rodar o Projeto (Modo Local):
--

Terminal 1: Nave-Mãe (Servidor):
(venv) python3 navemae/main.py
--

Terminal 2-5: Rover (Cliente/Clientes)
(venv) python3 rover/main.py
e escolher os determinados rovers
--

Terminal 3: Ground Control (Interface Web)
cd ground_control
python3 -m http.server 8001

hospedado em http://127.0.0.1:8001
--
