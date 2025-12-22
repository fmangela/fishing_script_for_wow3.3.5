import cv2
import numpy as np
import pyautogui
import time
import threading
import sounddevice as sd
import os
from pynput import keyboard
import sys
from pathlib import Path


class WOWFishingBot:
    def __init__(self):
        # 参数配置
        self.fishing_key = '`'  # 默认钓鱼快捷键
        self.target_fish_count = 10  # 目标钓鱼次数
        self.max_retries = 5  # 最大重试次数
        self.screenshot_interval = 0.5  # 截图间隔
        self.sound_threshold = 80  # 声音检测阈值
        self.match_threshold = 0.7  # 图像匹配阈值

        # 状态变量
        self.is_running = False
        self.current_count = 0
        self.stop_flag = False
        self.pause_flag = False
        self.sound_detected = False

        # 鱼漂模板列表
        self.bobber_templates = []

        # 齿轮光标模板列表
        self.gear_cursor_templates = []

        # 截图保存路径
        self.temp_screenshot_path = 'temp_screenshot.png'

        # 注册键盘监听
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

        # 加载模板
        self.load_bobber_templates()
        self.load_gear_cursor_templates()

        # 声音检测线程
        self.audio_thread = None

    def on_press(self, key):
        try:
            if key.char == 'esc':
                print("程序终止")
                self.stop_flag = True
                sys.exit(0)
            elif key.char == 'delete':
                print("钓鱼中止，重置计数")
                self.pause_flag = True
                self.current_count = 0
        except AttributeError:
            pass

    def load_bobber_templates(self):
        """加载鱼漂模板图片"""
        fishing_float_dir = Path('fishing_float')
        if not fishing_float_dir.exists():
            print("警告：fishing_float目录不存在，请在同目录下创建该目录并放入鱼漂图片")
            return

        template_files = sorted(fishing_float_dir.glob('*.png'))
        for file_path in template_files:
            template = cv2.imread(str(file_path), 0)
            if template is not None:
                self.bobber_templates.append(template)
                print(f"加载鱼漂模板: {file_path.name}")

        if not self.bobber_templates:
            print("警告：未找到任何鱼漂模板图片，请确保fishing_float目录下有1.png, 2.png等文件")

    def load_gear_cursor_templates(self):
        """加载齿轮光标模板图片"""
        gear_cursor_dir = Path('gear_cursor')
        if not gear_cursor_dir.exists():
            print("警告：gear_cursor目录不存在，请在同目录下创建该目录并放入齿轮光标图片")
            return

        template_files = sorted(gear_cursor_dir.glob('*.png'))
        for file_path in template_files:
            template = cv2.imread(str(file_path), 0)
            if template is not None:
                self.gear_cursor_templates.append(template)
                print(f"加载齿轮光标模板: {file_path.name}")

        if not self.gear_cursor_templates:
            print("警告：未找到任何齿轮光标模板图片，请确保gear_cursor目录下有1.png, 2.png等文件")

    def detect_sound(self):
        """监听声音线程"""

        def audio_callback(indata):
            volume_norm = np.linalg.norm(indata) * 10
            if volume_norm > self.sound_threshold:
                self.sound_detected = True

        while not self.stop_flag:
            if self.is_running and not self.pause_flag:
                try:
                    with sd.InputStream(callback=audio_callback):
                        sd.sleep(int(1000))  # 每秒检测一次
                except Exception:
                    time.sleep(1)  # 如果音频设备有问题，等待后重试
            else:
                time.sleep(1)

    def find_bobber(self, screenshot):
        """查找鱼漂位置，使用多个模板进行匹配"""
        if not self.bobber_templates:
            return None

        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        best_match = None
        best_max_val = 0
        best_location = None

        # 尝试每个模板
        for template in self.bobber_templates:
            result = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # 如果找到更好的匹配
            if max_val > best_max_val and max_val >= self.match_threshold:
                best_max_val = max_val
                best_location = max_loc
                best_match = template

        if best_match is not None:
            # 计算鱼漂中心位置
            h, w = best_match.shape
            center_x = best_location[0] + w // 2
            center_y = best_location[1] + h // 2
            return center_x, center_y, best_max_val

        return None

    # def is_gear_cursor(self):
    #     """检查鼠标是否变为齿轮形状，使用多个模板进行匹配"""
    #     if not self.gear_cursor_templates:
    #         return False
    #
    #     # 获取鼠标附近的截图
    #     x, y = pyautogui.position()
    #     screenshot = pyautogui.screenshot(region=(x - 15, y - 15, 30, 30))
    #     screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    #
    #     gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    #
    #     # 尝试每个齿轮光标模板
    #     for gear_template in self.gear_cursor_templates:
    #         result = cv2.matchTemplate(gray_screenshot, gear_template, cv2.TM_CCOEFF_NORMED)
    #         min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    #
    #         # 如果匹配度足够高
    #         if max_val >= self.match_threshold:
    #             return True
    #
    #     return False

    def take_screenshot(self):
        """截取屏幕并保存到临时文件，覆盖之前的截图"""
        screenshot = pyautogui.screenshot()
        screenshot.save(self.temp_screenshot_path)
        return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    def fish_once(self):
        """执行一次钓鱼动作"""
        retries = 0

        while retries < self.max_retries and not self.stop_flag:
            # 按下钓鱼快捷键
            pyautogui.press(self.fishing_key)
            time.sleep(1)  # 等待鱼漂出现

            # 截图查找鱼漂（覆盖旧截图）
            screenshot = self.take_screenshot()

            bobber_info = self.find_bobber(screenshot)
            if bobber_info is None:
                print(f"第{retries + 1}次未找到鱼漂，重试...")
                retries += 1
                time.sleep(1)
                continue

            bobber_pos = (bobber_info[0], bobber_info[1])
            match_confidence = bobber_info[2]

            print(f"找到鱼漂，匹配置信度: {match_confidence:.2f}")

            # 移动鼠标到鱼漂位置
            pyautogui.moveTo(bobber_pos[0], bobber_pos[1])

            # # 检查是否变为齿轮光标
            # time.sleep(0.5)
            # if self.is_gear_cursor():
            #     print("检测到齿轮光标，等待鱼上钩...")
            #     break
            # else:
            #     print(f"第{retries + 1}次未检测到齿轮光标，重试...")
            #     retries += 1
            #     time.sleep(1)

        if retries >= self.max_retries:
            print("超过最大重试次数，跳过本次钓鱼")
            return False

        # 等待鱼上钩的声音
        print("等待鱼上钩...")
        start_time = time.time()
        timeout = 30  # 30秒超时

        while not self.sound_detected and time.time() - start_time < timeout and not self.stop_flag:
            time.sleep(0.1)

        if self.sound_detected:
            print("检测到鱼上钩声音，执行右键点击")
            pyautogui.rightClick()
            self.sound_detected = False  # 重置声音检测标志
            time.sleep(1)  # 等待钓鱼动作完成
            return True
        else:
            print("超时未检测到鱼上钩")
            return False

    def update_settings(self, fishing_key='f', target_count=10, max_retries=5,
                        sound_threshold=80, match_threshold=0.7):
        """更新设置"""
        self.fishing_key = fishing_key
        self.target_fish_count = target_count
        self.max_retries = max_retries
        self.sound_threshold = sound_threshold
        self.match_threshold = match_threshold

    def start_fishing(self):
        """开始钓鱼"""
        if not self.bobber_templates:
            print("错误：请先在fishing_float目录下放置鱼漂模板图片（1.png, 2.png等）")
            return

        if not self.gear_cursor_templates:
            print("错误：请先在gear_cursor目录下放置齿轮光标模板图片（1.png, 2.png等）")
            return

        print(f"开始钓鱼，目标数量：{self.target_fish_count}")
        print(f"使用的鱼漂模板数量：{len(self.bobber_templates)}")
        print(f"使用的齿轮光标模板数量：{len(self.gear_cursor_templates)}")
        print(f"声音检测阈值：{self.sound_threshold}")
        print(f"图像匹配阈值：{self.match_threshold}")
        self.is_running = True
        self.pause_flag = False
        self.current_count = 0

        # 启动声音监听线程
        self.audio_thread = threading.Thread(target=self.detect_sound, daemon=True)
        self.audio_thread.start()

        # 执行钓鱼循环
        while self.current_count < self.target_fish_count and not self.stop_flag:
            if not self.pause_flag:
                print(f"\n第 {self.current_count + 1}/{self.target_fish_count} 次钓鱼")

                success = self.fish_once()
                if success:
                    self.current_count += 1
                    print(f"成功钓鱼 {self.current_count}/{self.target_fish_count}")

                    # 钓鱼完成后等待一段时间
                    time.sleep(2)
                else:
                    print("钓鱼失败，继续下一次")
                    time.sleep(1)
            else:
                print("钓鱼暂停中...")
                time.sleep(1)

        self.is_running = False
        print("\n钓鱼完成！")


# 使用示例
if __name__ == "__main__":
    bot = WOWFishingBot()

    # 更新设置（可选）
    # bot.update_settings(
    #     fishing_key='f',          # 钓鱼快捷键
    #     target_count=5,           # 目标钓鱼数量
    #     max_retries=5,            # 最大重试次数
    #     sound_threshold=80,       # 声音检测阈值
    #     match_threshold=0.7       # 图像匹配阈值
    # )

    # 检查必要的文件
    if not os.path.exists('fishing_float'):
        print("\n请在当前目录创建fishing_float文件夹，并放入鱼漂图片")
        print("例如：fishing_float/1.png, fishing_float/2.png等")
    else:
        float_files = list(Path('fishing_float').glob('*.png'))
        print(f"\n已找到 {len(float_files)} 张鱼漂图片")

    # if not os.path.exists('gear_cursor'):
    #     print("\n请在当前目录创建gear_cursor文件夹，并放入齿轮光标图片")
    #     print("例如：gear_cursor/1.png, gear_cursor/2.png等")
    # else:
    #     cursor_files = list(Path('gear_cursor').glob('*.png'))
    #     print(f"已找到 {len(cursor_files)} 张齿轮光标图片")

    print("\n准备就绪，调用bot.start_fishing()开始钓鱼")

    # 示例用法：
    # bot.start_fishing()