import asyncio
import websockets
from config.logger import setup_logging
from core.connection import ConnectionHandler
from core.handle.musicHandler import MusicHandler
from core.utils.util import get_local_ip
from core.utils import asr, vad, llm, tts

TAG = __name__


class WebSocketServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self._vad, self._asr, self._llm, self._tts, self._music = self._create_processing_instances()
        self.active_connections = set()  # 添加全局连接记录
        self.sessions = {}  # 用于存储会话状态
        self.voice_command_handler = None

    def _create_processing_instances(self):
        """创建处理模块实例"""
        return (
            vad.create_instance(
                self.config["selected_module"]["VAD"],
                self.config["VAD"][self.config["selected_module"]["VAD"]]
            ),
            asr.create_instance(
                self.config["selected_module"]["ASR"]
                if not 'type' in self.config["ASR"][self.config["selected_module"]["ASR"]]
                else
                self.config["ASR"][self.config["selected_module"]["ASR"]]["type"],
                self.config["ASR"][self.config["selected_module"]["ASR"]],
                self.config["delete_audio"]
            ),
            llm.create_instance(
                self.config["selected_module"]["LLM"]
                if not 'type' in self.config["LLM"][self.config["selected_module"]["LLM"]]
                else
                self.config["LLM"][self.config["selected_module"]["LLM"]]['type'],
                self.config["LLM"][self.config["selected_module"]["LLM"]],
            ),
            tts.create_instance(
                self.config["selected_module"]["TTS"]
                if not 'type' in self.config["TTS"][self.config["selected_module"]["TTS"]]
                else
                self.config["TTS"][self.config["selected_module"]["TTS"]]["type"],
                self.config["TTS"][self.config["selected_module"]["TTS"]],
                self.config["delete_audio"]
            ),
            MusicHandler(self.config)
        )

    async def start(self):
        server_config = self.config["server"]
        host = server_config["ip"]
        port = server_config["port"]

        self.logger.bind(tag=TAG).info("Server is running at ws://{}:{}", get_local_ip(), port)
        self.logger.bind(tag=TAG).info("=======上面的地址是websocket协议地址，请勿用浏览器访问=======")
        async with websockets.serve(
                self._handle_connection,
                host,
                port
        ):
            await asyncio.Future()

    async def _handle_connection(self, websocket):
        """处理新连接，每次创建独立的ConnectionHandler"""
        # 创建ConnectionHandler时传入当前server实例
        handler = ConnectionHandler(self.config, self._vad, self._asr, self._llm, self._tts, self._music)
        self.active_connections.add(handler)
        try:
            await handler.handle_connection(websocket)
        finally:
            self.active_connections.discard(handler)

    def register_voice_command_handler(self, handler):
        """注册声纹命令处理函数"""
        self.voice_command_handler = handler
    
    def get_session(self, session_id):
        """获取或创建会话状态"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "mode": "normal",  # normal, waiting_for_name
                "temp_audio_path": None,
            }
        return self.sessions[session_id]
    
    async def handle_message(self, websocket, message):
        # 获取会话ID和会话状态
        session_id = message.get("session_id", "default")
        session_state = self.get_session(session_id)
        
        # 如果是语音输入，先检查是否是特殊命令
        if message.get("type") == "audio" and self.voice_command_handler:
            audio_data = message.get("audio")
            text = message.get("text")  # 假设已经有ASR转换的文本
            
            # 调用声纹命令处理函数
            result = await self.voice_command_handler(
                text, 
                audio_data, 
                self._llm,  # 假设WebSocketServer有llm属性
                self._tts,  # 假设WebSocketServer有tts属性
                session_state
            )
            
            if result:
                # 如果是特殊命令，直接返回结果
                await websocket.send_json(result)
                return
        
        # 正常的消息处理流程
        # ... existing code ...
