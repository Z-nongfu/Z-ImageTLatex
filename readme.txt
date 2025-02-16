# 📸 Image to LaTeX Converter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A cross-platform desktop application that converts mathematical equations from images/screenshots to LaTeX code using AI. 🧠

![Application Screenshot](screenshot.png)

---

## ✨ Features

✅ **Screenshot Capture**: Select any area of your screen to capture equations.  
✅ **Image Upload**: Supports PNG, JPG, and JPEG formats.  
✅ **AI-Powered Conversion**: Utilizes Qwen-VL models via DashScope API.  
✅ **Clean Output**: Pure LaTeX code without markdown wrappers.  
✅ **Smart Preprocessing**:
   - 🔍 Auto-resizing with aspect ratio preservation.  
   - 🔧 Sharpening filters for better OCR accuracy.  
✅ **Cross-Platform**: Works on **Windows**, **macOS**, and **Linux**.  
✅ **Config Management**: Save API keys and model preferences.  

---

## 📋 Requirements

- 🐍 **Python 3.8+**
- 🔑 **[DashScope API Key](https://help.aliyun.com/zh/dashscope/developer-reference/activate-dashscope-and-create-an-api-key)**

---

## 🚀 Installation

### 🔧 From Source
```bash
git clone https://github.com/Z-nongfu/image-to-latex.git
cd image-to-latex
pip install -r requirements.txt
python tiqu.py
```

### 📦 Prebuilt Executable
Download the latest release from the [Releases page](https://github.com/Z-nongfu/image-to-latex/releases).

---

## 🎯 Usage

1. **Set API Key** 🔑  
   - Get your API key from [DashScope Console](https://dashscope.console.aliyun.com/apiKey).  
   - Enter it in the toolbar and click "Save Config".  

2. **Convert Images** 📸  
   - Click "Upload Image" to select an image file.  
   - Click "Capture Area" to take a screenshot.  
   - Wait for conversion (typically **5-15 seconds**).  

3. **Copy Code** 📋  
   - Click "Copy Code" to get LaTeX in clipboard.

---

## ⚙️ Configuration

Configuration file is stored in:
- 🖥️ **Windows**: `%USERPROFILE%\.config\latex_converter\config.ini`
- 🐧 **Linux/macOS**: `~/.config/latex_converter/config.ini`

For portable use (executable version), config is saved in `config/config.ini` next to the EXE file.

---

## 🤖 Supported Models

- **qwen-vl-max** (default)  
- **qwen-vl-plus**  
- Latest model versions

---

## 🔍 Troubleshooting

### 🛠 Common Issues
- **Blank Output**: Check API key validity.  
- **Blurry Conversions**: Capture higher-resolution images.  
- **Clipboard Errors**: Install [pyperclip dependencies](https://pypi.org/project/pyperclip/#dependencies).  

---

## 📜 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details. 📝

