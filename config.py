import json
import os
from datetime import datetime

class Config:
    def __init__(self, config_file="tts_config.json"):
        self.config_file = config_file
        self.default_config = {
            "voice": "zh-CN-XiaoxiaoNeural",
            "max_workers": 8,
            "history": []
        }
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.default_config.copy()
        return self.default_config.copy()
    
    def save_config(self):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def add_history(self, text, voice, sentences_count):
        """添加历史记录"""
        history_item = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": text[:100] + "..." if len(text) > 100 else text,
            "voice": voice,
            "sentences_count": sentences_count
        }
        
        self.config["history"].insert(0, history_item)
        # 只保留最近20条记录
        self.config["history"] = self.config["history"][:20]
        self.save_config()
    
    def clear_history(self):
        """清空历史记录"""
        self.config["history"] = []
        self.save_config()
    
    def get_last_settings(self):
        """获取上次设置"""
        return {
            "voice": self.config.get("voice", "zh-CN-XiaoxiaoNeural"),
            "max_workers": self.config.get("max_workers", 8)
        }
    
    def update_settings(self, voice, max_workers):
        """更新设置"""
        self.config["voice"] = voice
        self.config["max_workers"] = max_workers
        self.save_config()