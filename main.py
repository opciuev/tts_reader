import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pygame
import edge_tts
import asyncio
import threading
import tempfile
import os
import shutil
import re
from datetime import datetime
from config import Config

class TTSReader:
    def __init__(self, root):
        self.root = root
        self.config = Config()
        
        # 从配置文件加载设置
        last_settings = self.config.get_last_settings()
        self.voice = last_settings["voice"]
        self.max_workers = last_settings["max_workers"]
        
        self.root.title("TTS文本朗读器")
        self.root.geometry("800x600")
        
        # 初始化pygame音频
        pygame.mixer.init()
        
        # 状态变量
        self.sentences = []
        self.audio_files = []  # 存储每句对应的音频文件
        self.current_sentence = 0
        self.is_playing = False
        self.is_paused = False
        self.is_converted = False  # 是否已转换
        self.is_converting = False  # 是否正在转换
        self.temp_files = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 控制区域
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0,10))
        
        # 语音选择
        ttk.Label(control_frame, text="语音:").pack(side=tk.LEFT)
        self.voice_var = tk.StringVar(value=self.voice)
        voice_combo = ttk.Combobox(control_frame, textvariable=self.voice_var, width=30)
        voice_combo['values'] = [
            # 中文语音
            "zh-CN-XiaoxiaoNeural",
            "zh-CN-YunyeNeural", 
            "zh-CN-YunjianNeural",
            "zh-CN-XiaoyiNeural",
            "zh-CN-YunxiNeural",
            "zh-CN-XiaochenNeural",
            "zh-CN-XiaohanNeural",
            "zh-CN-XiaomengNeural",
            "zh-CN-XiaomoNeural",
            "zh-CN-XiaoqiuNeural",
            "zh-CN-XiaoruiNeural",
            "zh-CN-XiaoshuangNeural",
            "zh-CN-XiaoxuanNeural",
            "zh-CN-XiaoyanNeural",
            "zh-CN-XiaoyouNeural",
            "zh-CN-XiaozhenNeural",
            # 日文语音
            "ja-JP-NanamiNeural",
            "ja-JP-KeitaNeural",
            "ja-JP-AoiNeural",
            "ja-JP-DaichiNeural",
            "ja-JP-MayuNeural",
            "ja-JP-NaokiNeural",
            "ja-JP-ShioriNeural",
            # 英文语音
            "en-US-AriaNeural",
            "en-US-JennyNeural",
            "en-US-GuyNeural",
            "en-US-DavisNeural",
            "en-US-AmberNeural",
            "en-US-AnaNeural",
            "en-US-AndrewNeural",
            "en-US-EmmaNeural",
            "en-US-BrianNeural",
            "en-US-ChristopherNeural",
            "en-US-ElizabethNeural",
            "en-US-EricNeural",
            "en-US-JacobNeural",
            "en-US-JaneNeural",
            "en-US-JasonNeural",
            "en-US-MichelleNeural",
            "en-US-MonicaNeural",
            "en-US-NancyNeural",
            "en-US-RogerNeural",
            "en-US-SaraNeural",
            "en-US-SteffanNeural",
            "en-US-TonyNeural"
        ]
        voice_combo.pack(side=tk.LEFT, padx=(5,10))
        voice_combo.bind('<<ComboboxSelected>>', self.on_voice_change)
        
        # 线程数设置
        ttk.Label(control_frame, text="线程数:").pack(side=tk.LEFT, padx=(10,0))
        self.thread_var = tk.StringVar(value=str(self.max_workers))
        thread_spinbox = tk.Spinbox(control_frame, from_=1, to=16, width=3, textvariable=self.thread_var)
        thread_spinbox.pack(side=tk.LEFT, padx=(5,0))
        
        # 历史记录按钮
        history_btn = ttk.Button(control_frame, text="历史记录", command=self.show_history)
        history_btn.pack(side=tk.LEFT, padx=(10,5))
        
        clear_history_btn = ttk.Button(control_frame, text="清空历史", command=self.clear_history)
        clear_history_btn.pack(side=tk.LEFT, padx=(5,0))
        
        # 第一行按钮
        button_frame1 = ttk.Frame(main_frame)
        button_frame1.pack(fill=tk.X, pady=(0,5))
        
        # 剪贴板按钮
        ttk.Button(button_frame1, text="读取剪贴板", command=self.read_clipboard).pack(side=tk.LEFT, padx=(0,5))
        
        # 转换按钮
        self.convert_btn = ttk.Button(button_frame1, text="开始转换", command=self.convert_text)
        self.convert_btn.pack(side=tk.LEFT, padx=(0,5))
        
        # 保存音频按钮
        self.save_btn = ttk.Button(button_frame1, text="保存音频", command=self.save_audio, state="disabled")
        self.save_btn.pack(side=tk.LEFT, padx=(0,5))
        
        # 第二行按钮 - 播放控制
        button_frame2 = ttk.Frame(main_frame)
        button_frame2.pack(fill=tk.X, pady=(0,10))
        
        # 播放控制按钮
        self.play_btn = ttk.Button(button_frame2, text="播放", command=self.play_all, state="disabled")
        self.play_btn.pack(side=tk.LEFT, padx=(0,5))
        
        self.pause_btn = ttk.Button(button_frame2, text="暂停", command=self.pause_play, state="disabled")
        self.pause_btn.pack(side=tk.LEFT, padx=(0,5))
        
        self.stop_btn = ttk.Button(button_frame2, text="停止", command=self.stop_play, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=(0,5))
        
        # 状态显示
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0,10))
        
        self.status_label = ttk.Label(status_frame, text="状态: 就绪")
        self.status_label.pack(side=tk.LEFT)
        
        self.progress_label = ttk.Label(status_frame, text="进度: 0/0")
        self.progress_label.pack(side=tk.RIGHT)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0,10))
        
        # 文本区域
        text_frame = ttk.LabelFrame(main_frame, text="文本内容", padding="5")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建文本框和滚动条
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=tk.BOTH, expand=True)
        
        self.text_widget = tk.Text(text_container, wrap=tk.WORD, font=("微软雅黑", 12))
        scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 配置文本高亮标签
        self.text_widget.tag_configure("current", background="yellow", foreground="black")
        self.text_widget.tag_configure("completed", background="lightgreen", foreground="black")
        self.text_widget.tag_configure("converted", background="lightblue", foreground="black")
        self.text_widget.tag_configure("clickable", foreground="blue", underline=True)
        
        # 绑定文本点击事件和文本变化事件
        self.text_widget.bind("<Button-1>", self.on_text_click)
        self.text_widget.bind("<Motion>", self.on_text_hover)
        self.text_widget.bind("<KeyRelease>", self.on_text_change)
        # 移除ButtonRelease绑定，避免点击时误触发
    
    def format_rate_value(self):
        """格式化语速值"""
        try:
            value = int(float(self.rate_var.get().replace('%', '')))
            self.rate_var.set(f"{value}%")
        except:
            self.rate_var.set("0%")
    
    def format_volume_value(self):
        """格式化音量值"""
        try:
            value = int(float(self.volume_var.get().replace('%', '')))
            self.volume_var.set(f"{value}%")
        except:
            self.volume_var.set("0%")
    
    def format_pitch_value(self):
        """格式化音调值"""
        try:
            value = int(float(self.pitch_var.get().replace('Hz', '')))
            self.pitch_var.set(f"{value}Hz")
        except:
            self.pitch_var.set("0Hz")
    
    def on_text_change(self, event=None):
        """文本内容改变时的处理"""
        # 防止在处理过程中重复触发
        if hasattr(self, '_processing_text_change') and self._processing_text_change:
            return
        
        self._processing_text_change = True
        
        try:
            # 自动分割句子
            self.split_sentences()
            # 如果已经转换过，重置转换状态
            if self.is_converted:
                self.reset_conversion_state()
                self.status_label.config(text="状态: 文本已更改，需重新转换")
        finally:
            # 延迟重置标志，避免连续触发
            self.root.after(100, lambda: setattr(self, '_processing_text_change', False))
    
    def read_clipboard(self):
        """读取剪贴板内容"""
        try:
            clipboard_text = self.root.clipboard_get()
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.insert(1.0, clipboard_text)
            self.split_sentences()
            self.reset_conversion_state()
            self.status_label.config(text="状态: 已读取剪贴板")
        except tk.TclError:
            messagebox.showwarning("警告", "剪贴板为空或无法读取")
    
    def split_sentences(self):
        """将文本分割为句子"""
        text = self.text_widget.get(1.0, tk.END).strip()
        if not text:
            self.sentences = []
            self.progress_label.config(text="句子: 0句")
            return
            
        # 根据当前语音类型选择分割规则
        if self.voice.startswith("ja-JP"):
            # 日语分割：句号、问号、感叹号、换行、日语句号
            sentences = re.split(r'[。！？\n．]+', text)
        elif self.voice.startswith("en-US"):
            # 英语分割：句号、问号、感叹号、换行
            sentences = re.split(r'[.!?\n]+', text)
        else:
            # 中文分割：句号、问号、感叹号、换行
            sentences = re.split(r'[。！？\n]+', text)
            
        self.sentences = [s.strip() for s in sentences if s.strip()]
        self.current_sentence = 0
        
        # 清除所有标签
        self.text_widget.tag_remove("current", 1.0, tk.END)
        self.text_widget.tag_remove("completed", 1.0, tk.END)
        self.text_widget.tag_remove("converted", 1.0, tk.END)
        self.text_widget.tag_remove("clickable", 1.0, tk.END)
        
        self.progress_label.config(text=f"句子: {len(self.sentences)}句")
    
    def reset_conversion_state(self):
        """重置转换状态"""
        self.is_converted = False
        self.audio_files = []
        self.cleanup_temp_files()
        # 重置进度条和进度标签
        self.progress_var.set(0)
        self.progress_label.config(text=f"句子: {len(self.sentences)}句")
        self.update_button_states()
    
    def on_voice_change(self, event):
        """语音选择改变"""
        self.voice = self.voice_var.get()
        self.status_label.config(text=f"状态: 已切换语音 - {self.voice}")
        if self.is_converted:
            self.reset_conversion_state()
            self.status_label.config(text="状态: 语音已更改，需重新转换")
    
    def convert_text(self):
        """开始转换文本为音频"""
        # 确保获取最新的文本内容
        self.split_sentences()
        
        if not self.sentences:
            messagebox.showwarning("警告", "请先输入文本")
            return
            
        self.is_converting = True
        self.update_button_states()
        
        # 在新线程中处理TTS转换
        thread = threading.Thread(target=self.process_conversion)
        thread.daemon = True
        thread.start()
    
    def process_conversion(self):
        """处理TTS转换"""
        try:
            asyncio.run(self.convert_all_sentences_parallel())
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"转换失败: {str(e)}"))
        finally:
            self.is_converting = False
            self.root.after(0, self.update_button_states)
    
    async def convert_single_sentence(self, sentence, index):
        """转换单个句子"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()
        
        # 直接使用纯文本，不使用SSML
        communicate = edge_tts.Communicate(sentence, self.voice)
        await communicate.save(temp_file.name)
        
        return index, temp_file.name
    
    async def convert_all_sentences_parallel(self):
        """并行转换所有句子为音频文件"""
        total_sentences = len(self.sentences)
        self.audio_files = [None] * total_sentences
        self.temp_files = []
        
        max_workers = int(self.thread_var.get())
        
        tasks = []
        for i, sentence in enumerate(self.sentences):
            task = self.convert_single_sentence(sentence, i)
            tasks.append(task)
        
        semaphore = asyncio.Semaphore(max_workers)
        
        async def limited_convert(task):
            async with semaphore:
                return await task
        
        completed = 0
        for coro in asyncio.as_completed([limited_convert(task) for task in tasks]):
            if not self.is_converting:
                break
                
            index, temp_file_path = await coro
            self.audio_files[index] = temp_file_path
            self.temp_files.append(temp_file_path)
            
            completed += 1
            
            # 更新UI，但不标记句子颜色
            self.root.after(0, lambda c=completed: self.status_label.config(text=f"状态: 转换中... ({c}/{total_sentences})"))
            self.root.after(0, lambda c=completed: self.progress_var.set((c/total_sentences)*100))
            self.root.after(0, lambda c=completed: self.progress_label.config(text=f"转换: {c}/{total_sentences}"))
        
        # 转换完成
        if self.is_converting:
            self.is_converted = True
            self.root.after(0, lambda: self.status_label.config(text=f"状态: 转换完成，使用{max_workers}个线程"))
            self.root.after(0, lambda: self.progress_var.set(100))
            # 移除make_sentences_clickable调用，避免蓝色下划线
            
            # 保存到历史记录
            text = self.text_widget.get(1.0, tk.END).strip()
            self.config.add_history(text, self.voice, len(self.sentences))
            self.config.update_settings(self.voice, self.max_workers)
    
    def save_audio(self):
        """保存音频文件"""
        if not self.is_converted or not self.audio_files:
            messagebox.showwarning("警告", "请先转换文本")
            return
        
        # 选择保存目录
        save_dir = filedialog.askdirectory(title="选择保存目录")
        if not save_dir:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存单个句子音频
            for i, (sentence, audio_file) in enumerate(zip(self.sentences, self.audio_files)):
                safe_sentence = re.sub(r'[^\w\s-]', '', sentence[:30])  # 取前30个字符作为文件名
                safe_sentence = re.sub(r'[-\s]+', '_', safe_sentence)
                filename = f"{timestamp}_第{i+1:03d}句_{safe_sentence}.mp3"
                save_path = os.path.join(save_dir, filename)
                shutil.copy2(audio_file, save_path)
            
            # 合并所有音频为一个文件
            combined_filename = f"{timestamp}_完整音频.mp3"
            combined_path = os.path.join(save_dir, combined_filename)
            self.combine_audio_files(combined_path)
            
            messagebox.showinfo("成功", f"音频已保存到: {save_dir}\n包含{len(self.audio_files)}个单句音频和1个完整音频")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")
    
    def combine_audio_files(self, output_path):
        """合并音频文件"""
        try:
            # 使用pygame合并音频（简单的文件拼接）
            with open(output_path, 'wb') as outfile:
                for audio_file in self.audio_files:
                    with open(audio_file, 'rb') as infile:
                        outfile.write(infile.read())
        except Exception as e:
            # 如果合并失败，至少保存第一个文件
            if self.audio_files:
                shutil.copy2(self.audio_files[0], output_path)
    
    def mark_sentence_converted(self, sentence_index):
        """标记句子为已转换"""
        if sentence_index < len(self.sentences):
            text = self.text_widget.get(1.0, tk.END)
            start_pos = 0
            
            for i in range(sentence_index):
                start_pos = text.find(self.sentences[i], start_pos) + len(self.sentences[i])
            
            sentence_start = text.find(self.sentences[sentence_index], start_pos)
            if sentence_start != -1:
                sentence_end = sentence_start + len(self.sentences[sentence_index])
                start_index = f"1.0+{sentence_start}c"
                end_index = f"1.0+{sentence_end}c"
                self.text_widget.tag_add("converted", start_index, end_index)
    
    def make_sentences_clickable(self):
        """使所有句子可点击"""
        text = self.text_widget.get(1.0, tk.END)
        start_pos = 0
        
        for i, sentence in enumerate(self.sentences):
            sentence_start = text.find(sentence, start_pos)
            if sentence_start != -1:
                sentence_end = sentence_start + len(sentence)
                start_index = f"1.0+{sentence_start}c"
                end_index = f"1.0+{sentence_end}c"
                self.text_widget.tag_add("clickable", start_index, end_index)
                start_pos = sentence_end
    
    def on_text_click(self, event):
        """点击文本播放对应句子"""
        if not self.is_converted or not self.sentences:
            return
            
        # 获取点击位置
        index = self.text_widget.index(tk.CURRENT)
        clicked_text = self.text_widget.get(1.0, index)
        
        # 计算点击位置对应的句子
        char_count = 0
        for i, sentence in enumerate(self.sentences):
            char_count += len(sentence)
            if char_count >= len(clicked_text):
                self.current_sentence = i
                self.play_single_sentence(i)  # 只播放单句
                break
    
    def on_text_hover(self, event):
        """鼠标悬停时改变光标"""
        if self.is_converted:
            self.text_widget.config(cursor="hand2")
        else:
            self.text_widget.config(cursor="xterm")
    
    def play_single_sentence(self, sentence_index):
        """播放单个句子"""
        if not self.is_converted or sentence_index >= len(self.audio_files):
            return
            
        self.stop_play()  # 停止当前播放
        self.current_sentence = sentence_index
        self.is_playing = True
        
        # 高亮当前句子
        self.highlight_current_sentence()
        
        # 播放音频
        pygame.mixer.music.load(self.audio_files[self.current_sentence])
        pygame.mixer.music.play()
        
        self.update_button_states()
        self.status_label.config(text=f"状态: 播放第{self.current_sentence+1}句")
        
        # 监控播放完成但不自动播放下一句
        self.monitor_single_play()
    
    def monitor_single_play(self):
        """监控单句播放完成"""
        if pygame.mixer.music.get_busy() and self.is_playing:
            # 还在播放，继续监控
            self.root.after(100, self.monitor_single_play)
        elif self.is_playing:
            # 播放完成，停止播放
            self.is_playing = False
            self.update_button_states()
            self.text_widget.tag_remove("current", 1.0, tk.END)
            self.status_label.config(text="状态: 播放完成")
    
    def play_from_sentence(self, sentence_index):
        """从指定句子开始连续播放"""
        if not self.is_converted or sentence_index >= len(self.audio_files):
            return
            
        self.stop_play()  # 停止当前播放
        self.current_sentence = sentence_index
        self.is_playing = True
        self.play_current_and_continue()
        
    def play_all(self):
        """从第一句开始连续播放"""
        if not self.is_converted:
            return
        self.current_sentence = 0
        self.is_playing = True
        self.play_current_and_continue()
    
    def play_current_and_continue(self):
        """播放当前句子并继续下一句"""
        if not self.is_playing or self.current_sentence >= len(self.sentences):
            self.is_playing = False
            self.update_button_states()
            self.status_label.config(text="状态: 播放完成")
            return
            
        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.status_label.config(text="状态: 继续播放")
            self.update_button_states()
            return
        
        # 高亮当前句子
        self.highlight_current_sentence()
        
        # 播放音频
        pygame.mixer.music.load(self.audio_files[self.current_sentence])
        pygame.mixer.music.play()
        
        self.update_button_states()
        self.status_label.config(text=f"状态: 播放第{self.current_sentence+1}句")
        
        # 监控播放完成并自动播放下一句
        self.monitor_and_continue()
    
    def monitor_and_continue(self):
        """监控播放完成并自动播放下一句"""
        if pygame.mixer.music.get_busy() and self.is_playing:
            # 还在播放，继续监控
            self.root.after(100, self.monitor_and_continue)
        elif self.is_playing:
            # 播放完成，标记当前句子并播放下一句
            self.mark_sentence_completed()
            self.current_sentence += 1
            # 稍微延迟后播放下一句
            self.root.after(300, self.play_current_and_continue)
    
    def highlight_current_sentence(self):
        """高亮当前句子"""
        if not self.sentences or self.current_sentence >= len(self.sentences):
            return
            
        # 清除当前高亮
        self.text_widget.tag_remove("current", 1.0, tk.END)
        
        # 计算当前句子在文本中的位置
        text = self.text_widget.get(1.0, tk.END)
        start_pos = 0
        
        for i in range(self.current_sentence):
            start_pos = text.find(self.sentences[i], start_pos) + len(self.sentences[i])
        
        sentence_start = text.find(self.sentences[self.current_sentence], start_pos)
        if sentence_start != -1:
            sentence_end = sentence_start + len(self.sentences[self.current_sentence])
            start_index = f"1.0+{sentence_start}c"
            end_index = f"1.0+{sentence_end}c"
            
            self.text_widget.tag_add("current", start_index, end_index)
            self.text_widget.see(start_index)
    
    def mark_sentence_completed(self):
        """标记句子为已完成"""
        if self.current_sentence < len(self.sentences):
            text = self.text_widget.get(1.0, tk.END)
            start_pos = 0
            
            for i in range(self.current_sentence):
                start_pos = text.find(self.sentences[i], start_pos) + len(self.sentences[i])
            
            sentence_start = text.find(self.sentences[self.current_sentence], start_pos)
            if sentence_start != -1:
                sentence_end = sentence_start + len(self.sentences[self.current_sentence])
                start_index = f"1.0+{sentence_start}c"
                end_index = f"1.0+{sentence_end}c"
                self.text_widget.tag_add("completed", start_index, end_index)
    
    def pause_play(self):
        """暂停播放"""
        pygame.mixer.music.pause()
        self.is_paused = True
        self.update_button_states()
        self.status_label.config(text="状态: 已暂停")
    
    def stop_play(self):
        """停止播放"""
        self.is_playing = False
        self.is_paused = False
        pygame.mixer.music.stop()
        self.update_button_states()
        self.text_widget.tag_remove("current", 1.0, tk.END)
        self.status_label.config(text="状态: 已停止")
    
    def update_button_states(self):
        """更新按钮状态"""
        if self.is_converting:
            self.convert_btn.config(state="disabled")
            self.save_btn.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
        elif self.is_converted:
            self.convert_btn.config(state="normal")
            self.save_btn.config(state="normal")
            if self.is_playing:
                if self.is_paused:
                    self.play_btn.config(text="继续", state="normal")
                    self.pause_btn.config(state="disabled")
                else:
                    self.play_btn.config(state="disabled")
                    self.pause_btn.config(state="normal")
                self.stop_btn.config(state="normal")
            else:
                self.play_btn.config(text="播放", state="normal")
                self.pause_btn.config(state="disabled")
                self.stop_btn.config(state="disabled")
        else:
            self.convert_btn.config(state="normal")
            self.save_btn.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass
        self.temp_files.clear()
    
    def on_closing(self):
        """程序关闭时清理"""
        self.stop_play()
        self.cleanup_temp_files()
        pygame.mixer.quit()
        self.root.destroy()

    def show_history(self):
        """显示历史记录"""
        history_window = tk.Toplevel(self.root)
        history_window.title("转换历史")
        history_window.geometry("600x400")
        
        # 创建列表框
        listbox = tk.Listbox(history_window)
        scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # 添加历史记录
        for item in self.config.config["history"]:
            display_text = f"{item['timestamp']} | {item['voice']} | {item['sentences_count']}句 | {item['text']}"
            listbox.insert(tk.END, display_text)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 双击加载历史文本
        def on_double_click(event):
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                history_item = self.config.config["history"][index]
                # 这里只能显示截断的文本，实际应用中可能需要存储完整文本
                messagebox.showinfo("历史文本", f"文本预览:\n{history_item['text']}")
        
        listbox.bind("<Double-Button-1>", on_double_click)

    def clear_history(self):
        """清空历史记录"""
        if messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            self.config.clear_history()
            messagebox.showinfo("成功", "历史记录已清空")

if __name__ == "__main__":
    root = tk.Tk()
    app = TTSReader(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()





