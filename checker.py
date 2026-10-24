import os
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
ZONE_ID = os.environ.get("CF_ZONE_ID")
RECORD_NAME = "wind.irantrade.tech"

def check_ikev2(ip, port=500, timeout=0.8):
    """تست سریع ارسال و دریافت پکت IKEv2 روی پورت UDP 500"""
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
    if check_ikev2(ip):
        return ip
    return None

def resolve_domain(domain):
    try:
        return socket.gethostbyname(domain.strip())
    except Exception:
        return None

def get_record_id(headers):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?name={RECORD_NAME}&type=A"
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
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
    try:
        if record_id:
            url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{record_id}"
            requests.put(url, json=payload, headers=headers, timeout=10)
        else:
            url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
            requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"خطا در آپدیت کلادفلر: {e}")

# خواندن لیست دامنه‌ها
domain_file = "domain.txt" if os.path.exists("domain.txt") else ("domain" if os.path.exists("domain") else None)

if not domain_file:
    print("[-] فایل domain.txt یافت نشد.")
    exit(1)

with open(domain_file, "r") as f:
    domains = [line.strip() for line in f if line.strip() and not line.startswith("#")]

os.makedirs("results", exist_ok=True)
first_healthy_ip = None

print(f"شروع اسکن بهینه‌شده برای {len(domains)} دامنه...")

for domain in domains:
    print(f"\n[+] اسکن دامنه: {domain}")
    main_ip = resolve_domain(domain)
    
    if not main_ip:
        print(f"[✖] عدم امکان دریافت آی‌پی برای {domain}")
        continue
        
    prefix = ".".join(main_ip.split(".")[:3])
    ips_to_scan = [f"{prefix}.{i}" for i in range(1, 256)]
    domain_healthy_ips = []
    
    # اسکن موازی سریع با ۵۰ نخ هم‌زمان
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(scan_ip, ip) for ip in ips_to_scan]
        for future in as_completed(futures):
            res = future.result()
            if res:
                domain_healthy_ips.append(res)
                if not first_healthy_ip:
                    first_healthy_ip = res
                
    # ذخیره فایل نتایج دامنه
    file_path = os.path.join("results", f"{domain}.txt")
    with open(file_path, "w") as f:
        for ip in sorted(domain_healthy_ips):
            f.write(f"{ip}\n")
            
    print(f"[✔] {len(domain_healthy_ips)} آی‌پی سالم ذخیره شد.")

# آپدیت کلادفلر
if first_healthy_ip:
    update_cloudflare_dns(first_healthy_ip)
    print(f"\n[✔] دامنه اصلی {RECORD_NAME} روی آی‌پی {first_healthy_ip} ست شد.")
