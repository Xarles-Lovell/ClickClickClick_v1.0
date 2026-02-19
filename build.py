#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
点点点打包脚本
使用PyInstaller将Python程序打包成exe文件
"""

import os
import sys
import subprocess
import shutil

def check_pyinstaller():
    """检查PyInstaller是否已安装"""
    try:
        import PyInstaller
        print("✓ PyInstaller已安装")
        return True
    except ImportError:
        print("✗ PyInstaller未安装")
        print("正在安装PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✓ PyInstaller安装成功")
            return True
        except subprocess.CalledProcessError:
            print("✗ PyInstaller安装失败")
            return False

def build_exe():
    """打包exe文件"""
    print("\n开始打包exe文件...")
    
    # PyInstaller命令参数
    cmd = [
        "pyinstaller",
        "--onefile",                    # 打包成单个exe文件
        "--windowed",                   # 不显示控制台窗口
        "--name=点点点_v1.0",  # exe文件名
        "--icon=image/cover_icon.png",  # 程序图标
        "--add-data=image/cover_icon.png;image",  # 明确包含窗口图标
        "--add-data=image/click_icon.png;image",  # 明确包含标题图标
        "--add-data=image/cover_icon.svg;image",  # 包含svg备用图标
        "--add-data=image/click_icon.svg;image",  # 包含svg备用图标
        "--hidden-import=PIL",          # 确保PIL库被包含
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=PIL.Image",    # 添加PIL.Image
        "--hidden-import=PIL.ImageTk",  # 添加PIL.ImageTk
        "点点点.py"               # 主程序文件
    ]
    
    try:
        subprocess.check_call(cmd)
        print("✓ 打包成功！")
        
        # 检查生成的文件
        exe_path = "dist/点点点_v1.0.exe"
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
            print(f"✓ 生成的exe文件: {exe_path}")
            print(f"✓ 文件大小: {size:.1f} MB")
            
            # 确保release文件夹存在
            release_dir = "release"
            if not os.path.exists(release_dir):
                os.makedirs(release_dir)
            
            # 直接复制exe文件到release文件夹
            release_exe_path = f"{release_dir}/点点点_v1.0.exe"
            shutil.copy2(exe_path, release_exe_path)
            print(f"✓ exe文件已复制到: {release_exe_path}")
            
            # 复制配置文件到release
            config_files = ["settings.json", "version.txt"]
            for config_file in config_files:
                if os.path.exists(config_file):
                    shutil.copy2(config_file, f"{release_dir}/{config_file}")
                    print(f"✓ 已复制配置文件: {config_file}")
            
            print(f"✓ 发布文件已准备在 {release_dir} 文件夹中")
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ 打包失败: {e}")
        return False

def clean_build_files():
    """清理构建文件"""
    print("\n清理构建文件...")
    
    dirs_to_remove = ["build", "__pycache__"]
    files_to_remove = ["点点点.spec"]
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✓ 已删除 {dir_name}")
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"✓ 已删除 {file_name}")

def main():
    print("=" * 50)
    print("           点点点 - 打包工具")
    print("=" * 50)
    
    # 检查依赖
    if not check_pyinstaller():
        print("请手动安装PyInstaller: pip install pyinstaller")
        return
    
    # 检查主程序文件
    if not os.path.exists("点点点.py"):
        print("✗ 未找到主程序文件 点点点.py")
        return
    
    # 检查图标文件
    if not os.path.exists("image/cover_icon.png"):
        print("⚠ 未找到图标文件，将使用默认图标")
    
    # 开始打包
    if build_exe():
        print("\n🎉 打包完成！")
        print("你可以在 release 文件夹中找到可执行文件")
        print("现在可以将 release 文件夹分享给朋友们了！")
    else:
        print("\n❌ 打包失败，请检查错误信息")
    
    # 清理构建文件
    clean_build_files()

if __name__ == "__main__":
    main()