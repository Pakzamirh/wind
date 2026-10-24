import os
import socket
import requests
from concurrent.futures import ThreadPoolExecutor

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
ZONE_ID = os.environ.get("CF_ZONE_ID")
RECORD_NAME = "wind.irantrade.tech"

def check_ikev2(ip, port=500, timeout=1.5):
    """تست ارسال و دریافت پکت IKEv2 روی پورت UDP 500"""
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

def scan_ip(ip):
    """تابع اسکن موازی آی‌پی"""
    if check_ikev2(ip):
        return ip
    return None

def resolve_domain(domain):
    """دریافت آی‌پی اصلی دامنه"""
    try:
        return socket.gethostbyname(domain.strip())
    except Exception:
        return None

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

# خواندن لیست دامنه‌ها
domain_file = "domain.txt" if os.path.exists("domain.txt") else ("domain" if os.path.exists("domain") else None)

if not domain_file:
    print("[-] فایل domain.txt یافت نشد.")
    exit(1)

with open(domain_file, "r") as f:
    domains = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# ساخت پوشه اختصاصی results
os.makedirs("results", exist_ok=True)

first_healthy_ip = None

for domain in domains:
    print(f"\n[+] در حال اسکن دامنه: {domain}")
    main_ip = resolve_domain(domain)
    
    if not main_ip:
        print(f"[✖] دامنه {domain} به آی‌پی تبدیل نشد.")
        continue
        
    prefix = ".".join(main_ip.split(".")[:3])
    ips_to_scan = [f"{prefix}.{i}" for i in range(1, 256)]
    domain_healthy_ips = []
    
    # اسکن موازی ۲۵۵ آی‌پی رنج
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(scan_ip, ips_to_scan)
        for res in results:
            if res:
                domain_healthy_ips.append(res)
                if not first_healthy_ip:
                    first_healthy_ip = res
                
    # ذخیره آی‌پی‌های مجزا فقط برای همین دامنه
    file_path = os.path.join("results", f"{domain}.txt")
    with open(file_path, "w") as f:
        for ip in domain_healthy_ips:
            f.write(f"{ip}\n")
            
    print(f"[✔] تعداد {len(domain_healthy_ips)} آی‌پی سالم در فایل results/{domain}.txt ذخیره شد.")

# آپدیت کلادفلر جهت فعال ماندن wind.irantrade.tech
if first_healthy_ip:
    update_cloudflare_dns(first_healthy_ip)
    print(f"\n[✔] دامنه اصلی {RECORD_NAME} روی آی‌پی {first_healthy_ip} ست شد.")
