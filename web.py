from flask import Flask, redirect, request, session, render_template
import requests, sqlite3, secrets, time

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

CLIENT_ID = "1442489303274881197"
CLIENT_SECRET = "pntn2nklxBQj7fU0693SloE86FgPBhf4"
REDIRECT_URI = "http://localhost:8080/callback"
DISCORD_API = "https://discord.com/api"

# 建立資料庫
conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id TEXT PRIMARY KEY,
    anti_channel_create INTEGER DEFAULT 0,
    anti_channel_delete INTEGER DEFAULT 0,
    anti_role_delete INTEGER DEFAULT 0,
    anti_guild_rename INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS welcome (
guild_id TEXT PRIMARY KEY,
enabled INTEGER,
channel_id TEXT,
message TEXT
)
""")
conn.commit()
conn.close()

START_TIME = time.time()


@app.route("/")
def home():
    if "token" in session:
        return redirect("/guilds")
    return render_template("login.html")

@app.route("/login")
def login():
    return redirect(
        f"{DISCORD_API}/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify guilds"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(f"{DISCORD_API}/oauth2/token", data=data, headers=headers)
    token = r.json().get("access_token")
    session["token"] = token
    return redirect("/guilds")

@app.route("/logout")
def logout():
    session.pop("token", None)
    return redirect("/")

@app.route("/guilds")
def guilds():
    token = session.get("token")
    if not token:
        return redirect("/")
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=headers)
    all_guilds = r.json()
    # 過濾管理員權限
    guilds = [g for g in all_guilds if g["permissions"] & 8]
    return render_template("guilds.html", guilds=guilds)

@app.route("/dashboard/<guild_id>")
def dashboard(guild_id):
    page = request.args.get("page", "overview")

    # 先抓伺服器名稱和 icon
    token = session.get("token")
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=headers)

    guild_name = "Unknown"
    guild_icon = None
    for g in r.json():
        if g["id"] == guild_id:
            guild_name = g["name"]
            guild_icon = g["icon"]

    # 再連資料庫抓設定
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # 歡迎訊息
    cursor.execute("SELECT enabled, channel_id, message FROM welcome WHERE guild_id=? LIMIT 1", (guild_id,))
    w = cursor.fetchone()
    if w:
        welcome = {"enabled": w[0], "channel_id": w[1], "message": w[2]}
    else:
        # 即使資料庫沒紀錄，也給一個預設 dict
        welcome = {"enabled": 0, "channel_id": "", "message": ""}

    # 黑名單
    cursor.execute("SELECT user_id FROM blacklist")
    blacklist = [{"user_id": u[0]} for u in cursor.fetchall()]

    # 防炸
    cursor.execute("SELECT anti_channel_create, anti_channel_delete, anti_role_delete, anti_guild_rename FROM settings WHERE guild_id=? LIMIT 1", (guild_id,))
    s = cursor.fetchone()
    if s:
        protection = {
            "anti_channel_create": s[0],
            "anti_channel_delete": s[1],
            "anti_role_delete": s[2],
            "anti_guild_rename": s[3],
        }
    else:
        protection = {
            "anti_channel_create": 0,
            "anti_channel_delete": 0,
            "anti_role_delete": 0,
            "anti_guild_rename": 0,
        }

    conn.close()
    uptime = int(time.time() - START_TIME)

    return render_template("dashboard.html",
                           page=page,
                           guild_id=guild_id,
                           guild_name=guild_name,
                           guild_icon=guild_icon,
                           protection=protection,
                           blacklist=blacklist,
                           welcome=welcome,  # ← 確保這裡有
                           uptime=uptime,
                           title="控制台")

@app.route("/update_protection/<guild_id>", methods=["POST"])
def update_protection(guild_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    anti_channel_create = 1 if request.form.get("anti_channel_create") else 0
    anti_channel_delete = 1 if request.form.get("anti_channel_delete") else 0
    anti_role_delete = 1 if request.form.get("anti_role_delete") else 0
    anti_guild_rename = 1 if request.form.get("anti_guild_rename") else 0
    cursor.execute("""
    INSERT INTO settings (guild_id, anti_channel_create, anti_channel_delete, anti_role_delete, anti_guild_rename)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(guild_id) DO UPDATE SET
        anti_channel_create=excluded.anti_channel_create,
        anti_channel_delete=excluded.anti_channel_delete,
        anti_role_delete=excluded.anti_role_delete,
        anti_guild_rename=excluded.anti_guild_rename
    """, (guild_id, anti_channel_create, anti_channel_delete, anti_role_delete, anti_guild_rename))
    conn.commit()
    conn.close()
    return redirect(f"/dashboard/{guild_id}?page=protection")


@app.route("/update_blacklist/<guild_id>", methods=["POST"])
def update_blacklist(guild_id):
    user_id = request.form.get("user_id")
    if user_id:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO blacklist (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
    return redirect(f"/dashboard/{guild_id}?page=blacklist")

@app.route("/update_welcome/<guild_id>", methods=["POST"])
def update_welcome(guild_id):

    enabled = 1 if request.form.get("enabled") else 0
    channel_id = request.form.get("channel_id")
    message = request.form.get("message")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO welcome (guild_id, enabled, channel_id, message)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(guild_id) DO UPDATE SET
        enabled=excluded.enabled,
        channel_id=excluded.channel_id,
        message=excluded.message
    """,(guild_id, enabled, channel_id, message))

    conn.commit()
    conn.close()

    return redirect(f"/dashboard/{guild_id}?page=welcome")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
