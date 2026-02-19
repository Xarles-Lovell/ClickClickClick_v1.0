#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鼠标自动连点器 v2.0
功能：支持多点位置记录、点击频率调节、全局快捷键、预设保存等
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import json
import os
import sys  # 添加sys模块用于获取打包后的资源路径
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener
from pynput.keyboard import Key, KeyCode
import pyautogui
import ctypes
from ctypes import wintypes, Structure, c_long, c_ulong, c_int, c_uint, POINTER, byref
from PIL import Image, ImageTk  # 添加PIL库用于处理图片

# 禁用PyAutoGUI的fail-safe功能
pyautogui.FAILSAFE = False

# Windows API 常量和结构体
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 鼠标事件常量
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000

# INPUT结构体
class POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]

class MOUSEINPUT(Structure):
    _fields_ = [("dx", c_long),
                ("dy", c_long),
                ("mouseData", c_ulong),
                ("dwFlags", c_ulong),
                ("time", c_ulong),
                ("dwExtraInfo", POINTER(c_ulong))]

class KEYBDINPUT(Structure):
    _fields_ = [("wVk", c_uint),
                ("wScan", c_uint),
                ("dwFlags", c_ulong),
                ("time", c_ulong),
                ("dwExtraInfo", POINTER(c_ulong))]

class HARDWAREINPUT(Structure):
    _fields_ = [("uMsg", c_ulong),
                ("wParamL", c_uint),
                ("wParamH", c_uint)]

class INPUT(Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT),
                    ("mi", MOUSEINPUT),
                    ("hi", HARDWAREINPUT)]
    _fields_ = [("type", c_ulong),
                ("ii", _INPUT)]

# INPUT类型常量
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

# 版本信息
VERSION = "1.0"
VERSION_FILE = "version.txt"

# Windows API 常量
WM_COMMAND = 0x0111
WM_SYSCOMMAND = 0x0112
SC_TOPMOST = 0xF012  # 自定义系统命令ID

def windows_api_click(x, y, button='left'):
    """使用Windows API进行鼠标点击，绕过游戏保护"""
    try:
        # 获取屏幕分辨率
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # 转换为绝对坐标 (0-65535范围)
        abs_x = int(x * 65535 / screen_width)
        abs_y = int(y * 65535 / screen_height)
        
        # 创建INPUT结构体数组
        inputs = (INPUT * 3)()
        
        # 1. 移动鼠标到目标位置
        inputs[0].type = INPUT_MOUSE
        inputs[0].ii.mi.dx = abs_x
        inputs[0].ii.mi.dy = abs_y
        inputs[0].ii.mi.mouseData = 0
        inputs[0].ii.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        inputs[0].ii.mi.time = 0
        inputs[0].ii.mi.dwExtraInfo = None
        
        # 2. 按下鼠标按键
        inputs[1].type = INPUT_MOUSE
        inputs[1].ii.mi.dx = abs_x
        inputs[1].ii.mi.dy = abs_y
        inputs[1].ii.mi.mouseData = 0
        if button == 'left':
            inputs[1].ii.mi.dwFlags = MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE
        else:
            inputs[1].ii.mi.dwFlags = MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_ABSOLUTE
        inputs[1].ii.mi.time = 0
        inputs[1].ii.mi.dwExtraInfo = None
        
        # 3. 释放鼠标按键
        inputs[2].type = INPUT_MOUSE
        inputs[2].ii.mi.dx = abs_x
        inputs[2].ii.mi.dy = abs_y
        inputs[2].ii.mi.mouseData = 0
        if button == 'left':
            inputs[2].ii.mi.dwFlags = MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE
        else:
            inputs[2].ii.mi.dwFlags = MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_ABSOLUTE
        inputs[2].ii.mi.time = 0
        inputs[2].ii.mi.dwExtraInfo = None
        
        # 发送输入事件
        result = user32.SendInput(3, inputs, ctypes.sizeof(INPUT))
        return result == 3  # 成功发送3个事件
        
    except Exception as e:
        print(f"Windows API点击失败: {e}")
        return False

def fallback_click(x, y, button='left'):
    """备用点击方法，使用pyautogui"""
    try:
        if button == 'left':
            pyautogui.leftClick(x, y)
        else:
            pyautogui.rightClick(x, y)
        return True
    except Exception as e:
        print(f"备用点击失败: {e}")
        return False

def enhanced_click(x, y, button='left'):
    """增强的点击函数，优先使用Windows API，失败时使用备用方法"""
    # 首先尝试Windows API
    if windows_api_click(x, y, button):
        return True
    
    print("Windows API点击失败，使用备用方法...")
    # 备用方法：pyautogui
    return fallback_click(x, y, button)

class AutoClicker:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"点点点_ClickClickClick_v{VERSION}")
        self.root.geometry("520x1100")  # 增加高度到1100，确保状态信息栏有足够空间
        self.root.resizable(False, False)
        
        # 设置程序图标
        self.setup_icon()
        
        # 设置新的灰色主题配色
        self.root.configure(bg="#eaeaea")  # 浅灰色背景
        
        # 设置程序图标和样式
        self.setup_style()
        
        # 初始化变量
        self.is_clicking = False
        self.click_thread = None
        self.positions = []
        self.current_preset = None
        self.presets_file = "presets.json"
        
        # 快捷键相关
        self.hotkey_listener = None
        self.current_hotkey = "Alt+R"
        self.hotkey_pressed = False
        
        # 快捷键捕获状态
        self.capturing_hotkey = False
        self.temp_keys = set()
        
        # 置顶状态
        self.is_topmost = False
        
        # 测试窗口
        self.test_window = None
        
        # 添加系统相关功能
        self.setup_system_menu()
        
        # 创建界面
        self.create_widgets()
        
        # 加载预设
        self.load_presets()
        
        # 启动快捷键监听
        self.start_hotkey_listener()
        
        # 启动键盘监听（用于快捷键捕获）
        self.start_key_capture_listener()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 保存版本信息
        self.save_version_info()
        
        # 强制更新界面确保所有组件正确显示
        self.root.update_idletasks()
        self.root.after(100, self.check_status_display)
        
        # 加载置顶设置
        self.load_topmost_setting()

    def setup_icon(self):
        """设置程序图标"""
        try:
            # 获取资源文件路径（支持打包后的exe）
            def get_resource_path(relative_path):
                """获取资源文件的绝对路径，支持打包后的exe"""
                try:
                    # PyInstaller创建临时文件夹，并将路径存储在_MEIPASS中
                    base_path = sys._MEIPASS
                except Exception:
                    base_path = os.path.abspath(".")
                return os.path.join(base_path, relative_path)
            
            # 设置窗口图标
            icon_path = get_resource_path("image/cover_icon.png")
            if os.path.exists(icon_path):
                # 加载并设置窗口图标
                icon_image = Image.open(icon_path)
                icon_photo = ImageTk.PhotoImage(icon_image)
                self.root.iconphoto(True, icon_photo)
                
            # 加载标题用的点击图标
            click_icon_path = get_resource_path("image/click_icon.png")
            if os.path.exists(click_icon_path):
                # 调整图标大小，增大到36x36以更好地匹配文字大小
                click_image = Image.open(click_icon_path)
                click_image = click_image.resize((36, 36), Image.Resampling.LANCZOS)
                self.click_icon = ImageTk.PhotoImage(click_image)
            else:
                self.click_icon = None
                
        except Exception as e:
            print(f"加载图标失败: {e}")
            self.click_icon = None

    def toggle_topmost(self):
        """切换置顶状态"""
        self.toggle_topmost_shortcut()
    
    def toggle_topmost_shortcut(self):
        """通过快捷键切换置顶状态"""
        try:
            self.is_topmost = not self.is_topmost
            self.root.attributes('-topmost', self.is_topmost)
            
            # 更新窗口标题
            self.update_window_title()
            
            # 保存设置
            self.save_topmost_setting(self.is_topmost)
            
            # 添加日志
            status = "开启" if self.is_topmost else "关闭"
            self.add_log(f"窗口置顶已{status} (Ctrl+T)")
            
        except Exception as e:
            print(f"切换置顶状态失败: {e}")
            self.add_log(f"置顶设置失败: {e}")
    
    def save_topmost_setting(self, is_topmost):
        """保存置顶设置到文件"""
        try:
            settings = {}
            settings_file = "settings.json"
            
            # 尝试加载现有设置
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                except:
                    settings = {}
            
            # 更新置顶设置
            settings['window_topmost'] = is_topmost
            
            # 保存到文件
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"保存置顶设置失败: {e}")
    
    def load_topmost_setting(self):
        """加载置顶设置"""
        try:
            settings_file = "settings.json"
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    
                is_topmost = settings.get('window_topmost', False)
                self.is_topmost = is_topmost
                
                # 应用置顶设置
                if is_topmost:
                    self.root.attributes('-topmost', True)
                    self.update_window_title()
                    self.add_log("窗口置顶已开启")
                    
        except Exception as e:
            print(f"加载置顶设置失败: {e}")
            # 默认不置顶
            self.is_topmost = False
    
    def setup_style(self):
        """设置灰色简洁主题界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 定义新的配色方案
        bg_light = "#eaeaea"      # 浅灰色 - 大片面积
        bg_white = "#ffffff"      # 白色 - 亮色
        text_black = "#333333"    # 黑色 - 文字
        border_gray = "#999999"   # 深灰色 - 线框
        accent_gray = "#cbcbcb"   # 深灰色 - 点缀色
        
        # 配置各种组件样式
        style.configure("TFrame", background=bg_light)
        style.configure("TLabel", background=bg_light, foreground=text_black, font=("微软雅黑", 9))
        
        # 按钮样式 - 白色背景，黑色文字，深灰色边框
        style.configure("TButton", 
                       background=bg_white, 
                       foreground=text_black,
                       font=("微软雅黑", 9, "bold"),
                       borderwidth=2,
                       bordercolor=border_gray,
                       focuscolor="none")
        style.map("TButton",
                 background=[('active', accent_gray), ('pressed', accent_gray)])
        
        # 特殊按钮样式
        style.configure("Accent.TButton",
                       background=bg_white,
                       foreground=text_black,
                       font=("微软雅黑", 10, "bold"),
                       borderwidth=2,
                       bordercolor=border_gray)
        
        # LabelFrame样式 - 深灰色边框
        style.configure("TLabelframe", 
                       background=bg_light,
                       borderwidth=2,
                       relief="solid",
                       bordercolor=border_gray)
        style.configure("TLabelframe.Label",
                       background=bg_light,
                       foreground=text_black,
                       font=("微软雅黑", 12, "bold"))
        
        # 输入框样式 - 白色背景，深灰色边框
        style.configure("TEntry",
                       fieldbackground=bg_white,
                       foreground=text_black,
                       bordercolor=border_gray,
                       insertcolor=text_black,
                       borderwidth=2)
        
        # 下拉框样式
        style.configure("TCombobox",
                       fieldbackground=bg_white,
                       foreground=text_black,
                       bordercolor=border_gray,
                       borderwidth=2)
        
        # 滑块样式
        style.configure("TScale",
                       background=bg_light,
                       troughcolor=bg_white,
                       bordercolor=border_gray,
                       lightcolor=accent_gray,
                       darkcolor=accent_gray)
        
        # 单选按钮样式
        style.configure("TRadiobutton",
                       background=bg_light,
                       foreground=text_black,
                       focuscolor="none")
        
        # 列表框和文本框样式
        self.listbox_style = {
            'bg': bg_white,
            'fg': text_black,
            'selectbackground': accent_gray,
            'selectforeground': text_black,
            'font': ("Consolas", 9),
            'borderwidth': 1,
            'relief': 'solid',
            'highlightbackground': border_gray,
            'highlightcolor': border_gray,
            'highlightthickness': 1
        }
        
        self.text_style = {
            'bg': bg_white,
            'fg': text_black,
            'selectbackground': accent_gray,
            'selectforeground': text_black,
            'borderwidth': 1,
            'relief': 'solid',
            'highlightbackground': border_gray,
            'highlightcolor': border_gray,
            'highlightthickness': 1
        }
    
    def setup_system_menu(self):
        """设置系统相关功能"""
        try:
            # 由于tkinter限制，我们使用标题栏显示置顶状态
            # 并在窗口内添加快捷的置顶控制
            self.update_window_title()
            
        except Exception as e:
            print(f"设置系统功能失败: {e}")
    
    def update_window_title(self):
        """更新窗口标题，显示置顶状态"""
        base_title = f"点点点_ClickClickClick_v{VERSION}"
        if self.is_topmost:
            self.root.title(f"{base_title} 📌")
        else:
            self.root.title(base_title)
        
    def create_widgets(self):
        """创建界面组件"""
        # 创建顶部白色区域
        header_frame = tk.Frame(self.root, bg="#ffffff", height=120)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # 创建标题框架，用于放置图标和文字
        title_frame = tk.Frame(header_frame, bg="#ffffff")
        title_frame.pack(pady=(20, 5))
        
        # 如果有图标，显示图标和文字，否则只显示文字
        if hasattr(self, 'click_icon') and self.click_icon:
            # 显示图标
            icon_label = tk.Label(title_frame, image=self.click_icon, bg="#ffffff")
            icon_label.pack(side=tk.LEFT, padx=(0, 10))  # 增加间距到10px
            
            # 显示标题文字，稍微减小字体
            title_label = tk.Label(title_frame, text="点点点_ClickClickClick", 
                                  font=("微软雅黑", 18, "bold"),  # 从20减小到18
                                  fg="#333333", bg="#ffffff")
            title_label.pack(side=tk.LEFT)
        else:
            # 如果没有图标，使用原来的emoji方式
            title_label = tk.Label(title_frame, text="🖱 点点点_ClickClickClick", 
                                  font=("微软雅黑", 20, "bold"), 
                                  fg="#333333", bg="#ffffff")
            title_label.pack()
        
        # 置顶提示 - 改为深灰色文字，提高可读性
        topmost_tip = tk.Label(header_frame, text="💡 按 Ctrl+T 切换窗口置顶", 
                              font=("微软雅黑", 10), 
                              fg="#999999", bg="#ffffff")
        topmost_tip.pack(pady=(0, 15))
        
        # 创建主框架 - 浅灰色背景
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 连点测试区域
        self.create_test_area(main_frame)
        
        # 预设管理区域
        self.create_preset_management(main_frame)
        
        # 点击设置区域
        self.create_click_settings(main_frame)
        
        # 位置管理区域
        self.create_position_management(main_frame)
        
        # 控制按钮区域
        self.create_control_buttons(main_frame)
        
        # 状态显示区域
        self.create_status_area(main_frame)
        
        # 绑定置顶快捷键
        self.root.bind('<Control-t>', lambda e: self.toggle_topmost_shortcut())
        self.root.bind('<Control-T>', lambda e: self.toggle_topmost_shortcut())
    
    def create_click_settings(self, parent):
        """创建点击设置区域"""
        settings_frame = ttk.LabelFrame(parent, text="⚙️ 点击设置", padding="10", style="Heading.TLabelframe")
        settings_frame.pack(fill=tk.X, pady=(0, 20))  # 增加底部间距到20
        
        # 点击频率设置
        freq_frame = ttk.Frame(settings_frame)
        freq_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(freq_frame, text="点击频率:").pack(side=tk.LEFT)
        
        # 频率滑块（初始为秒模式）
        self.frequency_var = tk.DoubleVar(value=1.0)
        self.frequency_scale = ttk.Scale(freq_frame, from_=0.1, to=10.0, 
                                       variable=self.frequency_var, orient=tk.HORIZONTAL)
        self.frequency_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 5))
        
        # 频率输入框和单位选择
        freq_input_frame = ttk.Frame(freq_frame)
        freq_input_frame.pack(side=tk.RIGHT)
        
        self.frequency_entry = ttk.Entry(freq_input_frame, width=8)
        self.frequency_entry.pack(side=tk.LEFT)
        self.frequency_entry.insert(0, "1.0")
        
        # 单位选择
        self.freq_unit = tk.StringVar(value="秒/次")
        unit_combo = ttk.Combobox(freq_input_frame, textvariable=self.freq_unit, 
                                values=["秒/次", "毫秒/次"], width=8, state="readonly")
        unit_combo.pack(side=tk.LEFT, padx=(2, 0))
        unit_combo.bind("<<ComboboxSelected>>", self.update_frequency_unit)
        
        # 绑定事件
        self.frequency_scale.configure(command=self.update_frequency_from_scale)
        self.frequency_entry.bind('<Return>', self.update_frequency_from_entry)
        self.frequency_entry.bind('<FocusOut>', self.update_frequency_from_entry)
        
        # 鼠标按键选择
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(button_frame, text="鼠标按键:").pack(side=tk.LEFT)
        self.mouse_button = tk.StringVar(value="left")
        ttk.Radiobutton(button_frame, text="左键", variable=self.mouse_button, 
                       value="left").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(button_frame, text="右键", variable=self.mouse_button, 
                       value="right").pack(side=tk.LEFT)
    
    def create_position_management(self, parent):
        """创建位置管理区域"""
        pos_frame = ttk.LabelFrame(parent, text="📍 点击位置管理", padding="10", style="Heading.TLabelframe")
        pos_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))  # 增加底部间距到20
        
        # 快捷键设置（只保留记录位置）
        hotkey_frame = ttk.Frame(pos_frame)
        hotkey_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(hotkey_frame, text="记录位置快捷键:").pack(side=tk.LEFT)
        self.record_hotkey_btn = ttk.Button(hotkey_frame, text=self.current_hotkey, 
                                          command=self.capture_hotkey,
                                          width=15)
        self.record_hotkey_btn.pack(side=tk.LEFT, padx=(10, 5))
        
        # 提示标签 - 缩短文字并减少间距
        self.tip_label = ttk.Label(hotkey_frame, text="💡点击修改快捷键", 
                            font=("微软雅黑", 8), foreground="gray")
        self.tip_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # 位置操作按钮
        btn_frame = ttk.Frame(pos_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 配置列权重，让按钮等宽分布
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        
        self.record_btn = ttk.Button(btn_frame, text="📌 记录鼠标位置")
        self.record_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        self.record_btn.config(command=self.record_position)
        
        self.rename_pos_btn = ttk.Button(btn_frame, text="📝 重命名位置")
        self.rename_pos_btn.grid(row=0, column=1, sticky="ew", padx=(2, 2))
        self.rename_pos_btn.config(command=self.rename_selected_position)
        
        self.delete_pos_btn = ttk.Button(btn_frame, text="🗑 删除位置")
        self.delete_pos_btn.grid(row=0, column=2, sticky="ew", padx=(2, 0))
        self.delete_pos_btn.config(command=self.delete_selected_position_btn)
        
        # 位置列表
        list_frame = ttk.Frame(pos_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建列表框和滚动条，应用灰色主题
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.position_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                         height=3, **self.listbox_style)
        self.position_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.position_listbox.yview)
        
        # 绑定双击删除事件
        self.position_listbox.bind("<Double-Button-1>", self.delete_selected_position)
    
    def create_preset_management(self, parent):
        """创建预设管理区域"""
        preset_frame = ttk.LabelFrame(parent, text="💾 预设管理", padding="10", style="Heading.TLabelframe")
        preset_frame.pack(fill=tk.X, pady=(0, 20))  # 增加底部间距到20
        
        # 预设操作按钮
        btn_frame = ttk.Frame(preset_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 配置列权重，让按钮等宽分布
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        
        self.save_preset_btn = ttk.Button(btn_frame, text="💾 保存当前预设")
        self.save_preset_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        self.save_preset_btn.config(command=self.save_preset)
        
        self.rename_preset_btn = ttk.Button(btn_frame, text="📝 重命名预设")
        self.rename_preset_btn.grid(row=0, column=1, sticky="ew", padx=(2, 2))
        self.rename_preset_btn.config(command=self.rename_preset)
        
        self.delete_preset_btn = ttk.Button(btn_frame, text="🗑 删除预设")
        self.delete_preset_btn.grid(row=0, column=2, sticky="ew", padx=(2, 0))
        self.delete_preset_btn.config(command=self.delete_preset)
        
        # 预设选择下拉框
        select_frame = ttk.Frame(preset_frame)
        select_frame.pack(fill=tk.X)
        
        ttk.Label(select_frame, text="选择预设:").pack(side=tk.LEFT)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(select_frame, textvariable=self.preset_var, 
                                       state="readonly", width=20)
        self.preset_combo.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        self.preset_combo.bind("<<ComboboxSelected>>", self.load_selected_preset)
    
    def create_control_buttons(self, parent):
        """创建控制按钮区域"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=(0, 20))  # 增加底部间距到20
        
        # 配置列权重，让按钮等宽分布
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        
        self.start_btn = ttk.Button(control_frame, text="▶ 开始连点", 
                                  style="Accent.TButton")
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.start_btn.config(command=self.start_clicking)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ 停止连点（Esc）", 
                                 state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.stop_btn.config(command=self.stop_clicking)
    
    def create_test_area(self, parent):
        """创建连点测试区域"""
    def create_test_area(self, parent):
        """创建连点测试区域"""
        test_frame = ttk.LabelFrame(parent, text="🎯 连点测试/查看教程", padding="15")
        test_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 测试按钮占满整行，使用黄色样式
        self.test_btn = ttk.Button(test_frame, text="🎯 测一下试试", 
                                 command=self.open_test_window,
                                 style="Accent.TButton")
        self.test_btn.pack(fill=tk.X, ipady=8)  # 增加按钮高度
        
        # 测试窗口引用
        self.test_window = None
    
    def create_status_area(self, parent):
        """创建状态显示区域"""
        status_frame = ttk.LabelFrame(parent, text="📊 状态信息", padding="10", style="Heading.TLabelframe")
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))  # 添加expand=True确保显示
        
        # 创建滚动文本框用于显示日志，应用灰色主题
        log_frame = ttk.Frame(status_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建滚动条
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建文本框，设置为只读，高度约4行，应用灰色主题
        self.log_text = tk.Text(log_frame, height=5, wrap=tk.WORD, 
                               yscrollcommand=scrollbar.set, state=tk.DISABLED,
                               font=("微软雅黑", 9), 
                               **self.text_style)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # 日志消息列表，最多保留20条
        self.log_messages = []
        self.max_log_messages = 20
        
        # 使用说明
        help_text = "💡 使用提示：双击位置列表删除 | 可重命名位置方便识别 | Alt+R记录位置 | Esc停止连点"
        help_label = ttk.Label(status_frame, text=help_text, 
                             font=("微软雅黑", 8), foreground="gray")
        help_label.pack(pady=(5, 0))
        
        # 添加初始日志
        self.add_log('启动"点点点"...')
        
        # 强制更新界面以确保显示
        self.root.update_idletasks()

    def check_status_display(self):
        """检查状态显示区域是否正常"""
        try:
            # 确保日志文本框可见
            if hasattr(self, 'log_text'):
                # 添加一条测试日志来验证显示
                self.add_log("状态信息区域已就绪")
        except Exception as e:
            print(f"状态显示检查失败: {e}")

    def add_log(self, message):
        """添加日志消息"""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            
            # 添加到消息列表
            self.log_messages.append(log_entry)
            
            # 如果超过最大数量，删除最早的消息
            if len(self.log_messages) > self.max_log_messages:
                self.log_messages.pop(0)
            
            # 更新文本框显示
            self.update_log_display()
            
        except Exception as e:
            print(f"添加日志失败: {e}")
    
    def update_log_display(self):
        """更新日志显示"""
        try:
            if not hasattr(self, 'log_text') or not self.log_text:
                return
                
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            
            # 显示所有日志消息
            for message in self.log_messages:
                self.log_text.insert(tk.END, message + "\n")
            
            # 自动滚动到底部
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"更新日志显示失败: {e}")

    def update_frequency_from_scale(self, value):
        """从滑块更新频率"""
        freq = float(value)
        unit = self.freq_unit.get()
        
        if unit == "毫秒/次":
            # 毫秒模式：将滑块值转换为毫秒范围
            freq_ms = int(freq * 100)  # 0.1-10.0 -> 10-1000
            self.frequency_entry.delete(0, tk.END)
            self.frequency_entry.insert(0, str(freq_ms))
        else:
            # 秒模式：直接使用滑块值
            self.frequency_entry.delete(0, tk.END)
            self.frequency_entry.insert(0, f"{freq:.1f}")
    
    def update_frequency_from_entry(self, event=None):
        """从输入框更新频率"""
        try:
            freq = float(self.frequency_entry.get())
            unit = self.freq_unit.get()
            
            if unit == "秒/次":
                if 0.1 <= freq <= 10.0:
                    self.frequency_var.set(freq)
                else:
                    messagebox.showwarning("警告", "秒/次模式下频率必须在0.1-10.0之间！")
                    self.frequency_entry.delete(0, tk.END)
                    self.frequency_entry.insert(0, f"{self.frequency_var.get():.1f}")
            else:  # 毫秒/次
                freq_int = int(freq)
                if 1 <= freq_int <= 1000:
                    # 将毫秒值转换为滑块值 (1-1000 -> 0.01-10.0)
                    scale_value = freq_int / 100.0
                    self.frequency_var.set(scale_value)
                    self.frequency_entry.delete(0, tk.END)
                    self.frequency_entry.insert(0, str(freq_int))
                else:
                    messagebox.showwarning("警告", "毫秒/次模式下频率必须在1-1000之间的整数！")
                    self.frequency_entry.delete(0, tk.END)
                    self.frequency_entry.insert(0, "100")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")
            if self.freq_unit.get() == "秒/次":
                self.frequency_entry.delete(0, tk.END)
                self.frequency_entry.insert(0, f"{self.frequency_var.get():.1f}")
            else:
                self.frequency_entry.delete(0, tk.END)
                self.frequency_entry.insert(0, "100")
    
    def update_frequency_unit(self, event=None):
        """更新频率单位"""
        unit = self.freq_unit.get()
        if unit == "毫秒/次":
            # 切换到毫秒模式
            self.frequency_entry.delete(0, tk.END)
            self.frequency_entry.insert(0, "100")
            self.frequency_var.set(1.0)  # 对应100毫秒
        else:
            # 切换到秒模式
            self.frequency_entry.delete(0, tk.END)
            self.frequency_entry.insert(0, "1.0")
            self.frequency_var.set(1.0)
    
    def get_click_interval(self):
        """获取点击间隔（秒）"""
        try:
            freq_value = float(self.frequency_entry.get())
            unit = self.freq_unit.get()
            
            if unit == "秒/次":
                # 每X秒点击一次
                return freq_value
            else:  # 毫秒/次
                # 每X毫秒点击一次
                return freq_value / 1000.0
        except:
            return 1.0  # 默认1秒间隔
    
    def start_hotkey_listener(self):
        """启动快捷键监听"""
        try:
            if self.hotkey_listener:
                self.hotkey_listener.stop()
            
            # 构建快捷键映射 - 只包含记录位置快捷键
            hotkey_map = {}
            
            # 记录位置快捷键
            record_pynput = self.convert_to_pynput_format(self.current_hotkey)
            if record_pynput:
                hotkey_map[record_pynput] = self.hotkey_record_position
            
            if hotkey_map:
                self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
                self.hotkey_listener.start()
                print(f"快捷键监听已启动: 记录位置({self.current_hotkey})")
            
            # 单独启动Esc键监听
            self.start_esc_listener()
            
            # 添加日志 - 显示当前的快捷键设置
            self.add_log(f"快捷键已启动: 记录位置({self.current_hotkey}), 停止连点(Esc)")
                
        except Exception as e:
            print(f"快捷键监听启动失败: {e}")
            self.add_log(f"快捷键启动失败: {e}")
    
    def start_esc_listener(self):
        """启动Esc键单独监听"""
        try:
            if hasattr(self, 'esc_listener') and self.esc_listener:
                self.esc_listener.stop()
            
            def on_press(key):
                try:
                    if key == keyboard.Key.esc and self.is_clicking:
                        print("检测到Esc键，停止连点")
                        self.add_log("检测到Esc键，停止连点")
                        # 立即设置停止标志，防止额外点击
                        self.is_clicking = False
                        # 在主线程中执行停止操作和窗口置顶
                        self.root.after(0, self.stop_clicking_and_focus)
                except:
                    pass
            
            self.esc_listener = keyboard.Listener(on_press=on_press)
            self.esc_listener.start()
            print("Esc键监听已启动")
            
        except Exception as e:
            print(f"Esc键监听启动失败: {e}")
            self.add_log(f"Esc键监听启动失败: {e}")
    
    def hotkey_stop_clicking(self):
        """快捷键触发停止连点"""
        if self.is_clicking:
            print("快捷键触发停止连点")
            self.root.after(0, self.stop_clicking)
    
    def hotkey_start_stop_clicking(self):
        """快捷键触发开始/停止连点"""
        if self.is_clicking:
            self.root.after(0, self.stop_clicking)
        else:
            self.root.after(0, self.start_clicking)
    
    def hotkey_stop_clicking(self):
        """快捷键触发停止连点"""
        if self.is_clicking:
            self.root.after(0, self.stop_clicking)
    
    def convert_to_pynput_format(self, hotkey_str):
        """将显示格式的快捷键转换为pynput格式"""
        try:
            if not hotkey_str:
                return None
            
            # 处理单个按键的情况
            if '+' not in hotkey_str:
                # 单个功能键
                if hotkey_str.startswith('F') and hotkey_str[1:].isdigit():
                    return f'<{hotkey_str.lower()}>'
                # 单个字母或数字
                elif len(hotkey_str) == 1 and (hotkey_str.isalpha() or hotkey_str.isdigit()):
                    return hotkey_str.lower()
                # 特殊键
                elif hotkey_str == 'Space':
                    return '<space>'
                elif hotkey_str == 'Esc':
                    return '<esc>'
                else:
                    print(f"无法转换单个按键: {hotkey_str}")
                    return None
            
            parts = hotkey_str.split('+')
            if len(parts) < 2:
                return None
            
            # 转换映射
            convert_map = {
                'Ctrl': '<ctrl>',
                'Alt': '<alt>', 
                'Shift': '<shift>',
                'Win': '<cmd>',
                'Space': '<space>',
                'Esc': '<esc>'
            }
            
            converted_parts = []
            for part in parts:
                if part in convert_map:
                    converted_parts.append(convert_map[part])
                elif part.startswith('F') and part[1:].isdigit():
                    converted_parts.append(f'<{part.lower()}>')
                elif len(part) == 1 and (part.isalpha() or part.isdigit()):
                    converted_parts.append(part.lower())
                else:
                    print(f"无法转换的按键部分: {part}")
                    return None
            
            result = '+'.join(converted_parts)
            print(f"快捷键转换: {hotkey_str} -> {result}")
            return result
            
        except Exception as e:
            print(f"快捷键格式转换失败: {e}")
            return None
    
    def convert_hotkey_format(self, hotkey_str):
        """将用户输入的快捷键格式转换为pynput格式"""
        try:
            parts = hotkey_str.lower().strip().split('+')
            if len(parts) < 2:
                return None
            
            # 映射修饰键
            modifier_map = {
                'ctrl': '<ctrl>',
                'alt': '<alt>',
                'shift': '<shift>',
                'win': '<cmd>',
                'cmd': '<cmd>'
            }
            
            # 映射特殊键
            key_map = {
                'space': '<space>',
                'enter': '<enter>',
                'tab': '<tab>',
                'esc': '<esc>',
                'escape': '<esc>',
                'backspace': '<backspace>',
                'delete': '<delete>',
                'home': '<home>',
                'end': '<end>',
                'pageup': '<page_up>',
                'pagedown': '<page_down>',
                'up': '<up>',
                'down': '<down>',
                'left': '<left>',
                'right': '<right>'
            }
            
            converted_parts = []
            
            # 处理修饰键
            for part in parts[:-1]:
                part = part.strip()
                if part in modifier_map:
                    converted_parts.append(modifier_map[part])
                else:
                    return None
            
            # 处理主键
            main_key = parts[-1].strip()
            if main_key in key_map:
                converted_parts.append(key_map[main_key])
            elif len(main_key) == 1 and main_key.isalnum():
                # 单个字母或数字
                converted_parts.append(main_key)
            elif main_key.startswith('f') and main_key[1:].isdigit():
                # 功能键 f1-f12
                converted_parts.append(f'<{main_key}>')
            else:
                return None
            
            return '+'.join(converted_parts)
            
        except Exception as e:
            print(f"快捷键格式转换失败: {e}")
            return None
    
    def hotkey_record_position(self):
        """快捷键触发的记录位置"""
        if not self.hotkey_pressed:
            self.hotkey_pressed = True
            # 使用after方法在主线程中执行
            self.root.after(0, self._record_position_from_hotkey)
    
    def _record_position_from_hotkey(self):
        """在主线程中记录位置"""
        self.record_position()
        self.hotkey_pressed = False
    
    def set_hotkey(self):
        """设置新的快捷键"""
        new_hotkey = self.hotkey_var.get().strip().lower()
        if not new_hotkey:
            messagebox.showwarning("警告", "请输入快捷键！")
            return
        
        # 验证快捷键格式
        if not self.validate_hotkey(new_hotkey):
            messagebox.showerror("错误", 
                "快捷键格式不正确！\n\n"
                "支持的格式示例：\n"
                "• ctrl+shift+r\n"
                "• alt+f1\n" 
                "• ctrl+alt+c\n"
                "• shift+space\n\n"
                "修饰键：ctrl, alt, shift, win\n"
                "主键：a-z, 0-9, f1-f12, space, enter等")
            return
        
        # 测试快捷键是否能正确转换
        converted = self.convert_hotkey_format(new_hotkey)
        if not converted:
            messagebox.showerror("错误", f"快捷键 '{new_hotkey}' 无法识别，请使用其他组合！")
            return
        
        self.current_hotkey = new_hotkey
        self.start_hotkey_listener()
        messagebox.showinfo("成功", f"快捷键已设置为: {new_hotkey}\n转换格式: {converted}")
    
    def validate_hotkey(self, hotkey_str):
        """验证快捷键格式"""
        try:
            parts = hotkey_str.split('+')
            if len(parts) < 2:
                return False
            
            valid_modifiers = ['ctrl', 'alt', 'shift', 'cmd', 'win']
            valid_keys = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 
                         'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                         'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                         '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 
                         'space', 'enter', 'tab', 'esc', 'escape', 'backspace', 'delete',
                         'home', 'end', 'pageup', 'pagedown', 'up', 'down', 'left', 'right']
            
            # 检查修饰键
            for part in parts[:-1]:
                if part.strip() not in valid_modifiers:
                    return False
            
            # 检查主键
            main_key = parts[-1].strip()
            if main_key not in valid_keys:
                return False
            
            return True
        except:
            return False

    def start_key_capture_listener(self):
        """启动键盘监听（用于快捷键捕获）"""
        try:
            self.key_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release
            )
            self.key_listener.start()
        except Exception as e:
            print(f"键盘监听启动失败: {e}")
    
    def capture_hotkey(self):
        """开始或取消捕获快捷键"""
        if self.capturing_hotkey:
            # 当前正在捕获，点击取消
            self.cancel_capture()
        else:
            # 开始捕获快捷键
            self.capturing_hotkey = True
            self.temp_keys.clear()
            
            # 更新按钮和提示文本
            self.record_hotkey_btn.config(text="取消")
            self.tip_label.config(text="💡点击取消修改")
    
    def cancel_capture(self):
        """取消快捷键捕获"""
        if self.capturing_hotkey:
            self.capturing_hotkey = False
            self.temp_keys.clear()
            # 恢复按钮文本和提示
            self.record_hotkey_btn.config(text=self.current_hotkey)
            self.tip_label.config(text="💡点击修改快捷键")
    
    def on_key_press(self, key):
        """键盘按下事件"""
        if self.capturing_hotkey:
            try:
                # 转换键名
                key_name = self.get_key_name(key)
                if key_name:  # 包括"无效按键"
                    self.temp_keys.add(key_name)
                    # 实时更新按钮显示
                    self.update_capture_display()
            except Exception as e:
                print(f"按键处理错误: {e}")
    
    def on_key_release(self, key):
        """键盘释放事件"""
        if self.capturing_hotkey:
            try:
                # 当释放键时，如果有按键组合就检查并应用
                if self.temp_keys:
                    # 检查无效状态
                    invalid_status = self.check_invalid_combination(self.temp_keys)
                    
                    if invalid_status == "valid":
                        # 只有完全有效的组合才应用
                        hotkey_str = self.format_hotkey(self.temp_keys)
                        if hotkey_str and self.is_valid_hotkey_combination(self.temp_keys):
                            self.apply_captured_hotkey(hotkey_str)
                            return
                    elif invalid_status == "completely_invalid":
                        # 完全无效，清空并重新开始
                        self.temp_keys.clear()
                        self.update_capture_display()
                        return
                    # partially_invalid 的情况继续显示，让用户看到无效按键
                
                # 移除释放的键
                key_name = self.get_key_name(key)
                if key_name and key_name in self.temp_keys:
                    self.temp_keys.discard(key_name)
                    # 更新显示
                    self.update_capture_display()
                    
            except Exception as e:
                print(f"快捷键应用错误: {e}")
    
    def update_capture_display(self):
        """更新捕获过程中的显示"""
        if self.capturing_hotkey:
            if self.temp_keys:
                # 检查是否有完全无效的组合
                invalid_status = self.check_invalid_combination(self.temp_keys)
                
                if invalid_status == "completely_invalid":
                    # 完全无效的组合
                    self.record_hotkey_btn.config(text="取消")
                    self.tip_label.config(text="💡按键无效")
                    return
                
                # 格式化显示文本
                display_text = self.format_hotkey_with_invalid(self.temp_keys)
                if display_text:
                    # 如果是完整的快捷键组合，显示它并提示松开确认
                    if not display_text.endswith('+'):
                        self.record_hotkey_btn.config(text=display_text)
                        if "无效按键" in display_text:
                            self.tip_label.config(text=f"{display_text}(松开重试)")
                        else:
                            self.tip_label.config(text=f"{display_text}(松开确认)")
                    else:
                        # 如果只是控制键，显示"取消"但在提示中显示当前状态
                        self.record_hotkey_btn.config(text="取消")
                        modifier_text = display_text[:-1]  # 去掉末尾的'+'
                        if "无效按键" in modifier_text:
                            self.tip_label.config(text=f"{modifier_text}+...(松开重试)")
                        else:
                            self.tip_label.config(text=f"{modifier_text}+...(松开确认)")
                else:
                    self.record_hotkey_btn.config(text="取消")
            else:
                self.record_hotkey_btn.config(text="取消")
                self.tip_label.config(text="💡点击取消修改")
    
    def check_invalid_combination(self, keys):
        """检查按键组合的无效状态"""
        # 规则1：按键同时按下大于3个
        if len(keys) > 3:
            return "completely_invalid"
        
        # 分离控制键、字母键和无效按键
        control_keys = []
        letter_keys = []
        invalid_keys = []
        
        valid_control_keys = ['Ctrl', 'Shift', 'Alt', 'Win']
        valid_letter_keys = set()
        
        # 字母A-Z
        for i in range(26):
            valid_letter_keys.add(chr(ord('A') + i))
        
        # 数字0-9
        for i in range(10):
            valid_letter_keys.add(str(i))
        
        # 功能键F1-F12
        for i in range(1, 13):
            valid_letter_keys.add(f'F{i}')
        
        # 特殊字母键：Space和Esc
        valid_letter_keys.update(['Space', 'Esc'])
        
        for key in keys:
            if key in valid_control_keys:
                if key not in control_keys:  # 避免重复
                    control_keys.append(key)
            elif key in valid_letter_keys:
                letter_keys.append(key)
            elif key == "无效按键":
                invalid_keys.append(key)
        
        # 规则2：同时按下3个控制键
        if len(control_keys) >= 3:
            return "completely_invalid"
        
        # 规则3：同时按下>1个字母键
        if len(letter_keys) > 1:
            return "completely_invalid"
        
        # 如果有无效按键但其他条件满足，返回部分无效
        if invalid_keys:
            return "partially_invalid"
        
        return "valid"
    
    def format_hotkey_with_invalid(self, keys):
        """格式化快捷键字符串，包含无效按键处理"""
        if not keys:
            return None
        
        # 分离控制键、字母键和无效按键
        control_keys = []
        letter_keys = []
        invalid_keys = []
        
        valid_control_keys = ['Ctrl', 'Shift', 'Alt', 'Win']
        valid_letter_keys = set()
        
        # 字母A-Z
        for i in range(26):
            valid_letter_keys.add(chr(ord('A') + i))
        
        # 数字0-9
        for i in range(10):
            valid_letter_keys.add(str(i))
        
        # 功能键F1-F12
        for i in range(1, 13):
            valid_letter_keys.add(f'F{i}')
        
        # 特殊字母键
        valid_letter_keys.update(['Space', 'Esc'])
        
        for key in keys:
            if key in valid_control_keys:
                if key not in control_keys:  # 避免重复
                    control_keys.append(key)
            elif key in valid_letter_keys:
                letter_keys.append(key)
            elif key == "无效按键":
                invalid_keys.append(key)
        
        # 按指定顺序排列控制键：Ctrl > Shift > Alt > Win
        control_order = ['Ctrl', 'Shift', 'Alt', 'Win']
        sorted_controls = [ctrl for ctrl in control_order if ctrl in control_keys]
        
        # 构建显示文本
        parts = sorted_controls.copy()
        
        # 添加无效按键
        if invalid_keys:
            parts.extend(invalid_keys)
        
        # 添加字母键
        if letter_keys:
            parts.extend(letter_keys)
        
        # 如果只有控制键（可能包含无效按键），显示控制键+（用于实时显示）
        if (sorted_controls or invalid_keys) and not letter_keys:
            return '+'.join(parts) + '+'
        
        # 如果有字母键或无效按键作为最后一个
        if parts:
            return '+'.join(parts)
        
        return None
    
    def is_valid_hotkey_combination(self, keys):
        """检查是否是有效的快捷键组合"""
        if not keys or len(keys) > 3:  # 最多3个按键
            return False
        
        # 分离控制键和字母键
        control_keys = []
        letter_keys = []
        
        valid_control_keys = ['Ctrl', 'Shift', 'Alt', 'Win']
        valid_letter_keys = set()
        
        # 字母A-Z
        for i in range(26):
            valid_letter_keys.add(chr(ord('A') + i))
        
        # 数字0-9
        for i in range(10):
            valid_letter_keys.add(str(i))
        
        # 功能键F1-F12
        for i in range(1, 13):
            valid_letter_keys.add(f'F{i}')
        
        # 特殊字母键：Space和Esc
        valid_letter_keys.update(['Space', 'Esc'])
        
        for key in keys:
            if key in valid_control_keys:
                if key not in control_keys:  # 避免重复
                    control_keys.append(key)
            elif key in valid_letter_keys:
                letter_keys.append(key)
            else:
                return False  # 无效按键
        
        # 验证规则
        # 1. 最多只能有一个字母键
        if len(letter_keys) > 1:
            return False
        
        # 2. 控制键最多2个
        if len(control_keys) > 2:
            return False
        
        # 3. 不允许只使用控制键，若使用控制键必须存在字母键
        if control_keys and not letter_keys:
            return False
        
        # 4. Esc不能单独使用，必须搭配控制键
        if letter_keys and letter_keys[0] == 'Esc' and not control_keys:
            return False
        
        # 5. 必须至少有一个字母键
        if not letter_keys:
            return False
        
        return True
    
    def get_key_name(self, key):
        """获取标准化的键名"""
        try:
            # 控制键映射 - 添加更多的键映射以确保兼容性
            control_keys = {
                keyboard.Key.ctrl_l: 'Ctrl',
                keyboard.Key.ctrl_r: 'Ctrl',
                keyboard.Key.ctrl: 'Ctrl',  # 添加通用Ctrl键
                keyboard.Key.shift_l: 'Shift',
                keyboard.Key.shift_r: 'Shift',
                keyboard.Key.shift: 'Shift',  # 添加通用Shift键
                keyboard.Key.alt_l: 'Alt',
                keyboard.Key.alt_r: 'Alt',
                keyboard.Key.alt: 'Alt',  # 添加通用Alt键
                keyboard.Key.cmd: 'Win',
                keyboard.Key.cmd_l: 'Win',  # 添加左Win键
                keyboard.Key.cmd_r: 'Win'   # 添加右Win键
            }
            
            # 特殊字母键映射
            special_letter_keys = {
                keyboard.Key.space: 'Space',
                keyboard.Key.esc: 'Esc'
            }
            
            if key in control_keys:
                return control_keys[key]
            
            if key in special_letter_keys:
                return special_letter_keys[key]
            
            # 尝试通过键的vk属性识别（Windows特有）- 优先使用VK码
            if hasattr(key, 'vk'):
                vk_code = key.vk
                # 字母键A-Z的VK码是65-90
                if 65 <= vk_code <= 90:
                    return chr(vk_code)
                # 数字键0-9的VK码是48-57
                elif 48 <= vk_code <= 57:
                    return str(vk_code - 48)
                # 功能键F1-F12的VK码是112-123
                elif 112 <= vk_code <= 123:
                    return f'F{vk_code - 111}'
            
            # 功能键 F1-F12 - 改进处理逻辑
            if hasattr(key, 'name') and key.name:
                key_name = key.name.lower()
                if key_name.startswith('f') and len(key_name) >= 2:
                    try:
                        f_num = int(key_name[1:])
                        if 1 <= f_num <= 12:
                            return f'F{f_num}'  # F1, F2, etc.
                    except ValueError:
                        pass
            
            # 普通字符键（字母和数字）- 作为备用方案
            if hasattr(key, 'char') and key.char:
                char = key.char
                # 跳过控制字符（ASCII < 32），这些应该由VK码处理
                if ord(char) < 32:
                    pass  # 跳过控制字符，让VK码处理
                # 字母A-Z（只处理可打印的字母）
                elif char.isalpha():
                    return char.upper()
                # 数字0-9
                elif char.isdigit():
                    return char
                else:
                    print(f"不支持的字符键: '{char}' (ASCII: {ord(char)})")
                    return "无效按键"
                
            # 调试信息 - 帮助识别未知按键
            print(f"未识别的按键: {key}")
            print(f"  类型: {type(key)}")
            if hasattr(key, 'name'):
                print(f"  名称: {key.name}")
            if hasattr(key, 'char'):
                print(f"  字符: {key.char} (ASCII: {ord(key.char) if key.char else 'None'})")
            if hasattr(key, 'vk'):
                print(f"  VK码: {key.vk}")
            
            # 其他按键返回"无效按键"标记
            return "无效按键"
        except Exception as e:
            print(f"get_key_name异常: {e}")
            return "无效按键"
    
    def format_hotkey(self, keys):
        """格式化快捷键字符串"""
        if not keys:
            return None
        
        # 分离控制键和字母键
        control_keys = []
        letter_keys = []
        
        valid_control_keys = ['Ctrl', 'Shift', 'Alt', 'Win']
        
        for key in keys:
            if key in valid_control_keys:
                if key not in control_keys:  # 避免重复
                    control_keys.append(key)
            else:
                letter_keys.append(key)
        
        # 按指定顺序排列控制键：Ctrl > Shift > Alt > Win
        control_order = ['Ctrl', 'Shift', 'Alt', 'Win']
        sorted_controls = [ctrl for ctrl in control_order if ctrl in control_keys]
        
        # 如果只有控制键，显示控制键+（用于实时显示）
        if sorted_controls and not letter_keys:
            return '+'.join(sorted_controls) + '+'
        
        # 如果有字母键
        if letter_keys:
            if sorted_controls:
                # 控制键+字母键
                parts = sorted_controls + [letter_keys[0]]
                return '+'.join(parts)
            else:
                # 只有字母键
                return letter_keys[0]
        
        return None
    
    def apply_captured_hotkey(self, hotkey_str):
        """应用捕获的快捷键"""
        try:
            # 验证快捷键格式
            if not hotkey_str or hotkey_str.endswith('+'):
                # 无效快捷键，保持捕获状态让用户继续尝试
                self.tip_label.config(text="💡请输入完整的快捷键组合")
                return
            
            # 测试快捷键是否能正确转换为pynput格式
            pynput_format = self.convert_to_pynput_format(hotkey_str)
            if not pynput_format:
                # 无效快捷键，保持捕获状态让用户继续尝试
                self.tip_label.config(text=f"💡快捷键 '{hotkey_str}' 无效，请重新输入")
                return
            
            # 清理捕获状态
            self.capturing_hotkey = False
            self.temp_keys.clear()
            
            # 更新记录位置快捷键
            self.current_hotkey = hotkey_str
            self.record_hotkey_btn.config(text=hotkey_str)
            self.tip_label.config(text="💡点击修改快捷键")
            
            # 重新启动快捷键监听
            self.start_hotkey_listener()
            
            # 添加日志
            self.add_log(f"快捷键已更新: 记录位置({hotkey_str}), 停止连点(Esc)")
            messagebox.showinfo("成功", f"记录位置快捷键已设置为: {hotkey_str}")
            
        except Exception as e:
            # 发生错误时恢复界面状态
            self.tip_label.config(text=f"💡设置失败: {str(e)}")
            messagebox.showerror("错误", f"快捷键设置失败: {str(e)}")
    
    def record_position(self):
        """记录当前鼠标位置"""
        # 获取当前鼠标位置
        x, y = pyautogui.position()
        
        # 询问用户给位置命名
        name = simpledialog.askstring("位置命名", f"请为位置 ({x}, {y}) 命名:", 
                                    initialvalue=f"位置{len(self.positions)+1}")
        
        if name:  # 用户输入了名称
            position = {"name": name, "x": x, "y": y}
            
            # 添加到位置列表
            self.positions.append(position)
            
            # 更新界面显示
            self.update_position_list()
            
            # 添加日志
            self.add_log(f"已记录位置: {name} ({x}, {y}) - 共 {len(self.positions)} 个位置")
            print(f"记录位置: {name} ({x}, {y}), 总位置数: {len(self.positions)}")  # 调试信息
    
    def update_position_list(self):
        """更新位置列表显示"""
        self.position_listbox.delete(0, tk.END)
        for i, pos in enumerate(self.positions):
            if isinstance(pos, dict):
                # 新格式：字典
                self.position_listbox.insert(tk.END, f"{i+1}. {pos['name']} - ({pos['x']}, {pos['y']})")
            else:
                # 旧格式兼容：元组
                self.position_listbox.insert(tk.END, f"{i+1}. 位置 - ({pos[0]}, {pos[1]})")
    
    def delete_selected_position_btn(self):
        """删除选中的位置（按钮触发）"""
        selection = self.position_listbox.curselection()
        if selection:
            index = selection[0]
            pos = self.positions[index]
            pos_name = pos['name'] if isinstance(pos, dict) else f"位置{index+1}"
            
            if messagebox.askyesno("确认删除", f"确定要删除 '{pos_name}' 吗？"):
                del self.positions[index]
                self.update_position_list()
                self.add_log(f"已删除位置: {pos_name} - 剩余 {len(self.positions)} 个位置")
        else:
            messagebox.showwarning("提示", "请先选择要删除的位置！")
    
    def delete_selected_position(self, event):
        """删除选中的位置（双击触发）"""
        selection = self.position_listbox.curselection()
        if selection:
            index = selection[0]
            pos = self.positions[index]
            pos_name = pos['name'] if isinstance(pos, dict) else f"位置{index+1}"
            
            if messagebox.askyesno("确认删除", f"确定要删除 '{pos_name}' 吗？"):
                del self.positions[index]
                self.update_position_list()
                self.add_log(f"已删除位置: {pos_name} - 剩余 {len(self.positions)} 个位置")
    
    def rename_selected_position(self):
        """重命名选中的位置"""
        selection = self.position_listbox.curselection()
        if selection:
            index = selection[0]
            pos = self.positions[index]
            
            if isinstance(pos, dict):
                old_name = pos['name']
                new_name = simpledialog.askstring("重命名位置", 
                                                f"请输入新名称:", 
                                                initialvalue=old_name)
                if new_name and new_name != old_name:
                    self.positions[index]['name'] = new_name
                    self.update_position_list()
                    self.add_log(f"已将 '{old_name}' 重命名为 '{new_name}'")
            else:
                # 旧格式转换为新格式
                x, y = pos
                new_name = simpledialog.askstring("重命名位置", 
                                                f"请为位置 ({x}, {y}) 命名:", 
                                                initialvalue=f"位置{index+1}")
                if new_name:
                    self.positions[index] = {"name": new_name, "x": x, "y": y}
                    self.update_position_list()
                    self.add_log(f"已命名为 '{new_name}'")
        else:
            messagebox.showwarning("提示", "请先选择要重命名的位置！")
    
    def save_preset(self):
        """保存当前设置为预设"""
        if not self.positions:
            messagebox.showwarning("警告", "请先添加至少一个点击位置！")
            return
        
        name = simpledialog.askstring("保存预设", "请输入预设名称:")
        if name:
            preset_data = {
                "name": name,
                "frequency": float(self.frequency_entry.get()),
                "frequency_unit": self.freq_unit.get(),
                "mouse_button": self.mouse_button.get(),
                "positions": self.positions.copy(),  # 现在支持新的字典格式
                "hotkey": self.current_hotkey,
                "window_topmost": self.is_topmost  # 保存置顶设置
            }
            
            # 保存到文件
            self.save_preset_to_file(preset_data)
            
            # 更新预设列表
            self.update_preset_combo()
            
            messagebox.showinfo("成功", f"预设 '{name}' 已保存！")
    
    def rename_preset(self):
        """重命名预设"""
        current_name = self.preset_var.get()
        if not current_name:
            messagebox.showwarning("警告", "请先选择要重命名的预设！")
            return
        
        new_name = simpledialog.askstring("重命名预设", f"请输入新的预设名称:", initialvalue=current_name)
        if new_name and new_name != current_name:
            presets = self.load_presets_from_file()
            if current_name in presets:
                # 检查新名称是否已存在
                if new_name in presets:
                    messagebox.showerror("错误", f"预设名称 '{new_name}' 已存在！")
                    return
                
                # 重命名预设
                preset_data = presets[current_name].copy()
                preset_data["name"] = new_name
                presets[new_name] = preset_data
                del presets[current_name]
                
                try:
                    with open(self.presets_file, 'w', encoding='utf-8') as f:
                        json.dump(presets, f, ensure_ascii=False, indent=2)
                    
                    # 更新界面
                    self.update_preset_combo()
                    self.preset_var.set(new_name)
                    messagebox.showinfo("成功", f"预设已重命名为: {new_name}")
                except Exception as e:
                    messagebox.showerror("错误", f"重命名预设失败: {str(e)}")
    
    def save_preset_to_file(self, preset_data):
        """保存预设到文件"""
        presets = self.load_presets_from_file()
        presets[preset_data["name"]] = preset_data
        
        try:
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(presets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("错误", f"保存预设失败: {str(e)}")
    
    def load_presets_from_file(self):
        """从文件加载预设"""
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载预设文件失败: {e}")
        return {}
    
    def load_presets(self):
        """加载预设到界面"""
        self.update_preset_combo()
    
    def update_preset_combo(self):
        """更新预设下拉框"""
        presets = self.load_presets_from_file()
        preset_names = list(presets.keys())
        self.preset_combo['values'] = preset_names
        
        if preset_names and not self.preset_var.get():
            self.preset_combo.set(preset_names[0])
    
    def load_selected_preset(self, event=None):
        """加载选中的预设"""
        preset_name = self.preset_var.get()
        if not preset_name:
            return
        
        presets = self.load_presets_from_file()
        if preset_name in presets:
            preset = presets[preset_name]
            
            # 应用预设设置
            frequency = preset.get("frequency", 1.0)
            frequency_unit = preset.get("frequency_unit", "秒/次")
            
            # 更新频率设置
            self.frequency_entry.delete(0, tk.END)
            self.frequency_entry.insert(0, f"{frequency:.1f}")
            self.freq_unit.set(frequency_unit)
            self.frequency_var.set(frequency)
            
            # 更新其他设置
            self.mouse_button.set(preset.get("mouse_button", "left"))
            self.positions = preset.get("positions", []).copy()
            
            # 更新快捷键（如果有保存）
            if "hotkey" in preset:
                self.current_hotkey = preset["hotkey"]
                self.record_hotkey_btn.config(text=self.current_hotkey)
                self.start_hotkey_listener()
            
            # 更新置顶设置（如果有保存）
            if "window_topmost" in preset:
                is_topmost = preset["window_topmost"]
                self.is_topmost = is_topmost
                self.root.attributes('-topmost', is_topmost)
                self.update_window_title()
                
                # 同时保存到全局设置
                self.save_topmost_setting(is_topmost)
            
            # 更新界面
            self.update_position_list()
            
            # 添加日志
            self.add_log(f"已加载预设: {preset_name}")
    
    def delete_preset(self):
        """删除选中的预设"""
        preset_name = self.preset_var.get()
        if not preset_name:
            messagebox.showwarning("警告", "请先选择要删除的预设！")
            return
        
        if messagebox.askyesno("确认", f"确定要删除预设 '{preset_name}' 吗？"):
            presets = self.load_presets_from_file()
            if preset_name in presets:
                del presets[preset_name]
                
                try:
                    with open(self.presets_file, 'w', encoding='utf-8') as f:
                        json.dump(presets, f, ensure_ascii=False, indent=2)
                    
                    self.update_preset_combo()
                    self.preset_var.set("")
                    messagebox.showinfo("成功", f"预设 '{preset_name}' 已删除！")
                except Exception as e:
                    messagebox.showerror("错误", f"删除预设失败: {str(e)}")
    
    def start_clicking(self):
        """开始自动点击"""
        if not self.positions:
            messagebox.showwarning("警告", "请先添加至少一个点击位置！")
            return
        
        if self.is_clicking:
            return
        
        self.is_clicking = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # 启动点击线程
        self.click_thread = threading.Thread(target=self.clicking_loop, daemon=True)
        self.click_thread.start()
        
        # 添加日志
        self.add_log("开始连点...")
    
    def stop_clicking(self):
        """停止自动点击"""
        self.is_clicking = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        # 添加日志
        self.add_log("停止连点")
    
    def stop_clicking_and_focus(self):
        """停止连点并将窗口置顶"""
        # 先停止连点
        self.stop_clicking()
        
        # 将窗口置顶并获得焦点
        try:
            self.root.lift()  # 将窗口提升到最顶层
            self.root.attributes('-topmost', True)  # 临时置顶
            self.root.after(100, lambda: self.root.attributes('-topmost', False))  # 100ms后取消置顶
            self.root.focus_force()  # 强制获得焦点
        except Exception as e:
            print(f"窗口置顶失败: {e}")
    
    def clicking_loop(self):
        """点击循环（在单独线程中运行）"""
        position_index = 0
        
        while self.is_clicking:
            try:
                # 在每次循环开始时检查停止标志
                if not self.is_clicking:
                    break
                
                # 获取当前要点击的位置
                if self.positions:
                    pos = self.positions[position_index]
                    
                    # 兼容新旧格式
                    if isinstance(pos, dict):
                        x, y = pos['x'], pos['y']
                        pos_name = pos['name']
                    else:
                        x, y = pos
                        pos_name = f"位置{position_index+1}"
                    
                    # 再次检查停止标志，防止在移动鼠标时停止
                    if not self.is_clicking:
                        break
                    
                    # 先移动鼠标到目标位置（使用pyautogui获取位置信息）
                    pyautogui.moveTo(x, y, duration=0.1)
                    
                    # 在点击前最后一次检查停止标志
                    if not self.is_clicking:
                        break
                    
                    # 执行点击 - 使用增强的点击方法
                    button_type = 'left' if self.mouse_button.get() == "left" else 'right'
                    click_success = enhanced_click(x, y, button_type)
                    
                    # 如果测试窗口存在，显示点击动画
                    if (hasattr(self, 'test_window') and self.test_window and 
                        hasattr(self.test_window, 'window') and self.test_window.window.winfo_exists()):
                        self.root.after(0, lambda: self.test_window.show_click_animation(x, y))
                    
                    # 获取等待间隔
                    interval = self.get_click_interval()
                    
                    # 添加日志 - 在主线程中执行
                    click_method = "Windows API" if click_success else "备用方法"
                    log_msg = f"已点击位置: {pos_name} ({x}, {y}), 按键: {self.mouse_button.get()}, 方法: {click_method}, 等待间隔: {interval}秒"
                    self.root.after(0, lambda msg=log_msg: self.add_log(msg))
                    
                    print(f"已点击位置: {pos_name} ({x}, {y}), 按键: {self.mouse_button.get()}")  # 调试信息
                    
                    # 切换到下一个位置（循环）
                    position_index = (position_index + 1) % len(self.positions)
                
                # 等待指定间隔，但要分段检查停止标志
                print(f"等待间隔: {interval}秒")  # 调试信息
                
                # 将等待时间分成小段，每100ms检查一次停止标志
                wait_time = 0
                sleep_interval = 0.1  # 每次睡眠100ms
                while wait_time < interval and self.is_clicking:
                    time.sleep(sleep_interval)
                    wait_time += sleep_interval
                
            except Exception as e:
                print(f"点击过程中发生错误: {e}")
                # 发生错误时停止点击并记录日志
                error_msg = f"点击过程中发生错误: {e}"
                self.root.after(0, lambda msg=error_msg: self.add_log(msg))
                self.root.after(0, self.stop_clicking)
                break
    
    def save_version_info(self):
        """保存版本信息"""
        try:
            with open(VERSION_FILE, 'w', encoding='utf-8') as f:
                f.write(VERSION)
        except:
            pass
    
    def on_closing(self):
        """程序关闭时的处理"""
        if self.is_clicking:
            self.stop_clicking()
        
        # 停止快捷键监听
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except:
                pass
        
        # 停止Esc键监听
        if hasattr(self, 'esc_listener') and self.esc_listener:
            try:
                self.esc_listener.stop()
            except:
                pass
        
        # 停止键盘监听
        if hasattr(self, 'key_listener'):
            try:
                self.key_listener.stop()
            except:
                pass
        
        self.root.destroy()
    
    def run(self):
        """运行程序"""
        self.root.mainloop()
    
    def open_test_window(self):
        """打开测试窗口"""
        if self.test_window and self.test_window.winfo_exists():
            # 如果测试窗口已存在，将其置顶
            self.test_window.lift()
            self.test_window.focus_force()
            return
        
        # 创建新的测试窗口
        self.test_window = TestWindow(self)
        self.add_log("已打开连点测试窗口")

class TestWindow:
    """连点测试窗口类"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        self.click_animations = []  # 点击动画列表
        self.tutorial_visible = True  # 教程文字是否可见
        
        # 创建测试窗口
        self.window = tk.Toplevel(main_app.root)
        self.window.title("连点测试 - TestTestTest")
        self.window.geometry("800x600")
        self.window.configure(bg='white')
        
        # 设置窗口属性
        self.window.resizable(True, True)
        
        # 绑定关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 创建画布用于显示点击效果和教程
        self.canvas = tk.Canvas(self.window, bg='white', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绑定窗口大小变化事件
        self.window.bind("<Configure>", self.on_window_resize)
        
        # 显示教程信息
        self.show_tutorial()
        
        # 启动动画更新
        self.update_animations()
        
        # 监听主程序的连点状态变化
        self.check_clicking_status()
    
    def show_tutorial(self):
        """显示使用教程"""
        if not self.tutorial_visible:
            return
            
        # 清除现有教程文字
        self.canvas.delete("tutorial")
        
        # 获取画布中心位置
        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        center_x = canvas_width // 2
        center_y = canvas_height // 2
        
        # 标题框 - 居中对齐
        title_y = center_y - 120
        self.canvas.create_text(center_x, title_y, 
                               text="点点点 - 使用教程", 
                               font=("微软雅黑", 20, "bold"), 
                               fill="black", tags="tutorial")
        
        # 正文框 - 整体居中，内容左对齐，增加行距
        content_start_y = center_y - 60
        content_left_x = center_x - 180  # 正文框的左边界
        line_spacing = 40  # 增加行距到40像素
        
        steps = [
            "1. 设置鼠标点击速率",
            "2. 记录鼠标位置（可记录多个位置）", 
            "3. 开始连点",
            "4. 可以将当前设置存储为预设"
        ]
        
        # 绘制正文内容，左对齐
        for i, step in enumerate(steps):
            self.canvas.create_text(content_left_x, content_start_y + i * line_spacing, 
                                   text=step, 
                                   font=("微软雅黑", 14), 
                                   fill="black", tags="tutorial",
                                   anchor="w")  # 左对齐
        
        # 底部提示框 - 居中对齐
        bottom_tip_y = content_start_y + len(steps) * line_spacing + 30
        self.canvas.create_text(center_x, bottom_tip_y, 
                               text="- 试着按照教程设置 连续点击这里的任意位置吧 -", 
                               font=("微软雅黑", 12), 
                               fill="gray", tags="tutorial")
    
    def hide_tutorial(self):
        """隐藏教程文字"""
        self.tutorial_visible = False
        self.canvas.delete("tutorial")
    
    def show_tutorial_if_stopped(self):
        """如果连点停止，重新显示教程"""
        if not self.main_app.is_clicking:
            self.tutorial_visible = True
            self.show_tutorial()
    
    def check_clicking_status(self):
        """检查主程序的连点状态"""
        if not self.window.winfo_exists():
            return
            
        # 如果开始连点，隐藏教程
        if self.main_app.is_clicking and self.tutorial_visible:
            self.hide_tutorial()
        
        # 如果停止连点，显示教程
        elif not self.main_app.is_clicking and not self.tutorial_visible:
            self.show_tutorial_if_stopped()
        
        # 继续检查状态
        self.window.after(500, self.check_clicking_status)
    
    def show_click_animation(self, screen_x, screen_y):
        """显示点击动画效果"""
        # 将屏幕坐标转换为窗口坐标
        window_x = screen_x - self.window.winfo_rootx()
        window_y = screen_y - self.window.winfo_rooty()
        
        # 检查坐标是否在窗口范围内
        if (0 <= window_x <= self.window.winfo_width() and 
            0 <= window_y <= self.window.winfo_height()):
            
            # 创建点击动画
            animation = ClickAnimation(self.canvas, window_x, window_y)
            self.click_animations.append(animation)
    
    def update_animations(self):
        """更新动画效果"""
        # 更新所有动画
        active_animations = []
        for animation in self.click_animations:
            if animation.update():
                active_animations.append(animation)
        
        self.click_animations = active_animations
        
        # 继续更新
        if self.window.winfo_exists():
            self.window.after(50, self.update_animations)
    
    def on_window_resize(self, event):
        """窗口大小变化事件"""
        # 如果教程可见，重新绘制教程以适应新的窗口大小
        if self.tutorial_visible:
            self.window.after(100, self.show_tutorial)  # 延迟一点确保窗口大小更新完成
    
    def on_closing(self):
        """关闭测试窗口"""
        self.main_app.test_window = None
        self.window.destroy()
        self.main_app.add_log("已关闭连点测试窗口")

class ClickAnimation:
    """点击动画效果类"""
    
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.radius = 5
        self.max_radius = 30
        self.alpha = 1.0
        self.growth_speed = 2
        self.fade_speed = 0.05
        
        # 创建动画圆圈
        self.circle = self.canvas.create_oval(
            x - self.radius, y - self.radius,
            x + self.radius, y + self.radius,
            outline="red", width=3, fill=""
        )
    
    def update(self):
        """更新动画状态，返回True表示动画继续，False表示动画结束"""
        # 扩大圆圈
        self.radius += self.growth_speed
        
        # 淡化效果
        self.alpha -= self.fade_speed
        
        if self.alpha <= 0 or self.radius >= self.max_radius:
            # 动画结束，删除圆圈
            self.canvas.delete(self.circle)
            return False
        
        # 更新圆圈大小和颜色
        self.canvas.coords(self.circle,
                          self.x - self.radius, self.y - self.radius,
                          self.x + self.radius, self.y + self.radius)
        
        # 计算颜色透明度（简化处理）
        intensity = int(255 * self.alpha)
        color = f"#{intensity:02x}0000"  # 红色渐变
        
        try:
            self.canvas.itemconfig(self.circle, outline=color)
        except:
            pass
        
        return True

def main():
    """主函数"""
    try:
        app = AutoClicker()
        app.run()
    except Exception as e:
        print(f"程序启动失败: {e}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()