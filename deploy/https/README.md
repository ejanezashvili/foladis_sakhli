# HTTPS და ტელეფონი (8.7 / 4.7) - ჩართვის ინსტრუქცია

ახლა: Odoo პირდაპირ `192.168.13.13:8069`-ზეა, გარე `http://146.255.249.126` ოფისის როუტერიდან გადმოდის (80 → 8069).
HTTPS-ის გარეშე ტელეფონზე არ მუშაობს: push შეტყობინებები და „Add to Home Screen“ აპლიკაციის სახით.
ინტერფეისი ტელეფონზე უკვე მორგებულია (`steelhouse_task_flow/static/src/mobile`).

## 1. კომპანიისგან (ერთხელ)
1. **დომენი**, მაგ. `tasks.poladissakhli.ge`: DNS-ში A ჩანაწერი → `146.255.249.126`.
2. **ქსელის ადმინი, როუტერზე:** გარე პორტები **80 და 443** → `192.168.13.13` პორტები **80 და 443**
   (ახლანდელი 80 → 8069 გადამისამართება შეიცვლება).

## 2. სერვერზე (ჩვენ, ~1 საათი; ბაზის ასლი ჯერ - `sudo steelhouse_backup.sh`)
```sh
sudo apt install -y nginx certbot python3-certbot-nginx
sudo cp steelhouse.nginx.conf /etc/nginx/sites-available/steelhouse
sudo sed -i 's/DOMAIN/tasks.poladissakhli.ge/g' /etc/nginx/sites-available/steelhouse
# ჯერ მხოლოდ 80 (სერტიფიკატამდე 443-ის ბლოკი დროებით გამოთიშული), მერე:
sudo certbot --nginx -d tasks.poladissakhli.ge      # სერტიფიკატი + ავტომატური განახლება (systemd timer)
sudo ln -s /etc/nginx/sites-available/steelhouse /etc/nginx/sites-enabled/ && sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```
`/etc/odoo/odoo.conf`:
```
proxy_mode = True
```
`sudo systemctl restart odoo`, მერე Odoo-ში (პარამეტრები → ტექნიკური → სისტემის პარამეტრები):
- `web.base.url` = `https://tasks.poladissakhli.ge`, `web.base.url.freeze` = `True`
- PDF-ისთვის `report.url` = `http://127.0.0.1:8069` რჩება (wkhtmltopdf შიგნიდან).
- `web.web_app_name` = `ფოლადის სახლი` - ტელეფონის ეკრანზე ხატულას ქვეშ ეს სახელი ეწერება (ნაგულისხმევად „Odoo“;
  `web/controllers/webmanifest.py`). ხატულა თავად Odoo-ს ლოგოა - კომპანიის ლოგოსთვის `/web/manifest.webmanifest`-ის
  `icons` უნდა გადაიფაროს ჩვენს მოდულში (192 და 512 px PNG).

8069 გარედან აღარ უნდა ჩანდეს (მხოლოდ nginx): `sudo ufw allow 80,443/tcp` + 22 ოფისიდან / VPN-დან.

## 3. შემოწმება
- `https://DOMAIN` იხსნება, ბრაუზერში კლიტე 🔒; `http://` → `https://`.
- ჩატი / შეტყობინებები ცოცხლად მოდის (websocket `/websocket`).
- **ტელეფონი:** Chrome → ⋮ → „Install app“ / Safari → Share → „Add to Home Screen“ - Odoo-ს ხატულა ეკრანზე,
  იხსნება ბრაუზერის ზოლის გარეშე.
- **push:** პირველ შესვლაზე ბრაუზერი ითხოვს ნებართვას შეტყობინებებზე - „დაშვება“; ახალი დავალება /
  შვებულების მოთხოვნა ტელეფონზე შეტყობინებად მოდის (Odoo Community-ის web push, `mail`).
- PDF (შვებულების რეპორტი, დავალებების რეპორტები) ისევ სტილით იბეჭდება.

## უკან დაბრუნება
`sudo rm /etc/nginx/sites-enabled/steelhouse && sudo systemctl stop nginx`, `proxy_mode` წაშლა, `web.base.url` ძველი,
როუტერზე 80 → 8069.
