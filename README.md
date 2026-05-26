automated line screenshot 
สร้างโปรแกรมสำหรับดึงรูปภาพหน้าจอตาม url ที่กำหนด  แล้วส่งไปยัง line notify โดยจะมีฟังก์ชันเปรียบเทียบ url ว่าตรงกับ url ที่คาดหวังหรือไม่ ถ้าไม่ตรงจะส่งการแจ้งเตือนไปยัง line ตามค่าที่ตั้งไว้ใน .env

## 1. ติดตั้ง Library ที่จำเป็น

```bash
pip install requests Pillow pyautogui schedule
playwright install
pip3 install flask line-bot-sdk playwright python-dotenv

```
