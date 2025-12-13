import json
import os

USER_DATA_FILE = "users.json"

def load_users():
    if not os.path.exists(USER_DATA_FILE):
        return {}
    try:
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f)

def add_favorite(user_id, year, sem, course):
    data = load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"favorites": []}
    
    # Check for duplicates
    for fav in data[uid]["favorites"]:
        if fav["course"] == course:
            return
            
    data[uid]["favorites"].append({
        "year": year,
        "sem": sem,
        "course": course
    })
    save_users(data)

def remove_favorite(user_id, course):
    data = load_users()
    uid = str(user_id)
    if uid in data:
        data[uid]["favorites"] = [f for f in data[uid]["favorites"] if f["course"] != course]
        save_users(data)

def get_favorites(user_id):
    data = load_users()
    uid = str(user_id)
    return data.get(uid, {}).get("favorites", [])

def is_favorite(user_id, course):
    favs = get_favorites(user_id)
    for f in favs:
        if f["course"] == course:
            return True
    return False
