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
import time
import logging
from datetime import datetime
from config import Config
import aiohttp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tts_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
        self.is_continuous_play = False  # 是否为连续播放模式
        self.last_text_content = ""  # 记录上次的文本内容
        self.session = None  # 添加会话复用
        
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
        self.text_widget.bind("<<Modified>>", self.on_text_modified)
        # 移除KeyRelease绑定，只使用Modified事件
    
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
    
    def on_text_modified(self, event=None):
        """文本内容被修改时触发"""
        if self.text_widget.edit_modified():
            # 重置修改标志
            self.text_widget.edit_modified(False)
            
            # 获取当前文本内容
            current_text = self.text_widget.get(1.0, tk.END).strip()
            
            # 检查文本是否真的发生了变化
            if current_text != self.last_text_content:
                self.last_text_content = current_text
                self.on_text_content_changed()
    
    def on_text_content_changed(self):
        """文本内容发生变化时的处理"""
        # 自动分割句子
        self.split_sentences()
        
        # 如果已经转换过，重置转换状态
        if self.is_converted:
            self.reset_conversion_state()
            self.status_label.config(text="状态: 文本已更改，需重新转换")
    
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
        start_time = time.time()
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
        
        split_time = time.time() - start_time
        logger.info(f"文本分割完成，耗时: {split_time*1000:.1f}ms，分割出 {len(self.sentences)} 个句子")
    
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
        start_time = time.time()
        logger.info("=== 开始转换流程 ===")
        
        # 快速检查
        if not self.text_widget.get(1.0, tk.END).strip():
            messagebox.showwarning("警告", "请先输入文本")
            return
        
        logger.info(f"文本检查完成，耗时: {(time.time() - start_time)*1000:.1f}ms")
        
        # 立即更新状态，避免用户等待
        self.is_converting = True
        self.update_button_states()
        self.status_label.config(text="状态: 准备转换...")
        
        logger.info(f"UI状态更新完成，耗时: {(time.time() - start_time)*1000:.1f}ms")
        
        # 立即启动线程，减少延迟
        thread = threading.Thread(target=self.process_conversion)
        thread.daemon = True
        thread.start()
        
        logger.info(f"线程启动完成，总耗时: {(time.time() - start_time)*1000:.1f}ms")
    
    def process_conversion(self):
        """处理TTS转换"""
        process_start = time.time()
        logger.info("=== 进入转换线程 ===")
        
        try:
            # 在线程中进行文本分割，避免阻塞UI
            ui_start = time.time()
            self.root.after(0, lambda: self.status_label.config(text="状态: 分析文本..."))
            logger.debug(f"UI状态更新耗时: {(time.time() - ui_start)*1000:.1f}ms")
            
            # 确保获取最新的文本内容并分割
            text_start = time.time()
            text = self.text_widget.get(1.0, tk.END).strip()
            logger.info(f"获取文本内容耗时: {(time.time() - text_start)*1000:.1f}ms，文本长度: {len(text)}")
            
            if not text:
                self.root.after(0, lambda: messagebox.showwarning("警告", "文本为空"))
                return
            
            # 在主线程中分割句子
            split_start = time.time()
            self.root.after(0, self.split_sentences)
            
            # 等待分割完成
            time.sleep(0.1)
            logger.info(f"句子分割耗时: {(time.time() - split_start)*1000:.1f}ms，句子数量: {len(self.sentences)}")
            
            if not self.sentences:
                self.root.after(0, lambda: messagebox.showwarning("警告", "无法分割句子"))
                return
            
            # 显示句子信息
            for i, sentence in enumerate(self.sentences):
                logger.debug(f"句子 {i+1}: {sentence[:50]}...")
            
            self.root.after(0, lambda: self.status_label.config(text="状态: 开始转换..."))
            
            # 开始异步转换
            async_start = time.time()
            logger.info("开始异步转换...")
            
            # 检查网络连接
            logger.info("检查edge-tts服务连接...")
            asyncio.run(self.convert_all_sentences_parallel())
            logger.info(f"异步转换完成，耗时: {(time.time() - async_start):.2f}s")
            
        except Exception as e:
            logger.error(f"转换过程出错: {str(e)}", exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("错误", f"转换失败: {str(e)}"))
        finally:
            self.is_converting = False
            self.root.after(0, self.update_button_states)
            logger.info(f"=== 转换流程结束，总耗时: {(time.time() - process_start):.2f}s ===")
    
    async def get_session(self):
        """获取或创建aiohttp会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(
                limit=20,  # 连接池大小
                limit_per_host=10,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
        return self.session
    
    async def convert_single_sentence_optimized(self, sentence, index):
        """优化的单句转换"""
        start_time = time.time()
        logger.info(f"开始转换句子 {index+1}: {sentence[:50]}...")
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 创建Communicate对象
                communicate_start = time.time()
                communicate = edge_tts.Communicate(sentence, self.voice)
                logger.info(f"句子 {index+1} 创建Communicate对象耗时: {(time.time() - communicate_start)*1000:.1f}ms")
                
                # 网络请求
                save_start = time.time()
                logger.info(f"句子 {index+1} 开始网络请求... (尝试 {attempt+1}/{max_retries})")
                
                await communicate.save(temp_file.name)
                
                save_time = time.time() - save_start
                logger.info(f"句子 {index+1} 网络请求+保存完成，耗时: {save_time*1000:.1f}ms")
                
                # 检查文件
                file_size = os.path.getsize(temp_file.name) if os.path.exists(temp_file.name) else 0
                logger.info(f"句子 {index+1} 生成文件大小: {file_size} bytes")
                
                if file_size > 0:
                    break  # 成功
                else:
                    logger.warning(f"句子 {index+1} 生成文件为空，重试...")
                    
            except Exception as e:
                logger.error(f"句子 {index+1} 尝试 {attempt+1} 失败: {str(e)}")
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(1)  # 重试前等待
        
        total_time = time.time() - start_time
        logger.info(f"句子 {index+1} 转换完成，总耗时: {total_time*1000:.1f}ms")
        
        return index, temp_file.name
    
    async def convert_all_sentences_parallel(self):
        """优化的并行转换"""
        total_start = time.time()
        total_sentences = len(self.sentences)
        logger.info(f"开始并行转换 {total_sentences} 个句子")
        
        self.audio_files = [None] * total_sentences
        self.temp_files = []
        
        # 使用界面上设置的线程数
        max_workers = int(self.thread_var.get())
        logger.info(f"使用 {max_workers} 个并发线程")
        
        # 创建任务
        tasks = []
        for i, sentence in enumerate(self.sentences):
            task = self.convert_single_sentence_optimized(sentence, i)
            tasks.append(task)
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_workers)
        
        async def limited_convert(task):
            async with semaphore:
                return await task
        
        # 批量执行，添加延迟
        completed = 0
        batch_size = max(2, max_workers // 2)  # 根据线程数调整批次大小
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            logger.info(f"开始执行批次 {i//batch_size + 1}，包含 {len(batch)} 个任务")
            
            # 执行当前批次
            batch_results = await asyncio.gather(
                *[limited_convert(task) for task in batch],
                return_exceptions=True
            )
            
            # 处理结果
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"批次任务失败: {result}")
                    continue
                    
                index, temp_file_path = result
                self.audio_files[index] = temp_file_path
                self.temp_files.append(temp_file_path)
                completed += 1
                
                logger.info(f"句子 {index+1} 任务完成，进度: {completed}/{total_sentences}")
                
                # 更新UI
                self.root.after(0, lambda c=completed: self.status_label.config(text=f"状态: 转换中... ({c}/{total_sentences})"))
                self.root.after(0, lambda c=completed: self.progress_var.set((c/total_sentences)*100))
            
            # 批次间延迟，避免请求过于密集
            if i + batch_size < len(tasks):
                await asyncio.sleep(0.3)
        
        # 清理会话
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        
        convert_time = time.time() - total_start
        logger.info(f"所有句子转换完成，耗时: {convert_time:.2f}s，平均每句: {(convert_time/total_sentences)*1000:.1f}ms")
        
        # 转换完成
        if self.is_converting:
            self.is_converted = True
            self.root.after(0, lambda: self.status_label.config(text=f"状态: 转换完成"))
            self.root.after(0, lambda: self.progress_var.set(100))
            
            total_time = time.time() - total_start
            logger.info(f"=== 并行转换完成，总耗时: {total_time:.2f}s ===")
    
    def save_audio(self):
        """保存音频文件"""
        logger.info(f"保存按钮被点击 - is_converted: {self.is_converted}, audio_files数量: {len(self.audio_files)}")
        
        if not self.is_converted:
            logger.warning("保存失败：未转换状态")
            messagebox.showwarning("警告", "请先转换文本")
            return
            
        if not self.audio_files:
            logger.warning("保存失败：音频文件列表为空")
            messagebox.showwarning("警告", "没有可保存的音频文件")
            return
        
        # 检查音频文件是否存在
        valid_files = []
        for i, audio_file in enumerate(self.audio_files):
            if audio_file and os.path.exists(audio_file):
                valid_files.append(audio_file)
                logger.debug(f"音频文件 {i+1} 存在: {audio_file}")
            else:
                logger.warning(f"音频文件 {i+1} 不存在或为空: {audio_file}")
        
        if not valid_files:
            logger.error("保存失败：没有有效的音频文件")
            messagebox.showerror("错误", "没有有效的音频文件可保存")
            return
        
        logger.info(f"找到 {len(valid_files)} 个有效音频文件，开始保存...")
        
        # 生成默认文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{timestamp}.mp3"
        
        # 选择保存文件 - 修复参数名
        save_path = filedialog.asksaveasfilename(
            title="保存合并音频",
            defaultextension=".mp3",
            initialfile=default_filename,  # 修改为 initialfile
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")]
        )
        
        if not save_path:
            logger.info("用户取消了保存操作")
            return
        
        try:
            logger.info(f"开始合并音频到: {save_path}")
            # 合并所有音频为一个文件
            self.combine_audio_files(save_path)
            
            # 询问是否保存单句音频
            if messagebox.askyesno("保存选项", "是否同时保存单句音频文件？"):
                save_dir = os.path.dirname(save_path)
                base_name = os.path.splitext(os.path.basename(save_path))[0]
                
                # 保存单个句子音频
                saved_count = 0
                for i, (sentence, audio_file) in enumerate(zip(self.sentences, self.audio_files)):
                    if audio_file and os.path.exists(audio_file):
                        safe_sentence = re.sub(r'[^\w\s-]', '', sentence[:20])  # 取前20个字符
                        safe_sentence = re.sub(r'[-\s]+', '_', safe_sentence)
                        filename = f"{base_name}_第{i+1:03d}句_{safe_sentence}.mp3"
                        single_save_path = os.path.join(save_dir, filename)
                        shutil.copy2(audio_file, single_save_path)
                        saved_count += 1
                        logger.debug(f"保存单句音频: {single_save_path}")
                
                logger.info(f"保存完成 - 主文件: {save_path}, 单句文件: {saved_count}个")
                messagebox.showinfo("成功", f"音频已保存:\n主文件: {save_path}\n单句文件: {saved_count}个")
            else:
                logger.info(f"保存完成 - 仅主文件: {save_path}")
                messagebox.showinfo("成功", f"音频已保存: {save_path}")
            
        except Exception as e:
            logger.error(f"保存失败: {str(e)}", exc_info=True)
            messagebox.showerror("错误", f"保存失败: {str(e)}")
    
    def combine_audio_files(self, output_path):
        """合并音频文件 - 使用更高效的方法"""
        try:
            # 简单的二进制拼接（适用于相同格式的MP3文件）
            with open(output_path, 'wb') as outfile:
                for i, audio_file in enumerate(self.audio_files):
                    if os.path.exists(audio_file):
                        with open(audio_file, 'rb') as infile:
                            # 跳过第一个文件之外的MP3头部信息（简化处理）
                            if i == 0:
                                outfile.write(infile.read())
                            else:
                                # 跳过MP3头部，只写入音频数据部分
                                content = infile.read()
                                # 简单处理：直接拼接（可能有轻微的播放间隙）
                                outfile.write(content)
        except Exception as e:
            # 如果合并失败，至少保存第一个文件
            if self.audio_files and os.path.exists(self.audio_files[0]):
                shutil.copy2(self.audio_files[0], output_path)
            else:
                raise e
    
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
                # 播放单句（会自动重置状态）
                self.play_single_sentence(i)
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
        
        # 重置状态
        self.stop_play()
        self.current_sentence = sentence_index
        self.is_playing = True
        self.is_paused = False
        self.is_continuous_play = False  # 标记为单句播放模式
        
        # 清除所有标记
        self.text_widget.tag_remove("current", 1.0, tk.END)
        self.text_widget.tag_remove("completed", 1.0, tk.END)
        
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
        if pygame.mixer.music.get_busy() and self.is_playing and not self.is_paused:
            # 还在播放，继续监控
            self.root.after(100, self.monitor_single_play)
        elif self.is_playing and not self.is_paused:
            # 单句播放完成，重置状态
            self.is_playing = False
            self.text_widget.tag_remove("current", 1.0, tk.END)
            self.update_button_states()
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
        
        # 重置状态
        self.stop_play()
        self.current_sentence = 0
        self.is_playing = True
        self.is_paused = False
        self.is_continuous_play = True  # 标记为连续播放模式
        
        # 清除所有标记
        self.text_widget.tag_remove("current", 1.0, tk.END)
        self.text_widget.tag_remove("completed", 1.0, tk.END)
        
        self.play_current_and_continue()
    
    def play_current_and_continue(self):
        """播放当前句子并继续下一句"""
        if not self.is_playing or self.current_sentence >= len(self.sentences):
            # 播放完成，重置状态
            self.is_playing = False
            self.is_paused = False
            self.is_continuous_play = False
            self.text_widget.tag_remove("current", 1.0, tk.END)
            self.update_button_states()
            self.status_label.config(text="状态: 播放完成")
            return
        
        if self.is_paused:
            # 从暂停状态恢复
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
        if pygame.mixer.music.get_busy() and self.is_playing and not self.is_paused:
            # 还在播放，继续监控
            self.root.after(100, self.monitor_and_continue)
        elif self.is_playing and not self.is_paused:
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
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.update_button_states()
            self.status_label.config(text="状态: 已暂停")
    
    def stop_play(self):
        """停止播放"""
        self.is_playing = False
        self.is_paused = False
        self.is_continuous_play = False
        pygame.mixer.music.stop()
        
        # 清除所有高亮标记
        self.text_widget.tag_remove("current", 1.0, tk.END)
        self.text_widget.tag_remove("completed", 1.0, tk.END)
        
        self.update_button_states()
        self.status_label.config(text="状态: 已停止")
    
    def update_button_states(self):
        """更新按钮状态"""
        if self.is_converting:
            # 转换中：禁用所有按钮
            self.convert_btn.config(state="disabled")
            self.save_btn.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
        elif self.is_converted:
            # 已转换完成
            self.convert_btn.config(state="normal")
            self.save_btn.config(state="normal")
            
            if self.is_playing:
                if self.is_paused:
                    # 暂停状态：显示继续按钮
                    self.play_btn.config(text="继续", state="normal", command=self.resume_play)
                    self.pause_btn.config(state="disabled")
                    self.stop_btn.config(state="normal")
                else:
                    # 播放状态：禁用播放，启用暂停和停止
                    self.play_btn.config(text="播放", state="disabled", command=self.play_all)
                    self.pause_btn.config(state="normal")
                    self.stop_btn.config(state="normal")
            else:
                # 停止状态：启用播放，禁用暂停和停止
                self.play_btn.config(text="播放", state="normal", command=self.play_all)
                self.pause_btn.config(state="disabled")
                self.stop_btn.config(state="disabled")
        else:
            # 未转换：只启用转换按钮
            self.convert_btn.config(state="normal")
            self.save_btn.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.pause_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
    
    def resume_play(self):
        """恢复播放"""
        if self.is_paused:
            self.is_paused = False
            if self.is_continuous_play:
                # 连续播放模式：继续播放当前句子
                self.play_current_and_continue()
            else:
                # 单句播放模式：继续播放当前句子
                pygame.mixer.music.unpause()
                self.update_button_states()
                self.status_label.config(text=f"状态: 继续播放第{self.current_sentence+1}句")
                self.monitor_single_play()
    
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







