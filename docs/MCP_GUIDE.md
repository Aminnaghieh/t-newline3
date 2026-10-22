# 🔌 راهنمای اتصال Liara SRE Agent به عنوان MCP Server
## Model Context Protocol (MCP) Integration Guide

با فعال‌سازی سرور **MCP (Model Context Protocol)**، هر کاربری می‌تواند **Liara SRE Agent** را مستقیماً به کلاینت‌ها و ایجنت‌های دلخواه خود (مثل **Claude Desktop**, **Cursor**, **Antigravity**, **Windsurf**, **VS Code Cline**, **Continue.dev**) متصل کند.

---

### 💡 مزیت‌های استفاده از سرور MCP:
1. **کسر اعتبار مدل از حساب کاربر (BYOK - Bring Your Own Key)**: کاربر از اشتراک و اعتبار Claude یا OpenAI یا Gemini خودش در همان نرم‌افزار استفاده می‌کند و نیازی به شارژ اعتبار جانبی ندارد.
2. **عملیات مستقیم روی لیارا**: تمامی فرآیندهای ساخت اپ، دیپلوی، مانیتورینگ و عیب‌یابی مستقیماً با توکن و اعتبار لیارای کاربر اجرا می‌شوند.
3. **مکالمه طبیعی در محیط دلخواه**: می‌توانید مستقیماً در Claude یا Cursor بگویید: *"پروژه من رو در مسیر E:/my-app بررسی کن و روی لیارا دیپلوی کن و اگر به ارور خوردیم لاگ‌هاش رو دیباگ کن"*.

---

## 🛠️ لیست ابزارهای در دسترس ایجنت‌ها (Exposed MCP Tools):

| نام ابزار (Tool Name) | پارامترها | عملکرد |
|-----------------------|-----------|--------|
| `liara_get_account_info` | — | بررسی وضعیت حساب، ایمیل و باقیمانده اعتبار در لیارا |
| `liara_list_projects` | — | دریافت لیست تمام اپلیکیشن‌های فعال روی لیارا با وضعیت و پلن |
| `liara_get_project_details` | `project_name` | دریافت مشخصات کامل پروژه (پورت، وضعیت، متغیرها) |
| `liara_get_health` | `project_name` | دریافت زنده درصد مصرف CPU، RAM و هشدارهای فعال |
| `liara_get_logs` | `project_name`, `since_minutes`, `grep` | دریافت لاگ‌های اخیر همراه با فیلتر کلیدواژه |
| `liara_analyze_local_project` | `project_path` | تحلیل سورس‌کد محلی (زبان، فریم‌ورک، پورت و پیشنهاد پلن مناسب) |
| `liara_deploy_project` | `project_name`, `source_path`, `port` | بسته‌بندی سورس محلی و دیپلوی مستقیم روی لیارا |
| `liara_restart_app` | `project_name` | راه‌اندازی مجدد پادها و کانتینر پروژه |
| `liara_scale_app` | `project_name`, `scale` (0 یا 1) | روشن یا خاموش کردن اپلیکیشن |
| `liara_resize_plan` | `project_name`, `plan_id` | تغییر منابع سخت‌افزاری به پلن‌های micro تا xxlarge |
| `liara_diagnose_issue` | `project_name` | جمع‌آوری کانتکست خطا و تحلیل ریشه‌ای (RCA) با ارائه راهکار |

---

## ⚙️ نحوه پیکربندی در کلاینت‌های مختلف

### ۱. تنظیم در Claude Desktop
فایل پیکربندی کلود را در مسیر زیر باز کنید:
- **ویندوز**: `%APPDATA%\Claude\claude_desktop_config.json`
- **مک**: `~/Library/Application Support/Claude/claude_desktop_config.json`

کد زیر را به بخش `mcpServers` اضافه نمایید:

```json
{
  "mcpServers": {
    "liara-sre": {
      "command": "E:\\liara-challenge\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "liara_agent.mcp.server"
      ],
      "env": {
        "LIARA_API_TOKEN": "YOUR_LIARA_API_TOKEN",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

---

### ۲. تنظیم در Cursor IDE
در پوشه ریشه پروژه خود در Cursor یک فایل بنام `.cursor/mcp.json` ایجاد کنید:

```json
{
  "mcpServers": {
    "liara-sre": {
      "command": "E:\\liara-challenge\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "liara_agent.mcp.server"
      ],
      "env": {
        "LIARA_API_TOKEN": "YOUR_LIARA_API_TOKEN",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

---

### ۳. تنظیم در Antigravity / Gemini CLI
فایل تنظیمات سرورهای MCP در مسیر `~/.gemini/antigravity/mcp/` یا فایل کانفیگ پروژه را به شکل زیر ویرایش کنید:

```json
{
  "liara-sre": {
    "command": "E:\\liara-challenge\\.venv\\Scripts\\python.exe",
    "args": [
      "-m",
      "liara_agent.mcp.server"
    ],
    "env": {
      "LIARA_API_TOKEN": "YOUR_LIARA_API_TOKEN",
      "PYTHONIOENCODING": "utf-8"
    }
  }
}
```

---

## 🧪 تست اجرای سرور MCP به صورت دستی

برای اطمینان از صحت کارکرد سرور، می‌توانید در ترمینال دستور زیر را اجرا کنید:

```bash
# از طریق دستور CLI
.venv\Scripts\python.exe -m liara_agent mcp

# یا مستقیماً از طریق ماژول پایتون
.venv\Scripts\python.exe -m liara_agent.mcp.server
```
*(سرور آماده دریافت دستورات استاندارد JSON-RPC از هر کلاینت هوش مصنوعی خواهد بود)*
