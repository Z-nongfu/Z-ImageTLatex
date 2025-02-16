import os
import base64
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageGrab, ImageFilter
import screeninfo
from openai import OpenAI
import sys
import configparser
from pathlib import Path
import io
import re  # 新增正则处理
import pyperclip  # 新增剪贴板支持

# 新配置路径（根据打包状态选择路径）
if getattr(sys, 'frozen', False):
    # 打包后：存储在exe同级目录的config文件夹
    CONFIG_FILE = Path(sys.executable).parent / 'config' / 'config.ini'
else:
    # 开发环境：存储在用户目录
    CONFIG_FILE = Path.home() / '.config' / 'latex_converter' / 'config.ini'

# 确保配置目录存在
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

# 全局 OpenAI 客户端 (延迟初始化)
client = None


class ScreenshotSelector:
    def __init__(self, master):
        self.master = master
        # 底层事件窗口
        self.event_win = tk.Toplevel(master)
        self.event_win.attributes('-fullscreen', True)
        self.event_win.attributes('-alpha', 0.01)
        self.event_win.attributes('-topmost', True)
        self.event_win.overrideredirect(True)
        self.event_win.config(cursor='cross')

        # 可见绘制层
        self.draw_win = tk.Toplevel(self.event_win)
        self.draw_win.attributes('-fullscreen', True)
        self.draw_win.attributes('-alpha', 0.3)
        self.draw_win.attributes('-topmost', True)
        self.draw_win.overrideredirect(True)
        self.draw_win.attributes('-disabled', True)

        # 事件绑定
        self.event_win.bind('<ButtonPress-1>', self.on_press)
        self.event_win.bind('<B1-Motion>', self.on_drag)
        self.event_win.bind('<ButtonRelease-1>', self.on_release)
        self.event_win.bind('<Escape>', self.cancel)

        # 画布
        self.canvas = tk.Canvas(self.draw_win, bg='gray20', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.draw_screen_borders()

        self.start_x = self.start_y = 0
        self.rect = None
        self.selected_region = None
        self.current_monitor = None  # 当前鼠标所在显示器

    def draw_screen_borders(self):
        """绘制所有显示器的红色边界"""
        for monitor in screeninfo.get_monitors():
            x1, y1 = monitor.x, monitor.y
            x2, y2 = x1 + monitor.width, y1 + monitor.height
            self.canvas.create_rectangle(x1, y1, x2, y2, outline='#ff4444', width=3, dash=(5, 5))

    def on_press(self, event):
        self.event_win.config(cursor='cross')
        self.draw_win.config(cursor='cross')

        # 确定当前鼠标在哪一个显示器上
        self.current_monitor = self.get_current_monitor(event.x_root, event.y_root)

        if self.current_monitor:
            # 使用相对于当前显示器的坐标
            self.start_x = event.x_root
            self.start_y = event.y_root

            # 创建选区矩形
            self.rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline='#00ff00', width=2, dash=(3, 3)
            )

    def on_drag(self, event):
        if self.current_monitor:
            current_x = event.x_root
            current_y = event.y_root
            self.canvas.coords(self.rect, self.start_x, self.start_y, current_x, current_y)

    def on_release(self, event):
        self.event_win.config(cursor='')
        self.draw_win.config(cursor='')
        x, y = event.x_root, event.y_root
        x1, y1 = min(self.start_x, x), min(self.start_y, y)
        x2, y2 = max(self.start_x, x), max(self.start_y, y)
        self.selected_region = (x1, y1, x2 - x1, y2 - y1)
        self.draw_win.destroy()
        self.event_win.destroy()

    def get_current_monitor(self, x, y):
        """确定鼠标所在的显示器"""
        for monitor in screeninfo.get_monitors():
            if monitor.x <= x < monitor.x + monitor.width and monitor.y <= y < monitor.y + monitor.height:
                return monitor
        return None

    def cancel(self, event=None):
        self.selected_region = None
        if hasattr(self, 'draw_win') and self.draw_win:
            self.draw_win.destroy()
        if hasattr(self, 'event_win') and self.event_win:
            self.event_win.destroy()


class LatexConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Image to LaTeX")
        master.geometry("900x600")
        master.resizable(False, False)  # 禁止调整窗口大小
        master.configure(bg='#F5F5F7')

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#F5F5F7')
        self.style.configure('TButton', font=('San Francisco', 12), padding=8,
                             relief='flat', background='#007AFF', foreground='white')
        self.style.map('TButton', background=[('active', '#0063CC'), ('disabled', '#AEAEB2')])
        self.style.configure('Copied.TButton', 
                            background='#34C759',  # 成功颜色
                            foreground='white')

        # 主界面布局
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        # 图片预览区
        self.image_frame = ttk.LabelFrame(self.main_frame, text=" 图片预览 ", padding=15)
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.img_label = ttk.Label(self.image_frame)
        self.img_label.pack(fill=tk.BOTH, expand=True)

        # 操作按钮
        self.btn_frame = ttk.Frame(self.image_frame)
        self.btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(self.btn_frame, text="上传图片", command=self.upload_image).pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(self.btn_frame, text="区域截图", command=self.capture_screen).pack(side=tk.LEFT, expand=True, padx=5)

        # LaTeX结果区（尺寸缩小25%）
        self.result_frame = ttk.LabelFrame(self.main_frame, text=" LaTeX 代码 ", padding=10)
        self.result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))
        
        # 结果文本框（字体缩小25%）
        self.result_text = tk.Text(self.result_frame, font=('Menlo', 10), wrap=tk.WORD,
                                 padx=8, pady=8, highlightthickness=1)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        # 新增复制按钮（尺寸缩小25%）
        ttk.Button(
            self.result_frame,
            text="复制代码",
            command=self.copy_to_clipboard,
            style='TButton'
        ).pack(fill=tk.X, pady=5)

        # 加载动画
        self.loading_canvas = tk.Canvas(master, width=60, height=60, bg='#F5F5F7', highlightthickness=0)
        self.loading_angle = 0

        # 配置
        self.config = configparser.ConfigParser()
        self.create_toolbar()
        self.load_config()

        # 初始化全局客户端
        # self.update_client()  # 注释掉这行

    def show_loading(self):
        self.loading_canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        base_color = (100, 150, 255)

        def animate():
            self.loading_angle = (self.loading_angle + 12) % 360
            self.loading_canvas.delete("all")
            for i in range(12):
                angle = self.loading_angle + i * 30
                alpha = 0.8 - i * 0.07
                r = base_color[0] + int((255 - base_color[0]) * (1 - alpha))
                g = base_color[1] + int((255 - base_color[1]) * (1 - alpha))
                b = base_color[2] + int((255 - base_color[2]) * (1 - alpha))
                self.loading_canvas.create_arc(10, 10, 50, 50, start=angle, extent=25,
                                                outline=f'#{r:02x}{g:02x}{b:02x}', width=2, style=tk.ARC)
            self.loading_canvas.after(50, animate)

        animate()

    def hide_loading(self):
        self.loading_canvas.place_forget()

    def upload_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
        if file_path:
            self.process_image(file_path)

    def capture_screen(self):
        self.master.withdraw()
        self.master.update()
        selector = ScreenshotSelector(self.master)
        self.master.wait_window(selector.event_win)
        if selector.selected_region:
            self.master.after(300, lambda: self.final_capture(selector.selected_region))
        else:
            self.master.deiconify()

    def final_capture(self, region):
        try:
            x, y, w, h = region
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            screenshot.save(temp_file.name, "PNG")
            self.process_image(temp_file.name)
        except Exception as e:
            self.update_latex(f"截图失败: {e}")
        finally:
            self.master.deiconify()

    def preprocess_image(self, image_path):
        """图片预处理：等比例放大+锐化"""
        img = Image.open(image_path)
        
        # 转换为RGB模式（兼容JPEG）
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # 等比例放大（长边不超过2048，短边不超过1024）
        original_width, original_height = img.size
        target_long = 2048
        target_short = 1024
        
        # 计算缩放比例
        if original_width > original_height:
            ratio = min(target_long/original_width, target_short/original_height)
        else:
            ratio = min(target_short/original_width, target_long/original_height)
            
        new_size = (int(original_width*ratio), int(original_height*ratio))
        
        # 高质量缩放
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 锐化处理（可调节参数）
        img = img.filter(ImageFilter.UnsharpMask(
            radius=1.5,  # 降低半径防止过度锐化
            percent=200,  # 提高锐化强度
            threshold=2
        ))
        
        return img

    def process_image(self, image_path):
        # 预览图保持原样
        image = Image.open(image_path)
        image.thumbnail((400, 400))
        photo = ImageTk.PhotoImage(image)
        self.img_label.config(image=photo)
        self.img_label.image = photo
        self.show_loading()

        def convert_thread():
            try:
                # 预处理后的图片用于API调用
                processed_image = self.preprocess_image(image_path)
                
                # 转换为base64
                buffered = io.BytesIO()
                processed_image.save(buffered, format="PNG", quality=100)
                base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                # 添加API Key验证
                if not self.api_key_var.get().strip():
                    raise ValueError("请先设置API Key并保存配置")
                
                # 使用前更新客户端
                self.update_client()
                completion = client.chat.completions.create(
                    model=self.model_var.get(),
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": """\
请严格保持公式原样转换，仅输出LaTeX代码：
1. 完全保留原始公式的排版结构
2. 不要添加任何代码块标记（如```）
3. 保持原有环境（如equation/align等）
4. 输出纯LaTeX代码（不包含任何注释或说明）
5. 确保可直接粘贴到LaTeX编辑器中使用\
"""},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }],
                    temperature=0.0  # 完全禁用随机性
                )
                
                # 禁用后处理
                raw_output = completion.choices[0].message.content
                self.master.after(0, self.update_latex, raw_output.strip())

            except Exception as e:
                self.master.after(0, self.update_latex, f"错误: {str(e)}")

        threading.Thread(target=convert_thread, daemon=True).start()

    def update_latex(self, latex_code):
        self.hide_loading()
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, latex_code)

    @staticmethod
    def image_to_base64(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def create_toolbar(self):
        """创建唯一的配置工具栏"""
        toolbar = ttk.Frame(self.master, padding=5)
        toolbar.pack(fill=tk.X, pady=5)

        # API Key 输入组件
        ttk.Label(toolbar, text="API Key:").pack(side=tk.LEFT, padx=(0,5))
        self.api_key_var = tk.StringVar()
        self.api_entry = ttk.Entry(
            toolbar, 
            textvariable=self.api_key_var,
            width=40,
            show="*",
            font=('San Francisco', 9)
        )
        self.api_entry.pack(side=tk.LEFT, padx=5)

        # 模型选择组件
        ttk.Label(toolbar, text="模型:").pack(side=tk.LEFT, padx=(10,5))
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            toolbar,
            textvariable=self.model_var,
            values=[
                'qwen-vl-max',
                'qwen-vl-max-latest',
                'qwen-vl-max-2025-01-25',
                'qwen-vl-max-2024-12-30',
                'qwen-vl-max-2024-11-19',
                'qwen-vl-max-2024-10-30',
                'qwen-vl-plus',
                'qwen-vl-plus-2025-01-25',
                'qwen-vl-plus-2025-01-02'
            ],
            state="readonly",
            width=25,
            font=('San Francisco', 9)
        )
        self.model_combo.pack(side=tk.LEFT, padx=5)
        
        # 保存配置按钮
        self.save_btn = ttk.Button(
            toolbar,
            text="保存配置",
            command=self.save_config,
            style='TButton'
        )
        self.save_btn.pack(side=tk.LEFT, padx=10)

    def update_client(self):
        """更新全局客户端配置（改为延迟验证）"""
        global client
        api_key = self.api_key_var.get()
        client = OpenAI(
            api_key=api_key or "empty",  # 允许空值初始化
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def load_config(self):
        """加载配置文件"""
        self.config.read(CONFIG_FILE)
        try:
            # 设置控件值
            self.api_key_var.set(self.config.get('DEFAULT', 'api_key', fallback=''))
            model = self.config.get('DEFAULT', 'model', fallback='qwen-vl-max')
            if model in self.model_combo['values']:
                self.model_var.set(model)
                self.model_combo.current(self.model_combo['values'].index(model))
            else:
                self.model_var.set('qwen-vl-max')
                self.model_combo.current(0)
        except Exception as e:
            messagebox.showerror("配置错误", f"加载配置失败: {str(e)}")

    def save_config(self):
        """保存配置"""
        self.config['DEFAULT'] = {
            'api_key': self.api_key_var.get(),
            'model': self.model_var.get()
        }
        with open(CONFIG_FILE, 'w') as f:
            self.config.write(f)
        self.update_client()  # 保存后更新客户端
        messagebox.showinfo("提示", "配置已保存！")

    def post_process_latex(self, raw_text):
        """后处理：移除代码块标记"""
        # 移除 ```latex 和 ``` 标记
        cleaned = re.sub(r'```\s*latex\s*', '', raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r'```\s*', '', cleaned)
        # 移除首尾空白
        return cleaned.strip()

    def copy_to_clipboard(self):
        """复制代码到剪贴板"""
        code = self.result_text.get(1.0, tk.END).strip()
        if code:
            try:
                pyperclip.copy(code)
                # 改变按钮样式
                self.save_btn.config(style='Copied.TButton', text="已复制")
                self.master.after(2000, lambda: self.save_btn.config(style='TButton', text="保存配置"))
            except Exception as e:
                messagebox.showerror("错误", f"复制失败: {str(e)}")
        else:
            messagebox.showwarning("警告", "没有可复制的代码")

def main():
    # 资源路径处理 (for PyInstaller)
    if getattr(sys, 'frozen', False):
        os.chdir(sys._MEIPASS)

    root = tk.Tk()
    app = LatexConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()