"""
╔══════════════════════════════════════════════════════════╗
║           ✦ StudyAI — AI Study Assistant v2.0            ║
║     Professional Desktop App · Python + tkinter          ║
╚══════════════════════════════════════════════════════════╝

DEPENDENCIES:
  Standard: tkinter, sqlite3, json, os, datetime, hashlib,
            pathlib, urllib.request, threading
  Optional: Pillow  (pip install Pillow)  → image thumbnails

RUN:  python study_assistant.py

AI:  Uses Mistral API.
     Set MISTRAL_API_KEY below, OR enter it inside the app
     under Settings → Mistral API Key.
     Falls back to helpful offline responses if no key.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import json
import os
import sys
import datetime
import hashlib
import threading
import random
import urllib.request
import urllib.error
from pathlib import Path

# ── Optional Pillow ───────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION  — paste your Mistral key here (or set it inside the app)
# ═══════════════════════════════════════════════════════════════════════════════
MISTRAL_API_KEY = "YOUR_API_KEY_HERE"   # Mistral API key
DB_PATH = Path(__file__).resolve().parent / "study_assistant.db"

# ═══════════════════════════════════════════════════════════════════════════════
#  COLOUR & FONT TOKENS
# ═══════════════════════════════════════════════════════════════════════════════
C = {
    "bg":       "#0c0c1d",  "panel":  "#13132b",
    "card":     "#1c1c3a",  "input":  "#252550",
    "sidebar":  "#08081a",
    "primary":  "#6366f1",  "pri_lt": "#818cf8",
    "secondary":"#ec4899",  "accent": "#a855f7",
    "teal":     "#2dd4bf",
    "text":     "#f8fafc",  "muted":  "#a5b4fc",
    "dim":      "#6366f1",  "border": "#2e2e5e",
    "hover":    "#1e1e42",
    "success":  "#34d399",  "warn":   "#fbbf24",
    "error":    "#f43f5e",  "white":  "#ffffff",
}

F = {
    "logo":  ("Georgia",    20, "bold"),
    "title": ("Georgia",    17, "bold"),
    "h2":    ("Georgia",    13, "bold"),
    "h3":    ("Helvetica",  12, "bold"),
    "body":  ("Helvetica",  11),
    "bold":  ("Helvetica",  11, "bold"),
    "small": ("Helvetica",   9),
    "nav":   ("Helvetica",  11, "bold"),
    "mono":  ("Courier New",11),
}

SUBJECTS = ["Mathematics","Physics","Chemistry","Biology","Computer Science",
            "History","Geography","Literature","Economics","Psychology"]
EDU_LEVELS = ["School / O-A Levels","Bachelor's Degree",
              "Master's Degree","PhD / Doctorate"]
NAV = [("🏠","Dashboard"),("📚","Study"),("🤖","Ask AI"),
       ("🧠","Brain Gym"),("📊","Progress"),("⚙️","Settings")]

# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#  MISTRAL API  (OpenAI-compatible, pure urllib — no SDK needed)
# ═══════════════════════════════════════════════════════════════════════════════
MISTRAL_MODEL = "mistral-large-latest"  # Best Mistral model

def call_mistral(messages, system="", max_tokens=1100):
    """Call Mistral API (OpenAI-compatible). Returns answer string or offline text."""
    key = MISTRAL_API_KEY.strip()
    if not key:
        return _offline(messages[-1]["content"] if messages else "")
    
    # OpenAI-compatible format: system message goes in messages array
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    
    payload = json.dumps({
        "model":       MISTRAL_MODEL,
        "max_tokens":  max_tokens,
        "messages":    msgs,
        "temperature": 0.7,
    }).encode()
    
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return f"[API Error {e.code}]\n{body[:400]}"
    except Exception as ex:
        return f"[Network error: {ex}]\n\n" + _offline(
            messages[-1]["content"] if messages else "")

def _offline(q):
    return (
        "📖  OFFLINE MODE — No API key configured.\n\n"
        "To enable real AI answers:\n"
        "  1. Go to Settings → Mistral API Key\n"
        "  2. Paste your key (get one at console.mistral.ai)\n"
        "  3. Click  Apply API Key\n\n"
        f"Your question was:\n\"{q}\"\n\n"
        "Tip: study material + Q&A both use the same API key."
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
class DB:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        # Check if we need to reset DB (schema mismatch protection)
        try:
            self.conn.execute("SELECT uid FROM progress LIMIT 1")
        except sqlite3.OperationalError:
            # Old schema or corrupted - reset
            self.conn.close()
            import os
            try:
                os.remove(str(DB_PATH))
            except:
                pass
            self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email    TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                edu      TEXT DEFAULT '',
                subjects TEXT DEFAULT '[]',
                avatar   TEXT DEFAULT '',
                created  TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions(
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                uid     INTEGER,
                subject TEXT,
                topic   TEXT,
                content TEXT,
                ts      TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS qa(
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                uid      INTEGER,
                question TEXT,
                answer   TEXT,
                ts       TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS images(
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                uid  INTEGER,
                name TEXT,
                desc TEXT,
                data BLOB,
                path TEXT,
                ts   TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS progress(
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                uid      INTEGER,
                subject  TEXT,
                score    INTEGER DEFAULT 0,
                sessions INTEGER DEFAULT 0,
                UNIQUE(uid, subject)
            );
        """)
        self.conn.commit()

    # ── users ─────────────────────────────────────────────────────────────────
    def add_user(self, u, e, p, edu, subs, av=""):
        try:
            self.conn.execute(
                "INSERT INTO users(username,email,password,edu,subjects,avatar)"
                " VALUES(?,?,?,?,?,?)",
                (u, e, hashlib.sha256(p.encode()).hexdigest(),
                 edu, json.dumps(subs), av))
            self.conn.commit()
            return True, "ok"
        except sqlite3.IntegrityError:
            return False, "Username or e-mail already in use."

    def auth(self, u, p):
        r = self.conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (u, hashlib.sha256(p.encode()).hexdigest())).fetchone()
        return dict(r) if r else None

    def update_user(self, uid, edu, subs, av):
        self.conn.execute(
            "UPDATE users SET edu=?,subjects=?,avatar=? WHERE id=?",
            (edu, json.dumps(subs), av, uid))
        self.conn.commit()

    # ── sessions ──────────────────────────────────────────────────────────────
    def add_session(self, uid, subj, topic, content):
        self.conn.execute(
            "INSERT INTO sessions(uid,subject,topic,content) VALUES(?,?,?,?)",
            (uid, subj, topic, content))
        self.conn.commit()
        self._bump(uid, subj)

    def get_sessions(self, uid, n=20):
        try:
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM sessions WHERE uid=? ORDER BY ts DESC LIMIT ?",
                (uid, n))]
        except sqlite3.OperationalError:
            return []

    def count_sessions(self, uid):
        try:
            return self.conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE uid=?", (uid,)).fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    # ── qa ────────────────────────────────────────────────────────────────────
    def add_qa(self, uid, q, a):
        self.conn.execute(
            "INSERT INTO qa(uid,question,answer) VALUES(?,?,?)", (uid, q, a))
        self.conn.commit()

    def get_qa(self, uid, n=40):
        try:
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM qa WHERE uid=? ORDER BY ts ASC LIMIT ?", (uid, n))]
        except sqlite3.OperationalError:
            return []

    # ── images ────────────────────────────────────────────────────────────────
    def add_image(self, uid, name, desc, data, path):
        self.conn.execute(
            "INSERT INTO images(uid,name,desc,data,path) VALUES(?,?,?,?,?)",
            (uid, name, desc, data, path))
        self.conn.commit()

    def get_images(self, uid):
        return [dict(r) for r in self.conn.execute(
            "SELECT id,name,desc,path,ts FROM images WHERE uid=? ORDER BY ts DESC",
            (uid,))]

    def del_image(self, iid):
        self.conn.execute("DELETE FROM images WHERE id=?", (iid,))
        self.conn.commit()

    # ── progress ──────────────────────────────────────────────────────────────
    def _bump(self, uid, subj):
        self.conn.execute("""
            INSERT INTO progress(uid,subject,score,sessions) VALUES(?,?,10,1)
            ON CONFLICT(uid,subject) DO UPDATE SET
              sessions=sessions+1, score=MIN(score+8,100)
        """, (uid, subj))
        self.conn.commit()

    def get_progress(self, uid):
        try:
            return [dict(r) for r in self.conn.execute(
                "SELECT subject,score,sessions FROM progress"
                " WHERE uid=? ORDER BY score DESC", (uid,))]
        except sqlite3.OperationalError:
            return []

    def close(self):
        self.conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def setup_styles():
    s = ttk.Style()
    try: s.theme_use("clam")
    except: pass
    base = dict(background=C["bg"], foreground=C["text"],
                fieldbackground=C["input"], bordercolor=C["border"],
                troughcolor=C["input"], selectbackground=C["primary"],
                selectforeground=C["white"], insertcolor=C["text"])
    s.configure(".", **base)
    s.configure("TFrame",      background=C["bg"])
    s.configure("TLabel",      background=C["bg"], foreground=C["text"])
    s.configure("TCombobox",   fieldbackground=C["input"], background=C["card"],
                foreground=C["text"], arrowcolor=C["text"])
    s.map("TCombobox",
          fieldbackground=[("readonly", C["input"])],
          selectbackground=[("readonly", C["input"])],
          selectforeground=[("readonly", C["text"])])
    s.configure("TScrollbar",   background=C["card"], troughcolor=C["bg"],
                arrowcolor=C["muted"])
    s.configure("TCheckbutton", background=C["card"], foreground=C["text"])
    s.map("TCheckbutton",
          background=[("active", C["card"])],
          foreground=[("active", C["text"])])
    s.configure("Treeview",     background=C["card"], fieldbackground=C["card"],
                foreground=C["text"], rowheight=28)
    s.configure("Treeview.Heading", background=C["panel"],
                foreground=C["pri_lt"], font=F["bold"])
    s.map("Treeview",
          background=[("selected", C["primary"])],
          foreground=[("selected", C["white"])])
    for name, col in [("Prog","#4361ee"),("Good","#00c896"),
                      ("Mid","#ffb300"),("Low","#ff4466")]:
        s.configure(f"{name}.Horizontal.TProgressbar",
                    background=col, troughcolor=C["input"])


def mk_btn(parent, text, cmd, bg=None, fg=None, px=16, py=7, font=None, **kw):
    bg = bg or C["primary"]
    fg = fg or C["white"]
    b  = tk.Button(parent, text=text, command=cmd,
                   bg=bg, fg=fg, relief="flat", cursor="hand2",
                   font=font or F["bold"], padx=px, pady=py, bd=0,
                   activebackground=_lt(bg), activeforeground=C["white"], **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_lt(bg)))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def _lt(h):
    h = h.lstrip("#")
    r,g,b = int(h[:2],16), int(h[2:4],16), int(h[4:],16)
    return f"#{min(255,r+28):02x}{min(255,g+28):02x}{min(255,b+28):02x}"

def card(parent, **kw):
    return tk.Frame(parent, bg=C["card"],
                    highlightbackground=C["border"], highlightthickness=1, **kw)

def scrolled_txt(parent, h=10, editable=False, **kw):
    f = tk.Frame(parent, bg=C["bg"])
    t = tk.Text(f, height=h, bg=C["input"], fg=C["text"],
                insertbackground=C["text"], relief="flat",
                font=F["body"], wrap="word", padx=10, pady=8,
                state="normal" if editable else "disabled", **kw)
    sb = ttk.Scrollbar(f, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(side="left",   fill="both", expand=True)
    return f, t

def txt_set(w, s):
    w.config(state="normal")
    w.delete("1.0","end")
    w.insert("1.0", s)
    w.config(state="disabled")

def txt_add(w, s, tag=None):
    w.config(state="normal")
    if tag: w.insert("end", s, tag)
    else:   w.insert("end", s)
    w.config(state="disabled")
    w.see("end")

def make_scroll_canvas(parent):
    """Return (canvas, inner_frame) with auto-scroll config."""
    cnv = tk.Canvas(parent, bg=C["bg"], highlightthickness=0)
    sb  = ttk.Scrollbar(parent, orient="vertical", command=cnv.yview)
    cnv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    cnv.pack(fill="both", expand=True)
    inner = tk.Frame(cnv, bg=C["bg"])
    wid   = cnv.create_window((0,0), window=inner, anchor="nw")

    def _on_inner_configure(e=None):
        cnv.configure(scrollregion=cnv.bbox("all"))

    def _on_canvas_configure(e):
        cnv.itemconfig(wid, width=e.width)

    inner.bind("<Configure>", _on_inner_configure)
    cnv.bind("<Configure>", _on_canvas_configure)
    inner._update_scroll = _on_inner_configure  # expose for manual calls
    return cnv, inner

# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════════════════════════════
class LoginWin(tk.Toplevel):
    def __init__(self, master, db, on_ok):
        super().__init__(master)
        self.db, self.on_ok = db, on_ok
        self.title("StudyAI — Sign In")
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self._build()
        self.update_idletasks()
        W,H = self.winfo_width(), self.winfo_height()
        SW,SH = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(SW-W)//2}+{(SH-H)//2}")
        self.lift(); self.grab_set()

    def _build(self):
        f = tk.Frame(self, bg=C["bg"], padx=54, pady=46)
        f.pack()
        tk.Label(f, text="✦ StudyAI", bg=C["bg"], fg=C["pri_lt"],
                 font=F["logo"]).pack(pady=(0,4))
        tk.Label(f, text="Your Intelligent Learning Companion",
                 bg=C["bg"], fg=C["muted"], font=F["small"]).pack(pady=(0,30))
        self._u = self._field(f, "Username")
        self._p = self._field(f, "Password", show="•")
        tk.Frame(f, height=14, bg=C["bg"]).pack()
        mk_btn(f,"  Sign In  ", self._login,  bg=C["primary"]).pack(fill="x",pady=(0,8))
        mk_btn(f,"  Create Account  ", self._signup,
               bg=C["card"], fg=C["pri_lt"]).pack(fill="x")
        tk.Label(f, text="© 2025 StudyAI", bg=C["bg"], fg=C["dim"],
                 font=F["small"]).pack(pady=(22,0))

    def _field(self, p, label, show=""):
        tk.Label(p, text=label, bg=C["bg"], fg=C["muted"],
                 font=F["small"], anchor="w").pack(fill="x", pady=(0,3))
        e = tk.Entry(p, show=show, bg=C["input"], fg=C["text"],
                     insertbackground=C["text"], relief="flat",
                     font=F["body"], bd=0, width=30)
        e.pack(fill="x", ipady=8, pady=(0,3))
        tk.Frame(p, height=1, bg=C["border"]).pack(fill="x", pady=(0,14))
        return e

    def _login(self):
        u, p = self._u.get().strip(), self._p.get()
        if not u or not p:
            messagebox.showwarning("Missing","Enter username and password.",parent=self)
            return
        user = self.db.auth(u, p)
        if user:
            self.destroy(); self.on_ok(user)
        else:
            messagebox.showerror("Error","Invalid credentials.",parent=self)
            self._p.delete(0,"end")

    def _signup(self):
        self.withdraw()
        SignupWin(self.master, self.db, on_ok=self.on_ok, on_back=self.deiconify)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIGNUP
# ═══════════════════════════════════════════════════════════════════════════════
class SignupWin(tk.Toplevel):
    def __init__(self, master, db, on_ok, on_back=None):
        super().__init__(master)
        self.db, self.on_ok, self.on_back = db, on_ok, on_back
        self.title("StudyAI — Create Account")
        self.configure(bg=C["bg"])
        self.resizable(False, True)
        self._sv = {}
        self._av = tk.StringVar()
        self._build()
        self.update_idletasks()
        W = max(self.winfo_width(), 500)
        H = min(self.winfo_height(), 700)
        SW,SH = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(SW-W)//2}+{(SH-H)//2}")
        self.lift(); self.grab_set()

    def _build(self):
        cnv, inner = make_scroll_canvas(self)
        f = tk.Frame(inner, bg=C["bg"], padx=44, pady=32)
        f.pack(fill="x")
        tk.Label(f, text="✦ Create Account", bg=C["bg"], fg=C["pri_lt"],
                 font=F["title"]).pack(pady=(0,22))
        self._u  = self._fld(f,"Username *")
        self._e  = self._fld(f,"Email *")
        self._p  = self._fld(f,"Password *",      show="•")
        self._p2 = self._fld(f,"Confirm Password *",show="•")

        tk.Label(f,text="Education Level *",bg=C["bg"],fg=C["muted"],
                 font=F["small"],anchor="w").pack(fill="x",pady=(0,4))
        self._edu = ttk.Combobox(f, values=EDU_LEVELS, state="readonly",font=F["body"])
        self._edu.set(EDU_LEVELS[0])
        self._edu.pack(fill="x",pady=(0,18))

        tk.Label(f,text="Subjects",bg=C["bg"],fg=C["muted"],
                 font=F["small"],anchor="w").pack(fill="x",pady=(0,6))
        sf = card(f); sf.pack(fill="x",pady=(0,18))
        for i,s in enumerate(SUBJECTS):
            v = tk.BooleanVar(value=(i<3))
            self._sv[s] = v
            ttk.Checkbutton(sf,text=s,variable=v).grid(
                row=i//2,column=i%2,sticky="w",padx=14,pady=4)

        tk.Label(f,text="Profile Picture (optional)",bg=C["bg"],fg=C["muted"],
                 font=F["small"],anchor="w").pack(fill="x",pady=(0,4))
        ar = tk.Frame(f,bg=C["bg"]); ar.pack(fill="x",pady=(0,22))
        tk.Entry(ar,textvariable=self._av,bg=C["input"],fg=C["text"],
                 insertbackground=C["text"],relief="flat",
                 font=F["small"]).pack(side="left",fill="x",expand=True,ipady=6)
        mk_btn(ar,"Browse",self._brow,bg=C["card"],fg=C["muted"],
               px=10,py=4).pack(side="right",padx=(8,0))

        mk_btn(f,"  Create Account  ",self._submit,bg=C["primary"]).pack(
            fill="x",pady=(0,8))
        mk_btn(f,"  Back to Login  ",self._back,
               bg=C["card"],fg=C["muted"]).pack(fill="x")

    def _fld(self, p, label, show=""):
        tk.Label(p,text=label,bg=C["bg"],fg=C["muted"],font=F["small"],
                 anchor="w").pack(fill="x",pady=(0,3))
        e = tk.Entry(p,show=show,bg=C["input"],fg=C["text"],
                     insertbackground=C["text"],relief="flat",font=F["body"],bd=0)
        e.pack(fill="x",ipady=8,pady=(0,3))
        tk.Frame(p,height=1,bg=C["border"]).pack(fill="x",pady=(0,14))
        return e

    def _brow(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images","*.png *.jpg *.jpeg *.gif *.bmp"),("All","*.*")])
        if p: self._av.set(p)

    def _submit(self):
        u  = self._u.get().strip()
        em = self._e.get().strip()
        pw = self._p.get()
        c2 = self._p2.get()
        if not all([u, em, pw]):
            messagebox.showwarning("Missing","Fill required (*) fields.",parent=self); return
        if pw != c2:
            messagebox.showerror("Mismatch","Passwords don't match.",parent=self); return
        if len(pw) < 6:
            messagebox.showwarning("Weak","Password needs ≥ 6 chars.",parent=self); return
        subs = [s for s,v in self._sv.items() if v.get()]
        ok,msg = self.db.add_user(u, em, pw, self._edu.get(), subs, self._av.get())
        if ok:
            messagebox.showinfo("Welcome!",f"Account created! Welcome, {u}!",parent=self)
            user = self.db.auth(u, pw)
            self.destroy(); self.on_ok(user)
        else:
            messagebox.showerror("Error", msg, parent=self)

    def _back(self):
        self.destroy()
        if self.on_back: self.on_back()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN SHELL
# ═══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    SW = 214   # sidebar width

    def __init__(self):
        super().__init__()
        self.title("AI Study Assistant")
        self.configure(bg=C["bg"])
        self.minsize(980, 640)
        try:    self.state("zoomed")
        except: self.geometry("1280x800")

        self.db   = DB()
        self.user : dict = {}
        self._active = ""
        self._pages  : dict = {}

        setup_styles()
        self._build_shell()
        self.withdraw()
        self._show_login()

    # ── shell ─────────────────────────────────────────────────────────────────
    def _build_shell(self):
        self._sidebar = tk.Frame(self, bg=C["sidebar"], width=self.SW)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._content = tk.Frame(self, bg=C["bg"])
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()

    def _build_sidebar(self):
        s = self._sidebar
        tk.Label(s, text="✦ StudyAI", bg=C["sidebar"],
                 fg=C["pri_lt"], font=F["logo"]).pack(pady=(26,0))
        tk.Label(s, text="AI Study Companion", bg=C["sidebar"],
                 fg=C["dim"], font=F["small"]).pack(pady=(2,14))
        tk.Frame(s, height=1, bg=C["border"]).pack(fill="x", padx=18)

        self._av_lbl   = tk.Label(s, text="👤", bg=C["sidebar"],
                                   font=("Helvetica",24))
        self._av_lbl.pack(pady=(16,2))
        self._name_lbl = tk.Label(s, text="—", bg=C["sidebar"],
                                   fg=C["text"], font=F["bold"])
        self._name_lbl.pack()
        self._lvl_lbl  = tk.Label(s, text="—", bg=C["sidebar"],
                                   fg=C["muted"], font=F["small"])
        self._lvl_lbl.pack(pady=(0,12))
        tk.Frame(s, height=1, bg=C["border"]).pack(fill="x", padx=18, pady=(0,6))

        self._nav_btns = {}
        for icon, label in NAV:
            b = tk.Button(s, text=f"  {icon}  {label}", anchor="w",
                          bg=C["sidebar"], fg=C["muted"],
                          activebackground=C["hover"], activeforeground=C["text"],
                          relief="flat", font=F["nav"],
                          cursor="hand2", padx=18, pady=11, bd=0,
                          command=lambda l=label: self.go(l))
            b.pack(fill="x")
            b.bind("<Enter>",
                lambda e,b=b,l=label: b.config(bg=C["hover"],fg=C["text"])
                if self._active != l else None)
            b.bind("<Leave>",
                lambda e,b=b,l=label: b.config(
                    bg=C["primary"] if self._active==l else C["sidebar"],
                    fg=C["white"]   if self._active==l else C["muted"]))
            self._nav_btns[label] = b

        tk.Frame(s, bg=C["sidebar"]).pack(fill="both", expand=True)
        tk.Frame(s, height=1, bg=C["border"]).pack(fill="x", padx=18)
        mk_btn(s, "⏻  Log Out", self._logout,
               bg=C["sidebar"], fg=C["error"], px=18, py=12).pack(fill="x", pady=10)

    # ── navigation ────────────────────────────────────────────────────────────
    def go(self, label: str):
        self._active = label
        # update nav highlights
        for l, b in self._nav_btns.items():
            b.config(bg=C["primary"] if l==label else C["sidebar"],
                     fg=C["white"]   if l==label else C["muted"])
        # hide all existing pages
        for pg in self._pages.values():
            pg.place_forget()
        # create page if needed
        if label not in self._pages:
            cls = {"Dashboard": DashPage, "Study":    StudyPage,
                   "Ask AI":    AIPage,    "Brain Gym": BrainGymPage,
                   "Progress":  ProgressPage, "Settings": SettingsPage}[label]
            pg = cls(self._content, self)
            self._pages[label] = pg
        pg = self._pages[label]
        pg.place(relx=0, rely=0, relwidth=1, relheight=1)
        if hasattr(pg, "on_show"):
            pg.on_show()

    # ── auth ──────────────────────────────────────────────────────────────────
    def _show_login(self):
        LoginWin(self, self.db, self._on_login)

    def _on_login(self, user):
        self.user = user
        self._pages.clear()
        for w in self._content.winfo_children():
            w.place_forget()
        self._name_lbl.config(text=user["username"])
        lvl = user.get("edu","")
        self._lvl_lbl.config(
            text=(lvl.split("/")[0].split("'")[0].strip() or "Student"))
        self.deiconify()
        self.go("Dashboard")

    def _logout(self):
        if messagebox.askyesno("Log Out","Log out of StudyAI?"):
            self.user = {}
            self._pages.clear()
            for w in self._content.winfo_children():
                w.place_forget()
            self.withdraw()
            self._show_login()

    def subjects(self):
        return json.loads(self.user.get("subjects","[]"))

    def on_close(self):
        self.db.close()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  BASE PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class BasePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.db  = app.db

    def hdr(self, title, sub=""):
        h = tk.Frame(self, bg=C["bg"], pady=18, padx=30)
        h.pack(fill="x")
        tk.Label(h, text=title, bg=C["bg"], fg=C["text"],
                 font=F["title"]).pack(side="left")
        if sub:
            tk.Label(h, text=sub, bg=C["bg"], fg=C["muted"],
                     font=F["body"]).pack(side="left", padx=(12,0), pady=(3,0))
        tk.Frame(self, height=1, bg=C["border"]).pack(fill="x", padx=30)


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
class DashPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.hdr("🏠 Dashboard", "Overview")
        self._cnv, self._body = make_scroll_canvas(self)

    def on_show(self):
        for w in self._body.winfo_children():
            w.destroy()
        p = tk.Frame(self._body, bg=C["bg"], padx=30, pady=18)
        p.pack(fill="both", expand=True)

        u   = self.app.user
        sub = self.app.subjects() if self.app.user else []
        tot = self.db.count_sessions(u["id"]) if u else 0
        prg = self.db.get_progress(u["id"]) if u else []
        avg = int(sum(x["score"] for x in prg)/len(prg)) if prg else 0

        # Welcome banner
        wb = card(p); wb.pack(fill="x", pady=(0,18))
        tk.Label(wb,text=f"👋  Welcome back, {u['username']}!",
                 bg=C["card"],fg=C["text"],font=F["h2"],
                 anchor="w").pack(fill="x",padx=18,pady=(14,4))
        tk.Label(wb,text=f"{u.get('edu','')}  ·  {len(sub)} subjects enrolled",
                 bg=C["card"],fg=C["muted"],font=F["body"],
                 anchor="w").pack(fill="x",padx=18,pady=(0,14))

        # Stat cards
        row = tk.Frame(p,bg=C["bg"]); row.pack(fill="x",pady=(0,18))
        for icon,val,lbl_,col in [
            ("📚",str(tot),    "Study Sessions", C["primary"]),
            ("🏷️",str(len(sub)),"Subjects",       C["accent"]),
            ("⭐",f"{avg}%",   "Avg Score",      C["teal"]),
            ("📅",datetime.date.today().strftime("%b %d"),"Today",C["secondary"]),
        ]:
            c = card(row); c.pack(side="left",fill="both",expand=True,padx=(0,10))
            tk.Label(c,text=icon,bg=C["card"],font=("Helvetica",20)).pack(pady=(12,2))
            tk.Label(c,text=val, bg=C["card"],fg=col,  font=F["h2"]).pack()
            tk.Label(c,text=lbl_,bg=C["card"],fg=C["muted"],font=F["small"]).pack(pady=(2,12))

        # Progress
        if prg:
            tk.Label(p,text="Subject Progress",bg=C["bg"],fg=C["text"],
                     font=F["h3"],anchor="w").pack(fill="x",pady=(0,8))
            for px_ in prg[:5]:
                r = tk.Frame(p,bg=C["bg"]); r.pack(fill="x",pady=3)
                tk.Label(r,text=px_["subject"],bg=C["bg"],fg=C["text"],
                         font=F["body"],width=20,anchor="w").pack(side="left")
                sc = px_["score"]
                st = "Good" if sc>=70 else "Mid" if sc>=40 else "Low"
                ttk.Progressbar(r,style=f"{st}.Horizontal.TProgressbar",
                                orient="horizontal",length=250,
                                mode="determinate",maximum=100,value=sc).pack(
                                    side="left",padx=(8,8))
                tk.Label(r,text=f"{sc}%",bg=C["bg"],fg=C["muted"],
                         font=F["small"]).pack(side="left")

        # Recent sessions
        recent = self.db.get_sessions(u["id"],5)
        tk.Label(p,text="Recent Sessions",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(18,8))
        if recent:
            for s in recent:
                r = card(p); r.pack(fill="x",pady=3)
                tk.Label(r,text=f"📚  {s['subject']}  —  {s['topic']}",
                         bg=C["card"],fg=C["text"],font=F["body"],
                         anchor="w").pack(side="left",padx=14,pady=8)
                tk.Label(r,text=s["ts"][:16],bg=C["card"],fg=C["dim"],
                         font=F["small"]).pack(side="right",padx=14)
        else:
            r = card(p); r.pack(fill="x")
            tk.Label(r,text="No sessions yet — go to Study to get started!",
                     bg=C["card"],fg=C["muted"],font=F["body"]).pack(padx=16,pady=16)

        # Quick actions
        tk.Label(p,text="Quick Actions",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(18,8))
        ar = tk.Frame(p,bg=C["bg"]); ar.pack(fill="x")
        for txt,nav,col in [("📖 Study","Study",C["primary"]),
                             ("💬 Ask AI","Ask AI",C["accent"]),
                             ("🧠 Brain Gym","Brain Gym",C["secondary"]),
                             ("📊 Progress","Progress",C["teal"])]:
            mk_btn(ar,txt,lambda n=nav:self.app.go(n),
                   bg=col,px=14,py=9).pack(side="left",padx=(0,10))

        # Force scrollregion update
        self._body.update_idletasks()
        self._cnv.configure(scrollregion=self._cnv.bbox("all"))


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDY PAGE  (Mistral-powered note generator)
# ═══════════════════════════════════════════════════════════════════════════════
class StudyPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.hdr("📚 Study Material","AI-Generated Notes")
        self._last  = ""
        self._build()

    def _build(self):
        body = tk.Frame(self,bg=C["bg"],padx=30,pady=14)
        body.pack(fill="both",expand=True)

        # Controls
        ctrl = card(body); ctrl.pack(fill="x",pady=(0,12))
        ci = tk.Frame(ctrl,bg=C["card"],padx=14,pady=14); ci.pack(fill="x")

        tk.Label(ci,text="Subject:",bg=C["card"],fg=C["muted"],
                 font=F["small"]).grid(row=0,column=0,sticky="w",padx=(0,6))
        self._subj = ttk.Combobox(ci,values=SUBJECTS,state="readonly",
                                   width=18,font=F["body"])
        self._subj.set(SUBJECTS[0])
        self._subj.grid(row=0,column=1,padx=(0,18))

        tk.Label(ci,text="Topic:",bg=C["card"],fg=C["muted"],
                 font=F["small"]).grid(row=0,column=2,sticky="w",padx=(0,6))
        self._topic = tk.Entry(ci,bg=C["input"],fg=C["text"],
                                insertbackground=C["text"],relief="flat",
                                font=F["body"],width=26)
        self._topic.grid(row=0,column=3,ipady=6,padx=(0,18))
        self._topic.bind("<Return>",lambda e:self._gen())

        self._gbtn = mk_btn(ci,"⚡ Generate",self._gen,bg=C["primary"],px=14,py=6)
        self._gbtn.grid(row=0,column=4,padx=(0,8))
        mk_btn(ci,"💾 Save",self._save,bg=C["teal"],px=14,py=6).grid(row=0,column=5)

        self._status = tk.Label(body,text="Enter a topic and click Generate.",
                                 bg=C["bg"],fg=C["muted"],font=F["small"],anchor="w")
        self._status.pack(fill="x",pady=(0,6))

        tf, self._txt = scrolled_txt(body, h=26)
        tf.pack(fill="both",expand=True)
        txt_set(self._txt,
            "Select a subject and enter a topic, then click ⚡ Generate.\n\n"
            "Examples:\n"
            "  Mathematics    →  Integration by Parts, Eigenvalues, Bayes' Theorem\n"
            "  Physics        →  Quantum Tunnelling, Maxwell's Equations\n"
            "  Computer Sci   →  Binary Trees, Merge Sort, Transformer Architecture\n"
            "  Chemistry      →  SN2 Reactions, Le Chatelier's Principle\n"
            "  Biology        →  DNA Replication, Krebs Cycle, CRISPR\n\n"
            "AI will tailor the depth to your education level."
        )

    def _gen(self):
        subj  = self._subj.get()
        topic = self._topic.get().strip()
        if not topic:
            messagebox.showwarning("Missing","Enter a topic first.",parent=self); return
        level = self.app.user.get("edu","Bachelor's Degree") if self.app.user else "Bachelor's Degree"
        self._gbtn.config(state="disabled",text="⏳ Generating…")
        self._status.config(text="Contacting AI…",fg=C["warn"])
        self.update()

        def _run():
            system = (
                f"You are an expert {subj} tutor. "
                f"The student is at {level} level. "
                "Write comprehensive, well-structured study notes. Include:\n"
                "OVERVIEW — brief introduction\n"
                "KEY CONCEPTS — definitions, formulae, theorems\n"
                "EXPLANATION — step-by-step breakdown\n"
                "WORKED EXAMPLES — at least 2\n"
                "COMMON MISTAKES — pitfalls to avoid\n"
                "PRACTICE QUESTIONS — 3-5 questions graded easy to hard\n"
                "Use plain text. Section headers in ALL CAPS. Target 500-700 words."
            )
            result = call_mistral(
                [{"role":"user","content":f"Study notes for: {topic} ({subj})"}],
                system=system, max_tokens=1400)
            self.after(0, lambda: self._done(result, subj, topic))

        threading.Thread(target=_run, daemon=True).start()

    def _done(self, content, subj, topic):
        self._last = content
        txt_set(self._txt, content)
        self._gbtn.config(state="normal",text="⚡ Generate")
        self._status.config(text=f"✓ Notes ready for '{topic}' ({subj})",fg=C["success"])

    def _save(self):
        if not self._last:
            messagebox.showinfo("Nothing to save","Generate notes first.",parent=self); return
        if not self.app.user:
            messagebox.showwarning("Error","Not logged in!",parent=self); return
        subj  = self._subj.get()
        topic = self._topic.get().strip() or "Untitled"
        self.db.add_session(self.app.user["id"], subj, topic, self._last)
        self._status.config(text="✓ Saved to history",fg=C["success"])
        messagebox.showinfo("Saved",f"Notes for '{topic}' saved!",parent=self)


# ═══════════════════════════════════════════════════════════════════════════════
#  ASK AI  (real multi-turn Mistral chat)
# ═══════════════════════════════════════════════════════════════════════════════
class AIPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.hdr("🤖 Ask AI","Powered by Mistral")
        self._hist: list[dict] = []   # multi-turn messages
        self._build()

    def _build(self):
        body = tk.Frame(self,bg=C["bg"],padx=30,pady=12)
        body.pack(fill="both",expand=True)

        cf, self._chat = scrolled_txt(body, h=22)
        cf.pack(fill="both",expand=True)
        self._chat.tag_configure("you", foreground=C["pri_lt"], font=F["bold"])
        self._chat.tag_configure("ai",  foreground=C["teal"],   font=F["bold"])
        self._chat.tag_configure("msg", foreground=C["text"],   font=F["body"])
        self._chat.tag_configure("ts",  foreground=C["dim"],    font=F["small"])
        self._chat.tag_configure("sep", foreground=C["border"])

        txt_set(self._chat,
            "👋  Hello! I'm your AI study assistant, powered by Mistral.\n"
            "Ask me anything — maths problems, essay help, concept explanations.\n"
            "I remember our conversation so you can ask follow-up questions.\n\n"
            "Tip: Set your API key in Settings to enable real AI responses.\n")
        self._chat.tag_add("msg","1.0","end")

        # Input bar
        ib = card(body); ib.pack(fill="x",pady=(10,0))
        ii = tk.Frame(ib,bg=C["card"],padx=12,pady=10); ii.pack(fill="x")

        self._q = tk.Text(ii,bg=C["input"],fg=C["text"],
                           insertbackground=C["text"],relief="flat",
                           font=F["body"],height=3,wrap="word",padx=8,pady=6)
        self._q.pack(side="left",fill="x",expand=True,padx=(0,10))
        self._q.insert("1.0","Type your question and press Enter…")
        self._q.config(fg=C["dim"])
        self._q.bind("<FocusIn>",  self._ph_in)
        self._q.bind("<FocusOut>", self._ph_out)
        self._q.bind("<Return>",   self._enter)
        self._q.bind("<Shift-Return>", lambda e: None)

        # Image upload button
        ibtns = tk.Frame(ii, bg=C["card"])
        ibtns.pack(side="right", padx=(10, 0))

        self._img_path = tk.StringVar()
        mk_btn(ibtns, "📎 Attach", self._attach_img,
               bg=C["card"], fg=C["muted"], px=10, py=5).pack(pady=(0, 4))
        self._sbtn = mk_btn(ibtns, "➤ Send", self._send,
               bg=C["primary"], px=14, py=7)
        self._sbtn.pack(pady=(0, 4))
        mk_btn(ibtns, "🗑 Clear", self._clear,
               bg=C["input"], fg=C["muted"], px=10, py=5).pack()

    def _ph_in(self, e):
        if self._q.get("1.0","end-1c") == "Type your question and press Enter…":
            self._q.delete("1.0","end"); self._q.config(fg=C["text"])

    def _ph_out(self, e):
        if not self._q.get("1.0","end-1c").strip():
            self._q.insert("1.0","Type your question and press Enter…")
            self._q.config(fg=C["dim"])

    def _enter(self, e):
        if not (e.state & 0x1):   # Enter without Shift
            self._send(); return "break"

    def on_show(self):
        saved = self.db.get_qa(self.app.user["id"], 30)
        self._hist = []
        for qa in saved:
            self._hist.append({"role":"user",      "content":qa["question"]})
            self._hist.append({"role":"assistant",  "content":qa["answer"]})
        self._chat.config(state="normal")
        self._chat.delete("1.0","end")
        if saved:
            for qa in saved:
                self._append(qa["question"], qa["answer"], qa["ts"][:16])
        else:
            txt_add(self._chat,
                "👋  Hello! I'm your AI study assistant, powered by Mistral.\n"
                "Ask me anything — maths, essays, code, concepts…\n\n","msg")

    def _append(self, q, a, ts=""):
        self._chat.config(state="normal")
        ts_s = f"  ({ts})" if ts else ""
        self._chat.insert("end",f"\n🧑 You{ts_s}\n","you")
        self._chat.insert("end",q+"\n\n","msg")
        self._chat.insert("end","🤖 StudyAI\n","ai")
        self._chat.insert("end",a+"\n","msg")
        self._chat.insert("end","─"*58+"\n","sep")
        self._chat.config(state="disabled")
        self._chat.see("end")

    def _send(self):
        q = self._q.get("1.0","end-1c").strip()
        if not q or q.startswith("Type your question"):
            return
        img_path = self._img_path.get()
        if img_path:
            q += f"\n\n[User has attached an image: {os.path.basename(img_path)}]"
            self._img_path.set("")
        self._q.delete("1.0","end"); self._q.config(fg=C["text"])
        # show user msg + thinking
        self._chat.config(state="normal")
        self._chat.insert("end","\n🧑 You\n","you")
        self._chat.insert("end",q+"\n\n","msg")
        self._chat.insert("end","🤖 StudyAI  ⏳ thinking…\n","ai")
        self._chat.config(state="disabled")
        self._chat.see("end")
        self._sbtn.config(state="disabled",text="⏳")
        self.update()

        level   = self.app.user.get("edu","Bachelor's Degree") if self.app.user else "Bachelor's Degree"
        sub_str = ", ".join(self.app.subjects()) if self.app.user else "general studies"
        system  = (
            f"You are an expert AI tutor. Student level: {level}. "
            f"Enrolled subjects: {sub_str}. "
            "Answer clearly and accurately at the right academic level. "
            "Show working for maths/science. Use plain text with bullet points "
            "or numbered lists for structure."
        )
        msgs = list(self._hist[-18:])
        msgs.append({"role":"user","content":q})

        def _run():
            answer = call_mistral(msgs, system=system, max_tokens=1300)
            self.after(0, lambda: self._got(q, answer))

        threading.Thread(target=_run, daemon=True).start()

    def _got(self, question, answer):
        self._chat.config(state="normal")
        idx = self._chat.search("⏳ thinking…","1.0","end")
        if idx:
            ls = self._chat.index(f"{idx} linestart")
            le = self._chat.index(f"{idx} lineend+1c")
            self._chat.delete(ls, le)
            self._chat.insert(ls,"🤖 StudyAI\n","ai")
            self._chat.insert(f"{ls}+1l", answer+"\n","msg")
            self._chat.insert("end","─"*58+"\n","sep")
        self._chat.config(state="disabled")
        self._chat.see("end")
        self._sbtn.config(state="normal",text="➤ Send")
        if self.app.user:
            self.db.add_qa(self.app.user["id"], question, answer)
        self._hist.append({"role":"user",     "content":question})
        self._hist.append({"role":"assistant","content":answer})

    def _attach_img(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                       ("All", "*.*")])
        if p:
            self._img_path.set(p)
            name = os.path.basename(p)
            self._chat.config(state="normal")
            self._chat.insert("end", f"\n📎 Image attached: {name}\n", "ts")
            self._chat.config(state="disabled")
            self._chat.see("end")

    def _clear(self):
        if messagebox.askyesno("Clear","Clear chat display?",parent=self):
            txt_set(self._chat,"Chat cleared.\n")
            self._chat.tag_add("msg","1.0","end")
            self._img_path.set("")


# ═══════════════════════════════════════════════════════════════════════════════
#  GALLERY
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#  QUIZ PAGE  (Mistral-powered quiz generator)
# ═══════════════════════════════════════════════════════════════════════════════
class BrainGymPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.hdr("🧠 Brain Gym", "Unique AI Study Modes")
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=C["bg"], padx=30, pady=14)
        body.pack(fill="both", expand=True)
        self._cards = tk.Frame(body, bg=C["bg"])
        self._cards.pack(fill="both", expand=True)
        self._cards.grid_columnconfigure(0, weight=1)
        self._cards.grid_columnconfigure(1, weight=1)
        self._cards.grid_rowconfigure(0, weight=1)
        self._cards.grid_rowconfigure(1, weight=1)

        c1 = card(self._cards)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0,12), pady=(0,12))
        tk.Label(c1, text="🎯", bg=C["card"], font=("Helvetica",28)).pack(pady=(16,4))
        tk.Label(c1, text="Socratic Tutor", bg=C["card"], fg=C["pri_lt"], font=F["h2"]).pack()
        tk.Label(c1, text="AI does NOT give answers. It asks YOU questions to make YOU think deeper.", bg=C["card"], fg=C["muted"], font=F["body"], justify="center").pack(pady=(4,12))
        mk_btn(c1, "Start Socratic Session", self._start_socratic, bg=C["accent"], px=18, py=8).pack(pady=(0,16))

        c2 = card(self._cards)
        c2.grid(row=0, column=1, sticky="nsew", padx=(12,0), pady=(0,12))
        tk.Label(c2, text="⚔️", bg=C["card"], font=("Helvetica",28)).pack(pady=(16,4))
        tk.Label(c2, text="AI Battle Mode", bg=C["card"], fg=C["secondary"], font=F["h2"]).pack()
        tk.Label(c2, text="You vs AI in a real-time quiz duel! Who answers faster and better?", bg=C["card"], fg=C["muted"], font=F["body"], justify="center").pack(pady=(4,12))
        mk_btn(c2, "Challenge AI", self._start_battle, bg=C["secondary"], px=18, py=8).pack(pady=(0,16))

        c3 = card(self._cards)
        c3.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12,0))
        tk.Label(c3, text="🕸️", bg=C["card"], font=("Helvetica",28)).pack(pady=(16,4))
        tk.Label(c3, text="Concept Connector", bg=C["card"], fg=C["teal"], font=F["h2"]).pack()
        tk.Label(c3, text="AI builds a visual web showing how all your study topics connect to each other.", bg=C["card"], fg=C["muted"], font=F["body"], justify="center").pack(pady=(4,12))
        mk_btn(c3, "Generate My Concept Web", self._start_concept_web, bg=C["teal"], px=18, py=8).pack(pady=(0,16))

    def _start_socratic(self):
        self._socratic_win = tk.Toplevel(self)
        self._socratic_win.title("Socratic Tutor")
        self._socratic_win.configure(bg=C["bg"])
        self._socratic_win.geometry("700x600")
        self._socratic_win.resizable(True, True)
        self._socratic_win.transient(self)
        self._socratic_win.grab_set()
        self._socratic_win.update_idletasks()
        SW, SH = self._socratic_win.winfo_screenwidth(), self._socratic_win.winfo_screenheight()
        self._socratic_win.geometry(f"700x600+{(SW-700)//2}+{(SH-600)//2}")
        tk.Label(self._socratic_win, text="Socratic Tutor", bg=C["bg"], fg=C["pri_lt"], font=F["title"]).pack(pady=(20,4))
        tk.Label(self._socratic_win, text="The AI will guide you to discover answers yourself. No spoon-feeding!", bg=C["bg"], fg=C["muted"], font=F["body"]).pack(pady=(0,16))
        ef = tk.Frame(self._socratic_win, bg=C["bg"], padx=30)
        ef.pack(fill="x")
        tk.Label(ef, text="Topic to explore:", bg=C["bg"], fg=C["text"], font=F["bold"]).pack(side="left")
        self._soc_topic = tk.Entry(ef, bg=C["input"], fg=C["text"], insertbackground=C["text"], relief="flat", font=F["body"], width=35)
        self._soc_topic.pack(side="left", padx=(10,0), ipady=6)
        self._soc_topic.insert(0, "Enter any topic...")
        self._soc_topic.bind("<FocusIn>", lambda e: self._soc_topic.delete(0,"end") if self._soc_topic.get()=="Enter any topic..." else None)
        mk_btn(ef, "Begin", self._socratic_begin, bg=C["accent"], px=14, py=5).pack(side="left", padx=(10,0))

        # FIX: Use [0] for frame (pack it), [1] for text widget (chat ops)
        self._soc_chat_frame, self._soc_chat = scrolled_txt(self._socratic_win, h=20)
        self._soc_chat_frame.pack(fill="both", expand=True, padx=30, pady=(16,0))
        txt_set(self._soc_chat, "Socratic Tutor Ready! Enter a topic above and click 'Begin'. The AI will ask you thought-provoking questions to help you discover the answer yourself. Tip: Think out loud and type your reasoning!")
        self._soc_chat.tag_configure("ai", foreground=C["pri_lt"], font=F["bold"])
        self._soc_chat.tag_configure("you", foreground=C["teal"], font=F["bold"])
        self._soc_chat.tag_configure("msg", foreground=C["text"], font=F["body"])

        ib = card(self._socratic_win)
        ib.pack(fill="x", padx=30, pady=(10,20))
        ii = tk.Frame(ib, bg=C["card"], padx=12, pady=10)
        ii.pack(fill="x")
        self._soc_input = tk.Text(ii, bg=C["input"], fg=C["text"], insertbackground=C["text"], relief="flat", font=F["body"], height=2, wrap="word", padx=8, pady=6)
        self._soc_input.pack(side="left", fill="x", expand=True, padx=(0,10))
        self._soc_input.bind("<Return>", lambda e: self._socratic_send() if not (e.state & 0x1) else None)
        mk_btn(ii, "Reply", self._socratic_send, bg=C["accent"], px=14, py=6).pack(side="left")
        self._soc_history = []
        self._soc_turn = 0

    def _socratic_begin(self):
        topic = self._soc_topic.get().strip()
        if not topic or topic == "Enter any topic...":
            messagebox.showwarning("Topic?", "Enter a topic first!", parent=self._socratic_win)
            return
        self._soc_topic.config(state="disabled")
        self._socratic_send(initial=topic)

    def _socratic_send(self, initial=None):
        user_text = initial or self._soc_input.get("1.0","end-1c").strip()
        if not user_text:
            return
        if not initial:
            self._soc_input.delete("1.0","end")
        self._soc_turn += 1
        self._soc_chat.config(state="normal")
        self._soc_chat.insert("end", "\nYou: ", "you")
        self._soc_chat.insert("end", user_text + "\n\n", "msg")
        self._soc_chat.insert("end", "Socratic Tutor is thinking...\n", "ai")
        self._soc_chat.config(state="disabled")
        self._soc_chat.see("end")
        self._socratic_win.update()
        level = self.app.user.get("edu","Bachelor's Degree") if self.app.user else "Bachelor's Degree"
        system = "You are a Socratic tutor teaching a " + level + " student. NEVER give direct answers. NEVER say 'The answer is...'. Instead, ask thought-provoking questions that guide the student to discover the answer themselves. Ask ONE question at a time. If the student is stuck, give a tiny hint but still make them think. Be encouraging but challenging. Keep responses under 150 words."
        msgs = self._soc_history[-10:] + [{"role":"user","content":user_text}]
        def _run():
            reply = call_mistral(msgs, system=system, max_tokens=400)
            self.after(0, lambda: self._socratic_got(reply, user_text))
        threading.Thread(target=_run, daemon=True).start()

    def _socratic_got(self, reply, user_text):
        self._soc_chat.config(state="normal")
        idx = self._soc_chat.search("thinking...", "1.0", "end")
        if idx:
            ls = self._soc_chat.index(f"{idx} linestart")
            le = self._soc_chat.index(f"{idx} lineend+1c")
            self._soc_chat.delete(ls, le)
            self._soc_chat.insert(ls, "Socratic Tutor:\n", "ai")
            self._soc_chat.insert(f"{ls}+1l", reply + "\n", "msg")
        self._soc_chat.config(state="disabled")
        self._soc_chat.see("end")
        self._soc_history.append({"role":"user","content":user_text})
        self._soc_history.append({"role":"assistant","content":reply})

    def _start_battle(self):
        self._b_after_id = None
        self._battle_win = tk.Toplevel(self)
        self._battle_win.title("AI Battle Mode")
        self._battle_win.configure(bg=C["bg"])
        self._battle_win.geometry("800x650")
        self._battle_win.resizable(True, True)
        self._battle_win.transient(self)
        self._battle_win.grab_set()
        self._battle_win.update_idletasks()
        SW, SH = self._battle_win.winfo_screenwidth(), self._battle_win.winfo_screenheight()
        self._battle_win.geometry(f"800x650+{(SW-800)//2}+{(SH-650)//2}")
        tk.Label(self._battle_win, text="AI Battle Mode", bg=C["bg"], fg=C["secondary"], font=F["title"]).pack(pady=(16,4))
        tk.Label(self._battle_win, text="You vs AI! First to answer correctly wins the round. Difficulty adapts automatically.", bg=C["bg"], fg=C["muted"], font=F["body"]).pack(pady=(0,12))
        sb = tk.Frame(self._battle_win, bg=C["bg"], padx=30)
        sb.pack(fill="x")
        self._b_user_score = 0
        self._b_ai_score = 0
        self._b_round = 1
        self._b_total_rounds = 7
        self._b_qdata = None
        self._b_busy = False
        usc = card(sb)
        usc.pack(side="left", fill="both", expand=True, padx=(0,8))
        tk.Label(usc, text="YOU", bg=C["card"], fg=C["teal"], font=F["h2"]).pack(pady=(10,2))
        self._b_user_lbl = tk.Label(usc, text="0", bg=C["card"], fg=C["teal"], font=("Helvetica",32,"bold"))
        self._b_user_lbl.pack()
        self._b_user_streak = tk.Label(usc, text="Streak: 0", bg=C["card"], fg=C["muted"], font=F["small"])
        self._b_user_streak.pack(pady=(0,10))
        tk.Label(sb, text="VS", bg=C["bg"], fg=C["dim"], font=("Helvetica",20,"bold")).pack(side="left", padx=10)
        aisc = card(sb)
        aisc.pack(side="left", fill="both", expand=True, padx=(8,0))
        tk.Label(aisc, text="AI", bg=C["card"], fg=C["secondary"], font=F["h2"]).pack(pady=(10,2))
        self._b_ai_lbl = tk.Label(aisc, text="0", bg=C["card"], fg=C["secondary"], font=("Helvetica",32,"bold"))
        self._b_ai_lbl.pack()
        self._b_ai_conf = tk.Label(aisc, text="Confidence: --%", bg=C["card"], fg=C["muted"], font=F["small"])
        self._b_ai_conf.pack(pady=(0,10))
        self._b_round_lbl = tk.Label(self._battle_win, text="Round 1 of 7", bg=C["bg"], fg=C["pri_lt"], font=F["h3"])
        self._b_round_lbl.pack(pady=(12,0))
        self._b_qframe = card(self._battle_win)
        self._b_qframe.pack(fill="both", expand=True, padx=30, pady=(12,0))
        self._b_qinner = tk.Frame(self._b_qframe, bg=C["card"], padx=20, pady=20)
        self._b_qinner.pack(fill="both", expand=True)
        ctrl = tk.Frame(self._battle_win, bg=C["bg"], padx=30, pady=10)
        ctrl.pack(fill="x")
        tk.Label(ctrl, text="Subject:", bg=C["bg"], fg=C["muted"], font=F["small"]).pack(side="left")
        self._b_subj = ttk.Combobox(ctrl, values=SUBJECTS, state="readonly", width=16, font=F["body"])
        self._b_subj.set(SUBJECTS[0])
        self._b_subj.pack(side="left", padx=(6,12))
        self._b_startbtn = mk_btn(ctrl, "Start Battle", self._battle_start, bg=C["secondary"], px=16, py=7)
        self._b_startbtn.pack(side="left")
        self._b_status = tk.Label(self._battle_win, text="Select a subject and click Start Battle!", bg=C["bg"], fg=C["muted"], font=F["small"])
        self._b_status.pack(pady=(4,16))

    def _battle_start(self):
        # Cancel any pending AI timer from previous round
        if hasattr(self, '_b_after_id') and self._b_after_id:
            try:
                self._battle_win.after_cancel(self._b_after_id)
            except:
                pass
            self._b_after_id = None
        self._b_startbtn.config(state="disabled", text="Loading...")
        self._b_status.config(text="Generating battle question (round " + str(self._b_round) + ")...", fg=C["warn"])
        self._battle_win.update()
        subj = self._b_subj.get()
        edu = self.app.user.get("edu","Bachelor's Degree") if self.app.user else "Bachelor's Degree"
        prev_q = ""
        if hasattr(self, '_b_prev_questions') and self._b_prev_questions:
            prev_q = "Previously asked: " + " | ".join(self._b_prev_questions[-3:])
        def _run():
            system = "You are a quiz battle generator for " + subj + " at " + edu + " level. Generate ONE unique multiple-choice question that is DIFFERENT from previous ones. Format: Q: question text | A) option | B) option | C) option | D) option | ANSWER: X (where X is A/B/C/D). Make it challenging."
            content = "Generate battle question for " + subj + " round " + str(self._b_round) + ". " + prev_q + " Make sure this question is completely different from previous ones."
            result = call_mistral([{"role":"user","content":content}], system=system, max_tokens=500)
            self.after(0, lambda: self._battle_load(result, retry=0))
        threading.Thread(target=_run, daemon=True).start()

    def _battle_load(self, raw_text, retry=0):
        self._b_startbtn.config(state="normal", text="Start Battle")
        q = self._parse_battle_q(raw_text)
        if not q:
            if retry < 2:
                next_retry = retry + 1
                self._b_status.config(text="Parse failed, retrying... (attempt " + str(next_retry) + ")", fg=C["warn"])
                self._battle_win.update()
                subj = self._b_subj.get()
                edu = self.app.user.get("edu","Bachelor's Degree") if self.app.user else "Bachelor's Degree"
                def _retry(r):
                    system = "You are a quiz generator. Generate ONE simple multiple-choice question for " + subj + " at " + edu + " level. Use EXACT format: Q: question | A) opt1 | B) opt2 | C) opt3 | D) opt4 | ANSWER: X"
                    content = "Generate a simple " + subj + " question. Use exact format with Q: A) B) C) D) ANSWER:"
                    result = call_mistral([{"role":"user","content":content}], system=system, max_tokens=500)
                    self.after(0, lambda res=result, ret=r: self._battle_load(res, retry=ret))
                threading.Thread(target=lambda r=next_retry: _retry(r), daemon=True).start()
                return
            self._b_status.config(text="Failed after 3 tries. Try a different subject!", fg=C["error"])
            for w in self._b_qinner.winfo_children():
                w.destroy()
            tk.Label(self._b_qinner, text="Could not parse. Raw output:", bg=C["card"], fg=C["error"], font=F["h2"]).pack(pady=(10,5))
            t = tk.Text(self._b_qinner, height=8, bg=C["input"], fg=C["text"], relief="flat", font=F["body"], wrap="word", padx=8, pady=6)
            t.pack(fill="x", padx=10, pady=5)
            t.insert("1.0", raw_text[:800])
            t.config(state="disabled")
            mk_btn(self._b_qinner, "Try Again", self._battle_start, bg=C["primary"], px=18, py=8).pack(pady=(10,0))
            return
        if not hasattr(self, '_b_prev_questions'):
            self._b_prev_questions = []
        self._b_prev_questions.append(q["question"][:50])
        if len(self._b_prev_questions) > 10:
            self._b_prev_questions.pop(0)
        self._b_qdata = q
        self._b_status.config(text="Battle! Answer before the AI does!", fg=C["success"])
        self._battle_show_q()

    def _parse_battle_q(self, text):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) < 4:
            return None

        q_text = ""
        q_idx = -1
        options = {}
        answer = ""

        for i, line in enumerate(lines):
            lu = line.upper().strip()
            # Question detection
            if not q_text and (lu.startswith("Q:") or lu.startswith("Q.") or lu.startswith("QUESTION:")):
                q_text = line.split(":", 1)[1].strip() if ":" in line else line[2:].strip()
                q_idx = i
                continue
            # Option detection - very flexible
            if not q_text and i == 0:
                # First line might be question without Q:
                if not any(lu.startswith(x) for x in ["A)","A ","A.","ANSWER","OPTION","CHOICE"]):
                    q_text = line
                    q_idx = i
                    continue
            # Options A-D
            for opt in ["A","B","C","D"]:
                if lu.startswith(opt + ")") or lu.startswith(opt + " ") or lu.startswith(opt + ".") or lu.startswith(opt + "-"):
                    val = line[1:].strip()
                    # Remove leading punctuation
                    while val and val[0] in ").:- ":
                        val = val[1:].strip()
                    if val:
                        options[opt] = val
                    break
            # Answer detection
            if "ANSWER" in lu:
                # Extract letter after ANSWER
                for c in line.upper():
                    if c in "ABCD":
                        answer = c
                        break
                # Also check after colon
                if ":" in line:
                    after = line.split(":")[-1].strip().upper()
                    for c in after:
                        if c in "ABCD":
                            answer = c
                            break

        # If no Q: found, use first line as question
        if not q_text and lines:
            q_text = lines[0]
            q_idx = 0

        if q_text and len(options) >= 2 and answer in options:
            for k in ["A","B","C","D"]:
                if k not in options:
                    options[k] = "Option " + k
            return {"question":q_text,"options":options,"answer":answer}
        return None

    def _battle_show_q(self):
        for w in self._b_qinner.winfo_children():
            w.destroy()
        q = self._b_qdata
        tk.Label(self._b_qinner, text=q["question"], bg=C["card"], fg=C["text"], font=F["h3"], wraplength=650, justify="left").pack(anchor="w", pady=(0,12))
        self._b_selected = tk.StringVar(value="")
        for opt_key in ["A","B","C","D"]:
            of = tk.Frame(self._b_qinner, bg=C["card"], padx=5, pady=3)
            of.pack(fill="x", pady=2)
            rb = tk.Radiobutton(of, text=opt_key + ") " + q["options"][opt_key], variable=self._b_selected, value=opt_key, bg=C["card"], fg=C["text"], font=F["body"], selectcolor=C["primary"], activebackground=C["card"])
            rb.pack(anchor="w")
        bf = tk.Frame(self._b_qinner, bg=C["card"])
        bf.pack(fill="x", pady=(15,0))
        self._b_submit = mk_btn(bf, "Submit Answer", self._battle_submit, bg=C["secondary"], px=20, py=8)
        self._b_submit.pack(side="left")
        self._b_timer = tk.Label(bf, text="AI thinking...", bg=C["card"], fg=C["warn"], font=F["body"])
        self._b_timer.pack(side="right")
        self._b_busy = True
        self._battle_ai_answer()

    def _battle_ai_answer(self):
        q = self._b_qdata
        correct = q["answer"]
        ai_correct = random.random() < 0.7
        opts = list(q["options"].keys())
        wrong_opts = [k for k in opts if k != correct]
        ai_answer = correct if ai_correct else (random.choice(wrong_opts) if wrong_opts else correct)
        delay = random.randint(3000, 8000)
        self._b_ai_ans = ai_answer
        self._b_ai_correct = ai_correct
        self._b_after_id = self._battle_win.after(delay, self._battle_ai_done)

    def _battle_ai_done(self):
        self._b_after_id = None
        # Check if widget still exists (user may have moved to next round)
        try:
            if self._b_timer.winfo_exists():
                self._b_timer.config(text="AI has answered!")
                self._b_busy = False
        except (tk.TclError, AttributeError):
            pass  # Widget was destroyed, ignore

    def _battle_submit(self):
        user_ans = self._b_selected.get()
        if not user_ans:
            messagebox.showwarning("Select", "Pick an answer!", parent=self._battle_win)
            return
        self._battle_resolve(user_ans, user_first=self._b_busy)

    def _battle_resolve(self, user_ans, user_first):
        # Cancel any pending AI timer to avoid TclError
        if hasattr(self, '_b_after_id') and self._b_after_id:
            try:
                self._battle_win.after_cancel(self._b_after_id)
            except:
                pass
            self._b_after_id = None
        self._b_busy = False
        q = self._b_qdata
        correct = q["answer"]
        user_correct = user_ans == correct
        if user_correct and user_first:
            self._b_user_score += 2
            result_text = "CORRECT + FAST! +2 points!"
            result_color = C["success"]
        elif user_correct and not user_first:
            self._b_user_score += 1
            result_text = "Correct but AI was faster! +1 point"
            result_color = C["teal"]
        else:
            self._b_user_score -= 1
            result_text = "Wrong! Correct was " + correct + ". -1 point"
            result_color = C["error"]
        if self._b_ai_correct:
            self._b_ai_score += 1
        self._b_user_lbl.config(text=str(self._b_user_score))
        self._b_ai_lbl.config(text=str(self._b_ai_score))
        self._b_user_streak.config(text="Streak: " + str(self._b_user_score))
        self._b_ai_conf.config(text="Confidence: " + str(random.randint(60,95)) + "%")
        for w in self._b_qinner.winfo_children():
            w.destroy()
        tk.Label(self._b_qinner, text=result_text, bg=C["card"], fg=result_color, font=F["h2"]).pack(pady=(20,10))
        tk.Label(self._b_qinner, text="Correct Answer: " + correct + ") " + q["options"][correct], bg=C["card"], fg=C["text"], font=F["body"]).pack()
        tk.Label(self._b_qinner, text="Your answer: " + user_ans + ") " + q["options"][user_ans], bg=C["card"], fg=C["muted"], font=F["body"]).pack(pady=(4,0))
        self._b_round += 1
        if self._b_round > self._b_total_rounds:
            self._battle_end()
        else:
            self._b_round_lbl.config(text="Round " + str(self._b_round) + " of " + str(self._b_total_rounds))
            mk_btn(self._b_qinner, "Next Round", self._battle_next, bg=C["primary"], px=18, py=8).pack(pady=(20,0))

    def _battle_next(self):
        self._battle_start()

    def _battle_end(self):
        for w in self._b_qinner.winfo_children():
            w.destroy()
        if self._b_user_score > self._b_ai_score:
            winner = "YOU WIN!"
            col = C["success"]
        elif self._b_ai_score > self._b_user_score:
            winner = "AI WINS!"
            col = C["secondary"]
        else:
            winner = "TIE!"
            col = C["pri_lt"]
        tk.Label(self._b_qinner, text="BATTLE OVER!", bg=C["card"], fg=C["pri_lt"], font=F["title"]).pack(pady=(20,10))
        tk.Label(self._b_qinner, text=winner, bg=C["card"], fg=col, font=("Helvetica",28,"bold")).pack()
        tk.Label(self._b_qinner, text="Final Score — You: " + str(self._b_user_score) + " | AI: " + str(self._b_ai_score), bg=C["card"], fg=C["text"], font=F["h3"]).pack(pady=(10,0))
        if self._b_user_score > self._b_ai_score:
            tk.Label(self._b_qinner, text="Study King! AI bows to your knowledge!", bg=C["card"], fg=C["teal"], font=F["h2"]).pack(pady=(10,0))
        mk_btn(self._b_qinner, "New Battle", self._battle_restart, bg=C["secondary"], px=20, py=10).pack(pady=(20,0))

    def _battle_restart(self):
        self._b_user_score = 0
        self._b_ai_score = 0
        self._b_round = 1
        self._b_user_lbl.config(text="0")
        self._b_ai_lbl.config(text="0")
        self._b_round_lbl.config(text="Round 1 of 7")
        self._b_status.config(text="Select subject and click Start Battle!", fg=C["muted"])
        for w in self._b_qinner.winfo_children():
            w.destroy()
        tk.Label(self._b_qinner, text="Ready for battle?", bg=C["card"], fg=C["muted"], font=F["h2"]).pack(pady=40)

    def _start_concept_web(self):
        self._web_win = tk.Toplevel(self)
        self._web_win.title("Concept Connector")
        self._web_win.configure(bg=C["bg"])
        self._web_win.geometry("950x750")
        self._web_win.resizable(True, True)
        self._web_win.transient(self)
        self._web_win.grab_set()
        self._web_win.update_idletasks()
        SW, SH = self._web_win.winfo_screenwidth(), self._web_win.winfo_screenheight()
        self._web_win.geometry(f"950x750+{(SW-950)//2}+{(SH-750)//2}")
        tk.Label(self._web_win, text="Concept Connector", bg=C["bg"], fg=C["teal"], font=F["title"]).pack(pady=(16,4))
        tk.Label(self._web_win, text="Visual map of your study topics and how they connect!", bg=C["bg"], fg=C["muted"], font=F["body"]).pack(pady=(0,12))

        # Canvas frame
        cf = tk.Frame(self._web_win, bg=C["bg"], padx=20, pady=10)
        cf.pack(fill="both", expand=True)
        self._web_canvas = tk.Canvas(cf, bg=C["bg"], highlightthickness=0, width=900, height=600)
        self._web_canvas.pack(fill="both", expand=True)

        # Status and button
        bf = tk.Frame(self._web_win, bg=C["bg"], padx=20, pady=10)
        bf.pack(fill="x")
        self._web_status = tk.Label(bf, text="Click Generate to build your concept web!", bg=C["bg"], fg=C["muted"], font=F["small"])
        self._web_status.pack(side="left")
        mk_btn(bf, "Generate My Concept Web", self._web_generate, bg=C["teal"], px=20, py=10).pack(side="right")

    def _web_generate(self):
        self._web_status.config(text="Building your concept web...", fg=C["warn"])
        self._web_win.update()

        uid = self.app.user["id"] if self.app.user else 0
        sessions = self.db.get_sessions(uid, 100) if uid else []
        subjects = self.app.subjects() if self.app.user else []

        if not sessions and not subjects:
            self._web_status.config(text="No study data yet! Study some topics first.", fg=C["error"])
            return

        # Build web purely in Python - no AI needed for drawing
        self._build_concept_web(sessions, subjects)

    def _build_concept_web(self, sessions, subjects):
        self._web_canvas.delete("all")

        # Collect all unique topics from sessions
        all_topics = []
        topic_to_subject = {}
        for s in sessions:
            subj = s.get("subject", "Unknown")
            topic = s.get("topic", "Untitled")
            if topic and topic not in [t["name"] for t in all_topics]:
                all_topics.append({"name": topic, "subject": subj})
                topic_to_subject[topic] = subj

        # Add subjects as main nodes if not already covered
        for subj in subjects:
            if subj not in [t["subject"] for t in all_topics]:
                all_topics.append({"name": subj, "subject": subj})

        if not all_topics:
            all_topics = [{"name": "Start Studying!", "subject": "General"}]

        # Subject colors
        subj_colors = {
            "Mathematics": "#4361ee", "Physics": "#e94560", "Chemistry": "#00d4aa",
            "Biology": "#7b2ff7", "Computer Science": "#ffb300", "History": "#ff6b6b",
            "Geography": "#4ecdc4", "Literature": "#ff8c42", "Economics": "#95e1d3",
            "Psychology": "#f38181", "General": "#4361ee"
        }

        canvas_w, canvas_h = 900, 600
        center_x, center_y = canvas_w // 2, canvas_h // 2

        # Group topics by subject
        subject_groups = {}
        for t in all_topics:
            subj = t["subject"]
            if subj not in subject_groups:
                subject_groups[subj] = []
            subject_groups[subj].append(t["name"])

        nodes = []
        connections = []

        # Place subject nodes in a circle
        subj_list = list(subject_groups.keys())
        n_subjects = len(subj_list)
        radius = 200

        for i, subj in enumerate(subj_list):
            angle = (2 * 3.14159 * i) / max(n_subjects, 1)
            x = center_x + int(radius * __import__('math').cos(angle))
            y = center_y + int(radius * __import__('math').sin(angle))
            color = subj_colors.get(subj, "#4361ee")
            nodes.append({"name": subj, "x": x, "y": y, "size": 45, "color": color, "type": "subject"})

        # Place topic nodes around their subjects
        topic_radius = 90
        for i, subj in enumerate(subj_list):
            subj_node = nodes[i]
            topics = subject_groups[subj]
            for j, topic in enumerate(topics[:6]):  # Max 6 topics per subject
                angle = (2 * 3.14159 * j) / max(len(topics), 1)
                x = subj_node["x"] + int(topic_radius * __import__('math').cos(angle))
                y = subj_node["y"] + int(topic_radius * __import__('math').sin(angle))
                # Keep within canvas bounds
                x = max(60, min(canvas_w-60, x))
                y = max(60, min(canvas_h-60, y))
                color = subj_colors.get(subj, "#4361ee")
                # Lighter shade for topics
                nodes.append({"name": topic[:20], "x": x, "y": y, "size": 28, "color": color, "type": "topic"})
                connections.append({"from": subj, "to": topic[:20]})

        # Add cross-subject connections (topics with similar names)
        topic_nodes = [n for n in nodes if n["type"] == "topic"]
        for i, t1 in enumerate(topic_nodes):
            for t2 in topic_nodes[i+1:]:
                # Simple similarity: shared words
                words1 = set(t1["name"].lower().split())
                words2 = set(t2["name"].lower().split())
                if words1 & words2 and t1["color"] != t2["color"]:
                    connections.append({"from": t1["name"], "to": t2["name"]})

        # Draw connections
        node_dict = {n["name"]: n for n in nodes}
        for conn in connections:
            if conn["from"] in node_dict and conn["to"] in node_dict:
                n1 = node_dict[conn["from"]]
                n2 = node_dict[conn["to"]]
                # Different line style for cross-subject
                is_cross = n1.get("color") != n2.get("color")
                line_color = C["dim"] if not is_cross else "#5555aa"
                width = 1 if not is_cross else 2
                dash = () if not is_cross else (4, 4)
                self._web_canvas.create_line(n1["x"], n1["y"], n2["x"], n2["y"], 
                                              fill=line_color, width=width, dash=dash)

        # Draw nodes
        for node in nodes:
            x, y = node["x"], node["y"]
            size = node["size"]
            color = node["color"]
            name = node["name"]

            # Glow effect for subjects
            if node["type"] == "subject":
                self._web_canvas.create_oval(x-size-5, y-size-5, x+size+5, y+size+5, 
                                              fill="", outline=color, width=1, stipple="gray50")

            self._web_canvas.create_oval(x-size, y-size, x+size, y+size, 
                                          fill=color, outline=C["white"], width=2)
            self._web_canvas.create_text(x, y, text=name, fill=C["white"], 
                                          font=F["bold"] if node["type"]=="subject" else F["body"],
                                          justify="center", width=size*2-10)

        # Legend
        legend_y = 20
        tk.Label(self._web_win, text="— Same Subject", bg=C["bg"], fg=C["dim"], font=F["small"]).place(x=20, y=legend_y)
        tk.Label(self._web_win, text="- - Cross Subject", bg=C["bg"], fg="#5555aa", font=F["small"]).place(x=20, y=legend_y+20)

        self._web_canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))
        self._web_status.config(text="Concept web built with " + str(len(nodes)) + " nodes and " + str(len(connections)) + " connections!", fg=C["success"])

    def on_show(self):
        pass

class ProgressPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.hdr("📊 Progress","Learning Statistics")
        self._wrap = tk.Frame(self,bg=C["bg"])
        self._wrap.pack(fill="both",expand=True)

    def on_show(self):
        for w in self._wrap.winfo_children(): w.destroy()
        self._pcnv, body = make_scroll_canvas(self._wrap)
        p = tk.Frame(body,bg=C["bg"],padx=30,pady=18)
        p.pack(fill="both",expand=True)

        uid = self.app.user["id"] if self.app.user else 0
        prg   = self.db.get_progress(uid) if uid else []
        sess  = self.db.get_sessions(uid,20) if uid else []
        total = self.db.count_sessions(uid) if uid else 0
        avg   = int(sum(x["score"] for x in prg)/len(prg)) if prg else 0
        top   = prg[0]["subject"] if prg else "—"

        # Summary cards
        row = tk.Frame(p,bg=C["bg"]); row.pack(fill="x",pady=(0,22))
        for icon,val,lbl_,col in [
            ("🎯",f"{avg}%",    "Average Score",   C["primary"]),
            ("📚",str(total),   "Total Sessions",  C["accent"]),
            ("🏆",top,          "Top Subject",     C["teal"]),
            ("📈",str(len(prg)),"Tracked Subjects", C["secondary"]),
        ]:
            c = card(row); c.pack(side="left",fill="both",expand=True,padx=(0,10))
            tk.Label(c,text=icon,bg=C["card"],font=("Helvetica",20)).pack(pady=(12,2))
            tk.Label(c,text=val, bg=C["card"],fg=col,  font=F["h2"]).pack()
            tk.Label(c,text=lbl_,bg=C["card"],fg=C["muted"],font=F["small"]).pack(pady=(2,12))

        if not prg:
            c = card(p); c.pack(fill="x")
            tk.Label(c,text="No progress yet — start studying!",
                     bg=C["card"],fg=C["muted"],font=F["body"]).pack(padx=18,pady=18)
            return

        # Progress bars
        tk.Label(p,text="Subject Mastery",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(0,8))
        pc = card(p); pc.pack(fill="x",pady=(0,22))
        for px_ in prg:
            r = tk.Frame(pc,bg=C["card"]); r.pack(fill="x",padx=14,pady=6)
            tk.Label(r,text=px_["subject"],bg=C["card"],fg=C["text"],
                     font=F["body"],width=20,anchor="w").pack(side="left")
            sc = px_["score"]
            st = "Good" if sc>=70 else "Mid" if sc>=40 else "Low"
            ttk.Progressbar(r,style=f"{st}.Horizontal.TProgressbar",
                            orient="horizontal",length=280,
                            mode="determinate",maximum=100,value=sc).pack(
                                side="left",padx=(0,10))
            tk.Label(r,text=f"{sc}%  ·  {px_['sessions']} sessions",
                     bg=C["card"],fg=C["muted"],font=F["small"]).pack(side="left")

        # Session table
        tk.Label(p,text="Session History",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(0,8))
        tree = ttk.Treeview(p,columns=("s","t","d"),show="headings",height=10)
        tree.heading("s",text="Subject"); tree.heading("t",text="Topic")
        tree.heading("d",text="Date & Time")
        tree.column("s",width=160); tree.column("t",width=290); tree.column("d",width=140)
        tsb2 = ttk.Scrollbar(p,orient="vertical",command=tree.yview)
        tree.configure(yscrollcommand=tsb2.set)
        tsb2.pack(side="right",fill="y")
        tree.pack(fill="x",pady=(0,4))
        for s in sess:
            tree.insert("","end",values=(s["subject"],s["topic"],s["ts"][:16]))

        # Force scrollregion update
        self._wrap.update_idletasks()
        self._pcnv.configure(scrollregion=self._pcnv.bbox("all"))


# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
class SettingsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.hdr("⚙️ Settings","Profile & Preferences")
        self._sv = {}
        self._build()

    def _build(self):
        body = tk.Frame(self,bg=C["bg"],padx=30,pady=16)
        body.pack(fill="both",expand=True)

        # Profile
        tk.Label(body,text="Profile",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(0,8))
        pc = card(body); pc.pack(fill="x",pady=(0,20))
        pi = tk.Frame(pc,bg=C["card"],padx=18,pady=16); pi.pack(fill="x")

        self._uname = tk.Label(pi,text="—",bg=C["card"],fg=C["text"],font=F["body"])
        self._email = tk.Label(pi,text="—",bg=C["card"],fg=C["text"],font=F["body"])
        for i,(lbl_,wid_) in enumerate([("Username",self._uname),("Email",self._email)]):
            tk.Label(pi,text=lbl_,bg=C["card"],fg=C["muted"],font=F["small"],
                     anchor="w").grid(row=i,column=0,sticky="w",pady=7,padx=(0,18))
            wid_.grid(row=i,column=1,sticky="w")

        tk.Label(pi,text="Education Level",bg=C["card"],fg=C["muted"],
                 font=F["small"],anchor="w").grid(row=2,column=0,sticky="w",pady=7,padx=(0,18))
        self._edu = ttk.Combobox(pi,values=EDU_LEVELS,state="readonly",width=28,font=F["body"])
        self._edu.grid(row=2,column=1,sticky="w")

        tk.Label(pi,text="Profile Picture",bg=C["card"],fg=C["muted"],
                 font=F["small"],anchor="w").grid(row=3,column=0,sticky="w",pady=7,padx=(0,18))
        avf = tk.Frame(pi,bg=C["card"]); avf.grid(row=3,column=1,sticky="w")
        self._av = tk.StringVar()
        tk.Entry(avf,textvariable=self._av,bg=C["input"],fg=C["text"],
                 insertbackground=C["text"],relief="flat",font=F["small"],width=26).pack(
                     side="left",ipady=5)
        mk_btn(avf,"Browse",self._brow,bg=C["input"],fg=C["muted"],px=8,py=4).pack(
            side="left",padx=(8,0))

        # Subjects
        tk.Label(body,text="Subject Preferences",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(0,8))
        sc = card(body); sc.pack(fill="x",pady=(0,18))
        si = tk.Frame(sc,bg=C["card"],padx=14,pady=14); si.pack(fill="x")
        for i,s in enumerate(SUBJECTS):
            v = tk.BooleanVar(); self._sv[s] = v
            ttk.Checkbutton(si,text=s,variable=v).grid(
                row=i//3,column=i%3,sticky="w",padx=16,pady=4)

        mk_btn(body,"  💾 Save Profile  ",self._save,
               bg=C["primary"],px=20,py=10).pack(anchor="w")

        # API Key
        tk.Label(body,text="Mistral API Key",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(22,8))
        akc = card(body); akc.pack(fill="x",pady=(0,18))
        aki = tk.Frame(akc,bg=C["card"],padx=16,pady=14); aki.pack(fill="x")
        tk.Label(aki,
            text="Enter your Mistral API key to enable real AI (Study + Ask AI).",
            bg=C["card"],fg=C["muted"],font=F["small"],anchor="w").pack(fill="x",pady=(0,6))
        self._api = tk.Entry(aki,show="•",bg=C["input"],fg=C["text"],
                              insertbackground=C["text"],relief="flat",
                              font=F["mono"],width=52)
        self._api.pack(fill="x",ipady=8,pady=(0,8))
        self._api.insert(0, MISTRAL_API_KEY)
        ar = tk.Frame(aki,bg=C["card"]); ar.pack(fill="x")
        mk_btn(ar,"✓ Apply Key",self._apply_key,bg=C["teal"],px=14,py=6).pack(side="left")
        mk_btn(ar,"👁 Show/Hide",self._toggle_key,bg=C["card"],
               fg=C["muted"],px=10,py=6).pack(side="left",padx=(10,0))
        self._key_vis = False
        tk.Label(aki,
            text="Key is held in memory only — not saved to disk.\n"
                 "Get a free key at: console.mistral.ai",
            bg=C["card"],fg=C["dim"],font=F["small"],justify="left").pack(
                anchor="w",pady=(8,0))

        # About
        tk.Label(body,text="About",bg=C["bg"],fg=C["text"],
                 font=F["h3"],anchor="w").pack(fill="x",pady=(22,8))
        ab = card(body); ab.pack(fill="x")
        tk.Label(ab,
            text=f"✦ StudyAI  v2.0  ·  Python {sys.version[:6]}  ·  SQLite  ·  "
                 f"Pillow {'✅' if PIL_AVAILABLE else '⚠ not installed (pip install Pillow)'}\n"
                 f"AI Model: mistral-large-latest via Mistral API\n"
                 f"Database: {DB_PATH.resolve()}",
            bg=C["card"],fg=C["muted"],font=F["small"],
            justify="left",anchor="w").pack(fill="x",padx=16,pady=14)

    def on_show(self):
        u = self.app.user or {}
        self._uname.config(text=u.get("username",""))
        self._email.config(text=u.get("email",""))
        self._edu.set(u.get("edu",EDU_LEVELS[0]))
        self._av.set(u.get("avatar",""))
        subs = self.app.subjects() if self.app.user else []
        for s,v in self._sv.items(): v.set(s in subs)
        self._api.delete(0,"end")
        self._api.insert(0, MISTRAL_API_KEY)

    def _brow(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images","*.png *.jpg *.jpeg *.gif *.bmp"),("All","*.*")])
        if p: self._av.set(p)

    def _save(self):
        if not self.app.user:
            messagebox.showwarning("Error","Not logged in!",parent=self); return
        edu  = self._edu.get()
        subs = [s for s,v in self._sv.items() if v.get()]
        av   = self._av.get().strip()
        self.db.update_user(self.app.user["id"], edu, subs, av)
        self.app.user["edu"]      = edu
        self.app.user["subjects"] = json.dumps(subs)
        self.app.user["avatar"]   = av
        self.app._lvl_lbl.config(
            text=edu.split("/")[0].split("'")[0].strip() or "Student")
        messagebox.showinfo("Saved","Profile updated!",parent=self)

    def _apply_key(self):
        global MISTRAL_API_KEY
        MISTRAL_API_KEY = self._api.get().strip()
        if MISTRAL_API_KEY:
            messagebox.showinfo("API Key Applied",
                "API key set for this session.\n"
                "Study Material and Ask AI will now use real Mistral responses!",
                parent=self)
        else:
            messagebox.showinfo("Offline Mode",
                "No key set — running in offline mode.",parent=self)

    def _toggle_key(self):
        self._key_vis = not self._key_vis
        self._api.config(show="" if self._key_vis else "•")


# ═══════════════════════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
    