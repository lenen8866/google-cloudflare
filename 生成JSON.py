import json
import os
import tkinter as tk
from tkinter import messagebox
import webbrowser
#https://www.cloudflare.com/
FILE_NAME = "accounts.json"

def load_data():
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# 记录每个 entry 对应的 placeholder 文字
placeholder_map = {}

def get_entry_value(entry):
    val = entry.get()
    ph  = placeholder_map.get(entry, "")
    # 内容等于 placeholder 且颜色是灰色 → 视为空
    if val == ph and entry.cget("fg") == "grey":
        return ""
    return val

def save_data():
    global selected_original_name
    empty = [label for label, entry in required_entries if not get_entry_value(entry).strip()]
    if empty:
        messagebox.showerror("错误", f"以下字段不能为空：{', '.join(empty)}")
        return
    name = get_entry_value(entry_name).strip()
    if selected_original_name and selected_original_name in data and selected_original_name != name:
        del data[selected_original_name]
    data[name] = {
        "description": get_entry_value(entry_desc),
        "endpoint":    get_entry_value(entry_endpoint),
        "access_key":  get_entry_value(entry_access),
        "secret_key":  get_entry_value(entry_secret),
        "bucket":      get_entry_value(entry_bucket),
        "public_url":  get_entry_value(entry_url)
    }
    selected_original_name = name
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    messagebox.showinfo("成功", "保存成功！")
    refresh_list()
    new_account()

def delete_data():
    if not listbox.curselection():
        return
    selected = listbox.get(listbox.curselection())
    if selected in data:
        del data[selected]
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    refresh_list()

def new_account():
    global selected_original_name
    selected_original_name = None
    listbox.selection_clear(0, tk.END)
    for entry in all_entries:
        ph = placeholder_map.get(entry, "")
        entry.delete(0, tk.END)
        if ph:
            entry.insert(0, ph)
            entry.config(fg="grey")
        else:
            entry.config(fg="black")

def load_selected(event):
    global selected_original_name
    if not listbox.curselection():
        return
    selected = listbox.get(listbox.curselection())
    selected_original_name = selected
    acc = data[selected]
    # 顺序必须与 create_input_with_button 调用顺序完全一致：
    # name, desc, url, access, secret, bucket, endpoint
    values = [
        selected,
        acc.get("description", ""),
        acc.get("public_url", ""),
        acc.get("access_key", ""),
        acc.get("secret_key", ""),
        acc.get("bucket", ""),
        acc.get("endpoint", ""),
    ]
    for entry, value in zip(all_entries, values):
        entry.delete(0, tk.END)
        if value:
            entry.insert(0, value)
            entry.config(fg="black")
        else:
            ph = placeholder_map.get(entry, "")
            if ph:
                entry.insert(0, ph)
                entry.config(fg="grey")
            else:
                entry.config(fg="black")

def refresh_list():
    listbox.delete(0, tk.END)
    for key in data.keys():
        listbox.insert(tk.END, key)

def show_tip_window(label_text, tip_text):
    win = tk.Toplevel(root)
    win.title(f"提示 · {label_text}")
    win.resizable(False, False)
    win.transient(root)
    win.grab_set()

    win.update_idletasks()
    w, h = 460, 240
    x = root.winfo_rootx() + (root.winfo_width()  - w) // 2
    y = root.winfo_rooty() + (root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(win, text=label_text, font=("微软雅黑", 11, "bold"),
             fg="#333", pady=8).pack()

    text_box = tk.Text(win, wrap="word", height=8, width=54,
                       font=("微软雅黑", 10), relief="flat",
                       bg="#f5f5f5", fg="#222", padx=8, pady=8)
    text_box.insert("1.0", tip_text)
    text_box.config(state="disabled")
    text_box.pack(padx=12, pady=(0, 8))

    tk.Button(win, text="关闭", width=10, command=win.destroy).pack(pady=4)

def make_button_command(label_text, action):
    if action.startswith("http://") or action.startswith("https://"):
        return lambda: webbrowser.open(action)
    else:
        return lambda: show_tip_window(label_text, action)

def create_input_with_button(label_text, open_url_or_tip, required=False, placeholder=""):
    frame_row = tk.Frame(frame)
    frame_row.pack(fill="x", pady=3)
    label = label_text + " *" if required else label_text
    tk.Label(frame_row, text=label, width=12, anchor="w",
             fg="red" if required else "black").pack(side=tk.LEFT)

    entry = tk.Entry(frame_row, width=55)
    entry.pack(side=tk.LEFT)

    if placeholder:
        placeholder_map[entry] = placeholder  # 登记 placeholder
        entry.insert(0, placeholder)
        entry.config(fg="grey")

        def on_focus_in(e, en=entry, ph=placeholder):
            if en.get() == ph and en.cget("fg") == "grey":
                en.delete(0, tk.END)
                en.config(fg="black")

        def on_focus_out(e, en=entry, ph=placeholder):
            if not en.get().strip():
                en.delete(0, tk.END)
                en.insert(0, ph)
                en.config(fg="grey")

        entry.bind("<FocusIn>",  on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
    else:
        entry.config(fg="black")

    cmd = make_button_command(label_text, open_url_or_tip)
    tk.Button(frame_row, text="查看", command=cmd).pack(side=tk.LEFT, padx=5)

    if required:
        required_entries.append((label_text, entry))

    all_entries.append(entry)
    return entry

# 初始化
data = load_data()
selected_original_name = None
required_entries = []
all_entries = []       # 改为动态收集，顺序与创建顺序一致

# 主窗口
root = tk.Tk()
root.title("账号管理工具")
root.geometry("860x420")
root.resizable(False, False)

# 左侧列表
listbox = tk.Listbox(root, width=20)
listbox.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
listbox.bind("<<ListboxSelect>>", load_selected)

# ── 拖拽排序 ──────────────────────────────────────────
_drag_index = None

def on_drag_start(event):
    global _drag_index
    _drag_index = listbox.nearest(event.y)

def on_drag_motion(event):
    global _drag_index
    if _drag_index is None:
        return
    target = listbox.nearest(event.y)
    if target == _drag_index:
        return
    keys = list(data.keys())
    if 0 <= _drag_index < len(keys) and 0 <= target < len(keys):
        keys[_drag_index], keys[target] = keys[target], keys[_drag_index]
        new_data = {k: data[k] for k in keys}
        data.clear()
        data.update(new_data)
        refresh_list()
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(target)
        _drag_index = target

def on_drag_release(event):
    global _drag_index
    if _drag_index is not None:
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    _drag_index = None

listbox.bind("<ButtonPress-1>",   on_drag_start)
listbox.bind("<B1-Motion>",       on_drag_motion)
listbox.bind("<ButtonRelease-1>", on_drag_release)
# ─────────────────────────────────────────────────────

# 右侧区域
frame = tk.Frame(root)
frame.pack(side=tk.LEFT, padx=10, pady=10)

entry_name = create_input_with_button(
    "账号名称",
    "随意填写一个方便自己辨认的名称即可。\n"
    "例如：「CF 个人账号」「阿里云-工作」\n\n"
    "此名称只用于左侧列表区分账号，不影响实际连接。",
    placeholder="自定义名称，方便区分"
)

entry_desc = create_input_with_button(
    "description",
    "用一句话备注这个账号的用途，方便日后回忆。\n"
    "例如：「用 xxx@gmail.com 注册的 Cloudflare 免费账号」\n\n"
    "此字段不参与连接，纯属个人备注。",
    placeholder="备注：哪个邮箱 / 哪个项目"
)

entry_url = create_input_with_button(
    "public_url",
    "【在 Cloudflare 控制台获取公开访问链接】\n\n"
    "路径：Build → R2 Object Storage → Overview\n"
    "→ 点击对应的 Bucket 名称 → Settings\n"
    "→ 找到「Public Development URL」→ 点击开启\n"
    "→ 复制生成的链接填入此处\n\n"
    "⚠️ 末尾不要加斜杠 /",
    required=True,
    placeholder="https://pub-xxxxxxxx.r2.dev"
)

entry_access = create_input_with_button(
    "access_key",
    "【在 Cloudflare 控制台创建 API Token 后获取】\n\n"
    "路径：Build → R2 Object Storage → Overview\n"
    "→ 右侧「Account Details」→ 点击「Manage R2 API Tokens」\n"
    "→ 新建 Token，完成后复制「Access Key ID」填入此处\n\n"
    "⚠️ 此值仅在创建时显示一次，请立即复制保存！",
    required=True,
    placeholder="Access Key ID（创建 Token 时复制）"
)

entry_secret = create_input_with_button(
    "secret_key",
    "【与 Access Key ID 在同一页面获取】\n\n"
    "路径：Build → R2 Object Storage → Overview\n"
    "→ 右侧「Account Details」→ 点击「Manage R2 API Tokens」\n"
    "→ 新建 Token，完成后复制「Secret Access Key」填入此处\n\n"
    "⚠️ 此值仅在创建时显示一次，请立即复制保存！",
    required=True,
    placeholder="Secret Access Key（创建 Token 时复制）"
)

entry_bucket = create_input_with_button(
    "bucket",
    "【在 Cloudflare 控制台查看存储桶名称】\n\n"
    "路径：Build → R2 Object Storage → Overview → Buckets\n"
    "→ 找到你要使用的存储桶，复制其名称填入此处\n\n"
    "⚠️ 名称必须与控制台完全一致（区分大小写），\n"
    "    填写错误将导致上传失败！",
    required=True,
    placeholder="存储桶名称（严格区分大小写）"
)

entry_endpoint = create_input_with_button(
    "endpoint",
    "【在 Cloudflare 控制台获取 S3 兼容接口地址】\n\n"
    "路径：Build → R2 Object Storage → Overview\n"
    "→ 右侧「Account Details」→ 找到「S3 API」一栏\n"
    "→ 复制该地址填入此处\n\n"
    "格式通常为：https://<账号ID>.r2.cloudflarestorage.com\n\n"
    "⚠️ 末尾不要加斜杠 /",
    required=True,
    placeholder="https://<账号ID>.r2.cloudflarestorage.com"
)

# all_entries 顺序由 create_input_with_button 调用顺序决定
# 与 load_selected 里 values 的顺序必须一致：
# [name, desc, url, access, secret, bucket, endpoint]
# 但 load_selected 的 values 是按旧顺序写的，需同步修正：
# values = [name, desc, endpoint, access, secret, bucket, url]  ← 旧顺序
# 现在 all_entries = [name, desc, url, access, secret, bucket, endpoint]
# 所以 load_selected 里的 values 也要改成同样顺序，已在上方 load_selected 函数中对应 acc.get() 顺序

btn_frame = tk.Frame(frame)
btn_frame.pack(pady=8)
tk.Button(btn_frame, text="新建账号",     width=14, command=new_account).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="保存 / 新增",  width=14, command=save_data).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="删除选中账号", width=14, command=delete_data, bg="#ff4d4f", fg="white").pack(side=tk.LEFT, padx=5)

refresh_list()
root.mainloop()