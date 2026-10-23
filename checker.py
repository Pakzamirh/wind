import os
import socket
import requests

# دریافت توکن‌ها از Secrets گیتهاب
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
ZONE_ID = os.environ.get("CF_ZONE_ID")

# تنظیم نام ساب‌دامنه مقصد
RECORD_NAME = "wind.irantrade.tech"

def check_ikev2(ip, port=500, timeout=1.5):
    """تست باز بودن پورت UDP 500 برای IKEv2"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        # ارسال پکت اولیه IKEv2 Header
        sock.sendto(b'\x00' * 28, (ip, port))
        sock.close()
        return True
    except Exception:
        return False

def get_record_id(headers):
    """دریافت ID رکورد DNS فعلی از کلادفلر"""
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?name={RECORD_NAME}&type=A"
    try:
        res = requests.get(url, headers=headers).json()
        if res.get("success") and res.get("result"):
            return res["result"][0]["id"]
    except Exception as e:
        print(f"خطا در دریافت رکورد: {e}")
    return None

def update_cloudflare_dns(ip_address):
    """به‌روزرسانی یا ایجاد رکورد DNS در کلادفلر"""
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    record_id = get_record_id(headers)
    payload = {
        "type": "A",
        "name": RECORD_NAME,
        "content": ip_address,
        "ttl": 1,
        "proxied": False  # حالت DNS Only (ابر خاکستری)
    }
    
    if record_id:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{record_id}"
        res = requests.put(url, json=payload, headers=headers).json()
    else:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
        res = requests.post(url, json=payload, headers=headers).json()
        
    if res.get("success"):
        print(f"[✔] رکورد {RECORD_NAME} با موفقیت روی آی‌پی {ip_address} ست شد.")
    else:
        print(f"[✖] خطا در به‌روزرسانی کلادفلر: {res.get('errors')}")

# شروع اسکن آی‌پی‌های رنج 135.136.0.1 تا 135.136.0.255
healthy_ip = None
print(f"شروع اسکن آی‌پی‌های رنج 135.136.0.1 تا 135.136.0.255 برای دامنه {RECORD_NAME}...")

for i in range(1, 256):
    ip = f"135.136.0.{i}"
    if check_ikev2(ip):
        print(f"[+] آی‌پی سالم پیدا شد: {ip}")
        healthy_ip = ip
        break

if healthy_ip:
    update_cloudflare_dns(healthy_ip)
else:
    print("[-] هیچ آی‌پی سالمی در این رنج پیدا نشد.")
