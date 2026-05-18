import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import boto3
from botocore.config import Config
import threading, os, mimetypes, json
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    with open("accounts.json", "r", encoding="utf-8") as f:
        ACCOUNTS = json.load(f)
except Exception as e:
    messagebox.showerror("错误", f"无法读取 accounts.json\n\n{e}")
    raise

s3 = None
BUCKET = PUBLIC_URL = CURRENT_TOKEN = ""
FREE_LIMIT_GB = 10

BG, BG2, BG3     = "#1e1e2e", "#2a2a3e", "#313145"
ACCENT, ACCENT2  = "#7c6af7", "#5a4fd6"
TEXT, TEXT2      = "#e0e0f0", "#9090b0"
SUCCESS, DANGER  = "#50d890", "#f87171"
HOVER            = "#3d3d5c"


def load_account(token_name):
    global s3, BUCKET, PUBLIC_URL, CURRENT_TOKEN
    if token_name not in ACCOUNTS:
        messagebox.showerror("错误", f"没有找到 TOKEY：\n{token_name}")
        return False
    cfg = ACCOUNTS[token_name]
    try:
        new_s3 = boto3.client(
            "s3",
            endpoint_url=cfg["endpoint"],
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            config=Config(signature_version="s3v4"),
        )
        new_s3.list_objects_v2(Bucket=cfg["bucket"], MaxKeys=1)
        s3, BUCKET, PUBLIC_URL, CURRENT_TOKEN = new_s3, cfg["bucket"], cfg["public_url"], token_name
        return True
    except Exception as e:
        messagebox.showerror("连接失败", f"TOKEY：{token_name}\n\n错误：\n{e}")
        return False


def list_all_objects(prefix=""):
    objects, kwargs = [], {"Bucket": BUCKET, "Prefix": prefix}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        objects.extend(resp.get("Contents", []))
        if resp.get("IsTruncated"):
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
        else:
            break
    return objects


def list_directory(prefix=""):
    subdirs, files = [], []
    kwargs = {"Bucket": BUCKET, "Prefix": prefix, "Delimiter": "/"}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        subdirs.extend(cp["Prefix"] for cp in resp.get("CommonPrefixes", []))
        files.extend(o for o in resp.get("Contents", []) if o["Key"] != prefix)
        if resp.get("IsTruncated"):
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
        else:
            break
    return subdirs, files


def fmt_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def calc_bucket_size_gb():
    """扫描全部对象，返回总字节数和 GB 数"""
    total = sum(o["Size"] for o in list_all_objects(""))
    return total, total / (1024 ** 3)


def calc_local_size(local_dir):
    """统计本地文件夹总字节数"""
    total = 0
    for root, _, files in os.walk(local_dir):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


class R2App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("R2 多 TOKEY 文件管理器")
        self.geometry("1100x700")
        self.configure(bg=BG)
        self.current_prefix = ""
        self.build_ui()
        if ACCOUNTS:
            first = list(ACCOUNTS.keys())[0]
            self.token_var.set(first)
            self.switch_token()

    def build_ui(self):
        ttk.Style(self).theme_use("clam")

        # 顶部栏
        top = tk.Frame(self, bg=BG2, height=55)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="☁ R2 文件管理器", bg=BG2, fg=TEXT,
                 font=("Helvetica", 15, "bold")).pack(side="left", padx=20)

        self.token_var = tk.StringVar()
        self.token_combo = ttk.Combobox(top, textvariable=self.token_var,
                                        values=list(ACCOUNTS.keys()),
                                        state="readonly", width=18,
                                        font=("Helvetica", 10))
        self.token_combo.pack(side="right", padx=10, pady=12)
        self.token_combo.bind("<<ComboboxSelected>>", self.switch_token)

        for text, cmd, color in [
            ("⬆ 上传文件夹",       self.upload_folder,   ACCENT),
            ("⟳ 刷新",             self.refresh,          BG3),
            ("📋 复制当前目录链接", self.copy_dir_urls,    BG3),
            ("📊 统计用量",         self.show_bucket_size, BG3),
        ]:
            tk.Button(top, text=text, command=cmd, bg=color, fg=TEXT,
                      relief="flat", padx=12, pady=5, cursor="hand2"
                      ).pack(side="right", padx=4)

        # 信息行：连接状态 + 用量
        info_row = tk.Frame(self, bg=BG)
        info_row.pack(fill="x", padx=18, pady=(10, 2))
        self.info_var = tk.StringVar(value="未连接")
        tk.Label(info_row, textvariable=self.info_var, bg=BG, fg=SUCCESS,
                 font=("Helvetica", 11)).pack(side="left")
        self.size_var = tk.StringVar(value="")
        tk.Label(info_row, textvariable=self.size_var, bg=BG, fg=TEXT2,
                 font=("Helvetica", 10)).pack(side="left", padx=20)

        # 搜索栏
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.on_search())
        search_frame = tk.Frame(self, bg=BG2)
        search_frame.pack(fill="x", padx=16)
        tk.Entry(search_frame, textvariable=self.search_var,
                 bg=BG3, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Helvetica", 11)
                 ).pack(fill="x", pady=8, ipady=6)

        # 文件列表
        wrapper = tk.Frame(self, bg=BG)
        wrapper.pack(fill="both", expand=True, padx=16, pady=8)

        self.canvas = tk.Canvas(wrapper, bg=BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status = tk.Frame(self, bg=BG2, height=28)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)
        tk.Label(status, textvariable=self.status_var, bg=BG2, fg=TEXT2,
                 font=("Helvetica", 9)).pack(side="left", padx=10)

    def switch_token(self, event=None):
        token_name = self.token_var.get().strip()
        if token_name and load_account(token_name):
            self.info_var.set(f"当前 TOKEY：{token_name}    Bucket：{BUCKET}")
            self.current_prefix = ""
            self.refresh()

    def refresh(self):
        if s3:
            threading.Thread(target=self.load_dir, daemon=True).start()

    def load_dir(self):
        try:
            subdirs, files = list_directory(self.current_prefix)
            self.after(0, self.render_list, subdirs, files)
        except Exception as e:
            self.after(0, self.status, f"❌ {e}")

    def render_list(self, subdirs, files):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, d in enumerate(subdirs):
            self.add_row(i, "📁", d[len(self.current_prefix):], "", "目录", True, d)
        for i, f in enumerate(files, len(subdirs)):
            name = f["Key"][len(self.current_prefix):]
            self.add_row(i, "📄", name, fmt_size(f["Size"]),
                         os.path.splitext(name)[1] or "文件", False, f["Key"])
        self.status(f"📂 {len(subdirs)} 个目录  {len(files)} 个文件")

    def add_row(self, idx, icon, name, size, ftype, is_dir, full_key):
        bg = BG if idx % 2 == 0 else BG2
        row = tk.Frame(self.list_frame, bg=bg)
        row.pack(fill="x")

        def set_bg(color):
            row.config(bg=color)
            for c in row.winfo_children():
                try: c.config(bg=color)
                except: pass

        row.bind("<Enter>", lambda e: set_bg(HOVER))
        row.bind("<Leave>", lambda e: set_bg(bg))

        tk.Label(row, text=f"{icon} {name}", bg=bg, fg=TEXT, anchor="w",
                 font=("Helvetica", 11)).pack(side="left", fill="x", expand=True, padx=10, pady=8)
        tk.Label(row, text=size,  bg=bg, fg=TEXT2, width=12).pack(side="left")
        tk.Label(row, text=ftype, bg=bg, fg=TEXT2, width=10).pack(side="left")

        btns = tk.Frame(row, bg=bg)
        btns.pack(side="right", padx=10)

        if is_dir:
            tk.Button(btns, text="进入", command=lambda k=full_key: self.enter_dir(k),
                      bg=ACCENT, fg=TEXT, relief="flat", cursor="hand2").pack(side="left", padx=4)
        else:
            tk.Button(btns, text="复制链接", command=lambda k=full_key: self.copy_url(k),
                      bg=BG3, fg=TEXT, relief="flat", cursor="hand2").pack(side="left", padx=4)

    def show_bucket_size(self):
        """后台统计 bucket 全部对象大小，显示用量和剩余"""
        if not s3:
            return
        self.status("📊 正在统计 Bucket 大小，请稍候…")
        self.size_var.set("计算中…")

        def _calc():
            try:
                total_bytes, total_gb = calc_bucket_size_gb()
                remain_gb = FREE_LIMIT_GB - total_gb
                color = SUCCESS if remain_gb > 1 else DANGER
                text = (
                    f"已用：{fmt_size(total_bytes)}  /  "
                    f"{FREE_LIMIT_GB} GB 免费额度  |  "
                    f"剩余：{remain_gb:.2f} GB"
                )
                self.after(0, self.size_var.set, text)
                self.after(0, self.status, f"📊 统计完成：{fmt_size(total_bytes)} / {FREE_LIMIT_GB} GB")
            except Exception as e:
                self.after(0, self.size_var.set, "统计失败")
                self.after(0, self.status, f"❌ {e}")

        threading.Thread(target=_calc, daemon=True).start()

    def copy_dir_urls(self):
        """复制当前目录（含子目录）所有文件的直链，每行一个"""
        if not s3:
            return
        self.status("📋 正在获取文件列表…")

        def _collect():
            try:
                objects = list_all_objects(self.current_prefix)
                urls = "\n".join(f"{PUBLIC_URL}/{o['Key']}" for o in objects)
                count = len(objects)
                self.after(0, self._set_clipboard, urls)
                label = f"当前目录" if self.current_prefix else "根目录"
                self.after(0, self.status, f"✅ 已复制 {count} 个链接（{label}及子目录所有文件）")
            except Exception as e:
                self.after(0, self.status, f"❌ {e}")

        threading.Thread(target=_collect, daemon=True).start()

    def _set_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def enter_dir(self, prefix):
        self.current_prefix = prefix
        self.refresh()

    def copy_url(self, key):
        url = f"{PUBLIC_URL}/{key}"
        self.clipboard_clear()
        self.clipboard_append(url)
        self.status(f"✅ 已复制链接：{url}")

    def upload_folder(self):
        if not s3:
            messagebox.showwarning("提示", "请先连接 TOKEY")
            return
        local_dir = filedialog.askdirectory(title="选择上传文件夹")
        if not local_dir:
            return
        remote = simpledialog.askstring("上传目录", "上传到哪个目录？", initialvalue=self.current_prefix)
        if remote is None:
            return
        remote_prefix = remote.strip().rstrip("/") + "/" if remote.strip() else ""
        all_files = [
            (os.path.join(root, f), remote_prefix + os.path.relpath(os.path.join(root, f), local_dir).replace("\\", "/"))
            for root, _, files in os.walk(local_dir) for f in files
        ]
        if not all_files:
            messagebox.showinfo("提示", "文件夹为空")
            return

        # 计算本地大小并给出预估提示
        local_bytes = calc_local_size(local_dir)
        local_gb = local_bytes / (1024 ** 3)
        msg = (
            f"本地文件夹：{fmt_size(local_bytes)}（{len(all_files)} 个文件）\n\n"
            f"上传后约新增 {local_gb:.3f} GB 用量。\n"
            f"R2 免费额度 {FREE_LIMIT_GB} GB，请确认剩余空间充足。\n\n"
            f"确认上传到：{remote_prefix or '根目录'} ？"
        )
        if not messagebox.askyesno("确认上传", msg):
            return

        threading.Thread(target=self.do_upload, args=(all_files,), daemon=True).start()

    def do_upload(self, all_files):
        total, done = len(all_files), [0]

        def upload_one(local_path, remote_key):
            try:
                ct, _ = mimetypes.guess_type(local_path)
                s3.upload_file(local_path, BUCKET, remote_key, ExtraArgs={"ContentType": ct} if ct else {})
                done[0] += 1
                self.after(0, self.status, f"⬆ 上传 {done[0]}/{total}")
            except Exception as e:
                print(e)

        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in as_completed([pool.submit(upload_one, lp, rk) for lp, rk in all_files]):
                pass

        self.after(0, self.status, "✅ 上传完成")
        self.after(0, self.refresh)

    def on_search(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            self.refresh()
            return
        threading.Thread(target=self.search_thread, args=(keyword,), daemon=True).start()

    def search_thread(self, keyword):
        try:
            results = [o for o in list_all_objects(self.current_prefix) if keyword in o["Key"].lower()]
            self.after(0, self.render_search, results)
        except Exception as e:
            self.after(0, self.status, str(e))

    def render_search(self, results):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, obj in enumerate(results):
            self.add_row(i, "📄", obj["Key"], fmt_size(obj["Size"]),
                         os.path.splitext(obj["Key"])[1] or "文件", False, obj["Key"])
        self.status(f"🔍 找到 {len(results)} 个结果")

    def status(self, msg):
        self.status_var.set(msg)


if __name__ == "__main__":
    R2App().mainloop()