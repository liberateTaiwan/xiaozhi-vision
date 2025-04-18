# 简单的会话状态管理

class SessionManager:
    def __init__(self):
        self.sessions = {}
    
    def get_session(self, session_id):
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "mode": "normal",  # normal, waiting_for_name
                "temp_audio_path": None,
            }
        return self.sessions[session_id]
    
    def clear_session(self, session_id):
        """清除会话数据"""
        if session_id in self.sessions:
            del self.sessions[session_id]

# 创建全局会话管理器实例
session_manager = SessionManager() 