from flask import Flask, render_template_string
import sqlite3
import os
import time
import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL
)
""")

conn.commit()

app = Flask(__name__)

START_TIME = time.time()

@app.route("/")
def dashboard():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # 黑名單人數
    cursor.execute("SELECT COUNT(*) FROM blacklist")
    blacklist_count = cursor.fetchone()[0]

    # 防炸狀態（抓第一個伺服器）
    cursor.execute("SELECT anti_channel_create, anti_channel_delete, anti_role_delete, anti_guild_rename FROM settings LIMIT 1")
    settings = cursor.fetchone()

    if settings:
        protection_on = all(settings)
    else:
        protection_on = False

    uptime = int(time.time() - START_TIME)

    html = f"""
    <html>
    <head>
        <title>喵總管後台</title>
        <style>
            body {{
                background-color: #0f172a;
                color: white;
                font-family: Arial;
                text-align: center;
                padding: 40px;
            }}
            .card {{
                background: #1e293b;
                padding: 20px;
                margin: 20px auto;
                width: 300px;
                border-radius: 15px;
                box-shadow: 0 0 20px rgba(0,0,0,0.5);
            }}
            h1 {{ color: #38bdf8; }}
            .good {{ color: #22c55e; }}
            .bad {{ color: #ef4444; }}
        </style>
    </head>
    <body>
        <h1>🐾 喵總管 控制台</h1>

        <div class="card">
            <h2>封鎖總人數</h2>
            <p style="font-size: 28px;">{blacklist_count}</p>
        </div>

        <div class="card">
            <h2>防炸系統</h2>
            <p class="{'good' if protection_on else 'bad'}">
                {'🟢 啟用中' if protection_on else '🔴 已關閉'}
            </p>
        </div>

        <div class="card">
            <h2>機器人狀態</h2>
            <p class="good">🟢 運行中</p>
            <p>運行時間：{uptime} 秒</p>
        </div>

    </body>
    </html>
    """

    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
