import pyaudio
import queue
import serial
import modbus_tk.defines as cst
import modbus_tk.modbus_rtu as modbus_rtu
from aip import AipSpeech

# 百度平台的认证信息
APP_ID = '73843967'
API_KEY = 'HXQNLvDgmlEgm0erdxeNivB4'
SECRET_KEY = 'UtSKS2TVcjp1ZBVy1txmc6IhrO1d86U7'

# 音频录制的参数
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 3
RELAY_PORT = 'COM3'
RELAY_RESPONSE_TIMEOUT = 5.0

# 创建命令队列
commands_queue = queue.Queue()

# 初始化百度语音识别客户端
client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)

# 连接到继电器模块的串口
def connect_relay(port):
    try:
        # 初始化Modbus RTU主站
        master = modbus_rtu.RtuMaster(serial.Serial(port=port, baudrate=9600, bytesize=8, parity='E', stopbits=1))
        master.set_timeout(RELAY_RESPONSE_TIMEOUT)
        return 1, master
    except Exception as exc:
        print("Error opening serial port:", str(exc))
        return -1, None

# 录制音频
def record_audio():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print("开始录音")
    frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * RECORD_SECONDS))]
    print("录音结束")
    stream.stop_stream()
    stream.close()
    p.terminate()
    return b''.join(frames)

# 语音识别
def recognize_audio(audio_data):
    result = client.asr(audio_data, 'pcm', 16000, {'dev_pid': 1537})  # 1537为普通话输入法模型
    if 'result' in result and len(result['result']) > 0:
        command = result['result'][0]
        print(f"识别结果: {command}")
        return command
    else:
        print("未能识别语音")
        return ""

# 实时识别语音并放入命令队列
def recognize_realtime():
    while True:
        audio_data = record_audio()
        command = recognize_audio(audio_data)
        if command and ("打开" in command or "开启" in command or "关闭" in command or "风扇" in command or "终止" in command):
            commands_queue.put(command)
        print("按下回车键开始下次录制")
        input()

# 执行队列中的命令，控制继电器
def execute_commands():
    _, relay_master = connect_relay(RELAY_PORT)
    if relay_master is None:
        return
    while True:
        if not commands_queue.empty():
            command = commands_queue.get()
            if command and ("打开" in command or "开启" in command or "关闭" in command or "风扇" in command or "终止" in command):
                switch(relay_master, command)

# 根据语音指令控制开关
def switch(master, action):
    try:
        if "开" in action.lower():
            master.execute(2, cst.WRITE_SINGLE_COIL, 0, output_value=True)
            print("风扇已打开")
        elif "关" in action.lower():
            master.execute(2, cst.WRITE_SINGLE_COIL, 0, output_value=False)
            print("风扇已关闭")
    except Exception as exc:
        print(str(exc))

# 主程序入口
if __name__ == "__main__":
    import threading
    # 创建两个线程，分别实时识别语音和执行命令
    recognize_thread = threading.Thread(target=recognize_realtime)
    execute_thread = threading.Thread(target=execute_commands)
    recognize_thread.start()
    execute_thread.start()
