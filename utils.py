import os
import json
import asyncio

def load(file):
    """自動建立檔案並讀取 JSON"""
    if not os.path.exists(file):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w") as f:
            json.dump({}, f)
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    """寫入 JSON"""
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# cooldown 工具
async def cooldown_check(user_id, action, cd_time):
    """檢查 cooldown"""
    cooldown_file = "database/cooldown.json"
    data = load(cooldown_file)
    if str(user_id) not in data:
        data[str(user_id)] = {}
    import time
    now = time.time()
    if action in data[str(user_id)] and now < data[str(user_id)][action]:
        return False, int(data[str(user_id)][action] - now)
    data[str(user_id)][action] = now + cd_time
    save(cooldown_file, data)
    return True, 0
