import os
import socket
import requests

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
ZONE_ID = os.environ.get("CF_ZONE_ID")
RECORD_NAME = "wind.irantrade.tech"

def check_ikev2(ip, port=500, timeout=2.0):
    """تست واقعی ارسال و دریافت پکت IKEv2 روی پورت UDP 500"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # ساخت یک هدر معتبر IKE_SA_INIT جهت دریافت پاسخ از سرور
        ike_packet = (
            b'\x01\x02\x03\x04\x05\x06\x07\x08'  # Initiator SPI
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Responder SPI
            b'\x21\x20\x22\x08'                  # Next Payload, Ver 2.0, Exchange IKE_SA_INIT
            b'\x00\x00\x00\x00'                  # Message ID
            b'\x00\x00\x00\x1c'                  # Length 28
        )
        
        sock.sendto(ike_packet, (ip, port))
        data, _ = sock.recvfrom(1024)  # انتظار برای دریافت پاسخ واقعی از سرور
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
        res = requests.put(url, json=payload, headers=headers).json()
    else:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
        res = requests.post(url, json=payload, headers=headers).json()
        
    if res.get("success"):
        print(f"[✔] رکورد {RECORD_NAME} با موفقیت روی آی‌پی {ip_address} ست شد.")
    else:
        print(f"[✖] خطا در به‌روزرسانی کلادفلر: {res.get('errors')}")

# اسکن رنج آی‌پی
healthy_ip = None
print(f"شروع اسکن واقعی آی‌پی‌ها برای {RECORD_NAME}...")

for i in range(1, 256):
    ip = f"135.136.0.{i}"
    if check_ikev2(ip):
        print(f"[+] آی‌پی پاسخ‌دهنده و سالم پیدا شد: {ip}")
        healthy_ip = ip
        break

if healthy_ip:
    update_cloudflare_dns(healthy_ip)
else:
    print("[-] هیچ آی‌پی پاسخی ارسال نکرد.")
