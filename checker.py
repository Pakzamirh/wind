import os
import socket
import requests

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
ZONE_ID = os.environ.get("CF_ZONE_ID")
RECORD_NAME = "wind.irantrade.tech"

def check_ikev2(ip, port=500, timeout=1.5):
    """تست واقعی ارسال و دریافت پکت IKEv2 روی پورت UDP 500"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        ike_packet = (
            b'\x01\x02\x03\x04\x05\x06\x07\x08'
            b'\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x21\x20\x22\x08'
            b'\x00\x00\x00\x00'
            b'\x00\x00\x00\x1c'
        )
        
        sock.sendto(ike_packet, (ip, port))
        data, _ = sock.recvfrom(1024)
        sock.close()
        return len(data) > 0
    except Exception:
        return False

def get_record_id(headers):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?name={RECORD_NAME}&type=A"
    try:
        res = requests.get(url, headers=headers).json()
        if res.get("success") and res.get("result"):
            return res["result"][0]["id"]
    except Exception as e:
        print(f"خطا در دریافت رکورد: {e}")
    return None

def update_cloudflare_dns(ip_address):
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
        "proxied": False
    }
    
    if record_id:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{record_id}"
        requests.put(url, json=payload, headers=headers)
    else:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
        requests.post(url, json=payload, headers=headers)

# اسکن کامل تمام ۲۵۵ آی‌پی
healthy_ips = []
print(f"شروع اسکن کامل تمام ۲۵۵ آی‌پی برای {RECORD_NAME}...")

for i in range(1, 256):
    ip = f"135.136.0.{i}"
    if check_ikev2(ip):
        print(f"[+] آی‌پی سالم پیدا شد: {ip}")
        healthy_ips.append(ip)

# ۱. ذخیره لیست کامل آی‌پی‌های سالم در فایل متنی
with open("healthy_ips.txt", "w") as f:
    for ip in healthy_ips:
        f.write(f"{ip}\n")

print(f"تعداد {len(healthy_ips)} آی‌پی سالم در فایل healthy_ips.txt ذخیره شد.")

# ۲. آپدیت کلادفلر با اولین آی‌پی سالم لیست
if healthy_ips:
    update_cloudflare_dns(healthy_ips[0])
    print(f"[✔] دامنه کلادفلر روی {healthy_ips[0]} تنظیم شد.")
else:
    print("[-] هیچ آی‌پی پاسخی ارسال نکرد.")
