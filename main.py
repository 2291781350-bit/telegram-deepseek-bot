import os
import requests
import schedule
import time
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== 配置区（从环境变量读取） ====================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
CHARACTER_SETTING = os.environ.get("CHARACTER_SETTING", "你是一个友好的AI助手")
YOUR_CHAT_ID = os.environ.get("YOUR_CHAT_ID")

# 存储你和机器人的对话历史（简化版，只保留最近20条）
conversation_history = []

def call_deepseek(messages):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_msg = {"role": "system", "content": CHARACTER_SETTING}
    all_messages = [system_msg] + messages[-19:]  # 保留最近19条 + system prompt
    
    data = {
        "model": "deepseek-chat",
        "messages": all_messages,
        "temperature": 0.9,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"DeepSeek 错误: {e}")
        return "呜呜，我的大脑卡住了，等一下下好吗？"

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=data, timeout=10)

def send_active_message():
    """主动发消息给你"""
    try:
        if conversation_history:
            recent = conversation_history[-4:]  # 最近4条
        else:
            recent = [{"role": "user", "content": "你好呀"}]
        
        trigger = {
            "role": "user",
            "content": "（系统提示：你注意到用户已经有一段时间没说话了。请根据你的人设，主动发起一个自然的、关心用户的话题。直接说出你要说的话，不要加前缀。）"
        }
        
        messages_for_ai = recent + [trigger]
        ai_message = call_deepseek(messages_for_ai)
        
        if ai_message and YOUR_CHAT_ID:
            send_telegram_message(YOUR_CHAT_ID, ai_message)
            conversation_history.append({"role": "assistant", "content": ai_message})
            print(f"主动消息已发送: {ai_message}")
    except Exception as e:
        print(f"主动发送失败: {e}")

def run_scheduler():
    """定时任务"""
    # 每天早上9点、中午12点、下午3点、晚上8点、晚上11点主动发消息
    schedule.every().day.at("09:00").do(send_active_message)
    schedule.every().day.at("12:00").do(send_active_message)
    schedule.every().day.at("15:00").do(send_active_message)
    schedule.every().day.at("20:00").do(send_active_message)
    schedule.every().day.at("23:00").do(send_active_message)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    
    if "message" in update and "text" in update["message"]:
        chat_id = str(update["message"]["chat"]["id"])
        user_message = update["message"]["text"]
        
        # 存储用户消息
        conversation_history.append({"role": "user", "content": user_message})
        if len(conversation_history) > 20:
            conversation_history.pop(0)
        
        # 生成 AI 回复
        ai_reply = call_deepseek(conversation_history)
        conversation_history.append({"role": "assistant", "content": ai_reply})
        
        # 发送回复
        send_telegram_message(chat_id, ai_reply)
    
    return jsonify({"status": "ok"})

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    # 启动定时任务线程
    threading.Thread(target=run_scheduler, daemon=True).start()
    # 启动 Flask 服务
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
