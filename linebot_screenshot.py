from flask import Flask, request, abort, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
from dotenv import load_dotenv
import os, threading ,glob

load_dotenv()

print("DEBUG ---")
print(f"CHANNEL_SECRET : {os.getenv('LINE_CHANNEL_SECRET')}")
print(f"CHANNEL_TOKEN  : {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}")
print(f"APP_USERNAME   : {os.getenv('APP_USERNAME')}")
print(f"BASE_URL       : {os.getenv('BASE_URL')}")
print("---")

os.makedirs("image", exist_ok=True)

app = Flask(__name__)

# ==============================
# ตั้งค่า Line Bot
# ==============================
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET       = os.getenv("LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler       = WebhookHandler(CHANNEL_SECRET)

# ==============================
# ตั้งค่า Login เว็บ
# ==============================
LOGIN_URL    = os.getenv("LOGIN_URL")
EXPECTED_URL = os.getenv("EXPECTED_URL")
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

# ==============================
# Keyword → URL mapping
# ==============================
BRANCH_MAP = {
    "greenwing":  "https://www.saucedemo.com/inventory.html",
    "bigwing":       "https://www.saucedemo.com/cart.html",
    # "cubhouse": "https://example.com/branch-other",
}

# ==============================
# ✅ Flask serve รูปจากโฟลเดอร์ image/
# ==============================
@app.route("/image/<filename>")
def serve_image(filename):
    return send_from_directory("image", filename)
    
# ==============================
# ลบรูปเก่า
# ==============================
def delete_old_images() -> int:
    files = glob.glob("image/*.png") + glob.glob("image/*.jpg")
    for f in files:
        os.remove(f)
    print(f"🗑️  ลบรูปทั้งหมด {len(files)} ไฟล์")
    return len(files)
# ==============================
# แคปรูปเว็บ
# ==============================
def capture_screenshot(target_url: str) -> str | None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ])
            page    = browser.new_page()

            # Login
            page.goto(LOGIN_URL)
            page.wait_for_load_state("domcontentloaded")
            page.locator('#user-name').fill(APP_USERNAME)
            page.locator('#password').fill(APP_PASSWORD)
            page.locator('#login-button').click()

            try:
                page.wait_for_url("**/inventory.html", timeout=10000)
            except PlaywrightTimeout:
                print("❌ Login ล้มเหลว")
                browser.close()
                return None

            # ไปหน้าที่ต้องการ
            page.goto(target_url)
            page.wait_for_load_state("domcontentloaded")

            # บันทึกรูป
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename  = f"screenshot_{timestamp}.png"
            filepath  = os.path.join("image", filename)
            page.screenshot(path=filepath, full_page=True)
            browser.close()

            print(f"📸 แคปรูปสำเร็จ: {filepath}")
            return filename  # ✅ return แค่ชื่อไฟล์

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ==============================
# Webhook
# ==============================
@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    keyword     = event.message.text.strip().lower()
    reply_token = event.reply_token
    source_type = event.source.type  # "group", "room", "user"

    if source_type == "group":
        target_id = event.source.group_id
    elif source_type == "room":
        target_id = event.source.room_id
    else:
        target_id = event.source.user_id  # ส่วนตัว

    print(f"📌 source_type : {event.source.type}")
    print(f"📌 target_id   : {target_id}")

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if keyword not in BRANCH_MAP:
            branch_list = "\n".join([f"• {k}" for k in BRANCH_MAP.keys()])
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(
                        text=f"❓ ไม่พบสาขา '{keyword}'\n\nสาขาที่มี:\n{branch_list}"
                    )]
                )
            )
            return

        # แจ้งว่ากำลังแคป
        # line_bot_api.reply_message(
        #     ReplyMessageRequest(
        #         reply_token=reply_token,
        #         messages=[TextMessage(text=f"⏳ กำลังแคปรูปสาขา '{keyword}' ...")]
        #     )
        # )

    # แคปรูปใน thread แยก
    def do_capture():
        target_url = BRANCH_MAP[keyword]
        filename   = capture_screenshot(target_url)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            if filename and BASE_URL:
                # ✅ ส่งรูปกลับ Line
                image_url = f"{BASE_URL}/image/{filename}"
                print(f"🔗 Image URL: {image_url}")

                line_bot_api.push_message(
                    PushMessageRequest(
                        to=target_id,
                        messages=[
                            ImageMessage(
                                original_content_url=image_url,
                                preview_image_url=image_url,
                            )
                        ]
                    )
                )
            elif filename and not BASE_URL:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=target_id,
                        messages=[TextMessage(
                            text="✅ แคปรูปสำเร็จ แต่ยังไม่ได้ตั้ง BASE_URL ใน .env\n"
                                 "กรุณาเพิ่ม BASE_URL=https://xxxx.ngrok-free.app"
                        )]
                    )
                )
            else:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=target_id,
                        messages=[TextMessage(text=f"❌ แคปรูปสาขา '{keyword}' ล้มเหลว")]
                    )
                )

    threading.Thread(target=do_capture).start()

# ==============================
# Run
# ==============================
if __name__ == "__main__":
    print("🤖 Line Bot พร้อมทำงาน!")
    print(f"   BASE_URL    : {BASE_URL or '⚠️  ยังไม่ได้ตั้งค่า'}")
    print(f"   สาขาที่รองรับ: {list(BRANCH_MAP.keys())}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)

