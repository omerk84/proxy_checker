# ⚡ Proxy Scraper & Speed Checker

כלי אסינכרוני מתקדם, מדויק ומהיר ביותר לאיסוף (Scraping), בדיקת תקינות, סיווג אנונימיות ומדידת זמן תגובה (MS Latency) עבור פרוקסים מסוג:
- **HTTP / HTTPS**
- **SOCKS4**
- **SOCKS5**

---

## 🌐 פורטלי Web ומקורות יומיים עם Pagination מלא (ללא זבל ומתים)

המערכת שואבת במקביל מעשרות פורטלים חיים ומקורות מנוטרים בזמן אמת, כולל **תמיכה בריבוי עמודים (Full Multi-Page Pagination)** ובשילוב מנועי חילוץ ו-Reverse-Engineering ייעודיים:

1. **ProxyCompass.com (Live Multi-Page API & Real-Time Portal)**:
   - חילוץ ישיר מתוך ממשק ה-API הפנימי של האתר (`/api/v1/free-proxies/live`).
   - תמיכה מלאה בסינון לפי פרוטוקול (`protocol=socks5/socks4/http`), פגינציה רב-עמודית (`page=1, 2, 3`), וסינון לפי מדד זמני תגובה (`latency`).
   - תוצאה אמפירית: **100% שרידות חיים** ברמת Socket ופינג ממוצע יוצא דופן של **217ms**!
2. **Free-Proxy-List Network (Free-Proxy-List.net, Socks-Proxy.net, SSLProxies.org, US-Proxy.org, UK-Proxy, Anon-Proxy)**:
   - פורטלים חיים מתעדכנים כל 10 דקות הכוללים מאות שרתי SOCKS4/5 ו-HTTP/SSL מאומתים.
3. **FreeProxy.World (Multi-Page Portal)**:
   - חילוץ טבלאי מלא בעמודים 1, 2 ו-3 (`page=1`, `page=2`, `page=3`) עבור SOCKS5, SOCKS4, ו-HTTP.
   - תוצאה אמפירית: **80.0% שרידות חיים** ברמת Socket!
4. **ProxyDB.net (Multi-Page Decoy-Bypassed Portal)**:
   - תמיכה מלאה בהיסטים מרובים (`offset=0`, `offset=30`, `offset=60`).
   - עוקף לחלוטין את מלכודות ה-DOM המוסתרות (`<div style="display:none">`) ומפיק 30 פרוקסים איכותיים לכל עמוד.
5. **Proxy-List.org (Multi-Page Base64 Portal)**:
   - סריקת 5 עמודים מלאים (`p=1`, `p=2`, `p=3`, `p=4`, `p=5`).
   - פענוח אוטומטי של קריאות JavaScript מוצפנות ב-Base64 (`Proxy('...')`).
6. **Advanced.Name (Multi-Page Obfuscated Portal)**:
   - סריקת עמודים 1 ו-2 (`page=1`, `page=2`) עם פענוח מאפייני `data-ip` ו-`data-port` המוצפנים ב-Base64.
7. **Geonode Public REST API (Multi-Page Paginated API)**:
   - תמיכה בעמודים 1 ו-2 (`page=1`, `page=2`) עם `limit=100` ומיון לפי `lastChecked`.
   - שיעור שרידות: **40.0%**, זמן תגובה ממוצע 290ms.
8. **Proxy-Daily.com (Real-Time Export & DataTables API)**:
   - ממשק ישיר לייצוא פרוקסים מנוטרים המתעדכנים כל 5 דקות (`/api/export_proxies_ip_port`).
   - שיעור שרידות: **43.5%**, זמן תגובה ממוצע 242ms.
9. **Spys.One & Spys.Me (Authority Direct Feeds)**:
   - פיד ה-Authority של מנהל האתר Spys (`socks.txt`, `proxy.txt`) ופורטל ה-XOR של Spys.one עם ביצועי מפתח (חישוב ב-Bitwise תוך <5ms).
10. **My-Proxy.com (Categorized Dedicated Lists)**:
    - חילוץ ישיר של דפי קטגוריות (`free-socks-5-proxy.html`, `free-socks-4-proxy.html`, `free-elite-proxy.html`).
    - שיעור שרידות: **52.0%**.
11. **Monosans/Proxy-List (Hourly Latency-Sorted Feed)**:
    - מאגר מנוטר ברמת Rust, מתעדכן בכל שעה וממוין מראש לפי Latency.
    - שיעור שרידות: **56.0%**.
12. **ProxyScrape API v2 (Live Free API)**:
    - חיבור ישיר לפידי ה-API החיים של ProxyScrape.
    - שיעור שרידות: **68.0%**, זמן תגובה ממוצע 207ms.
13. **Tier-1 Health-Checked Feeds**:
    - פידים מנוטרים בזמן אמת (`xyzs996` עם 86.7% שרידות, `rdavydov`, `ClearProxy`, `hproxy-com`).

---


## 🔬 מנגנון הבדיקה המתקדם (Smart Checker Architecture)

1. **Smart Fast-Fail (ללא Retries מבוזבזים על שקעים מתים)**:
   - אם הפרוקסי נכשל בחיבור הרשת הבסיסי (`ConnectionRefused`, `Timeout`, פורט סגור) – **הוא נפסל מיידית ב-0 שניות ללא כל ניסיון חוזר**. זה חוסך עשרות אלפי בקשות סרק ומכפיל את מהירות הבדיקה.
2. **Targeted Failover (גיבוי יעד בלבד)**:
   - רק אם החיבור לפרוקסי הצליח, אך שרת ה-Echo הראשי (`api.ipify.org`) החזיר שגיאת עומס 429 או 503 – רק אז מתבצע מעבר מהיר לשרת הגיבוי (`icanhazip.com`).
3. **זיהוי רמת אנונימיות ומניעת דליפות (Anti-Leak & Anonymity)**:
   - זיהוי אוטומטי של רמת אנונימיות (**ELITE** לעומת **ANONYMOUS**) ווידוא מלא שכתובת ה-IP הביתית לא נחשפת.
4. **סיום מוקדם בלחיצת מקש (Early Finish)**:
   - בכל שלב במהלך ה-Scraping או ה-Checking, ניתן ללחוץ על **`f`** (Finish), **`q`** (Quit), **`Enter`** או **`Ctrl+C`**.
   - המערכת לא קורסת, אלא עוצרת בצורה חלקה, שומרת את כל הפרוקסים שנאספו או נבדקו עד אותו רגע, וממשיכה מיד לשלב הבא!
5. **שמירה נקייה לקובץ יחיד (Single Clean Output File)**:
   - בתיקיית `output/` נוצר **קובץ יחיד בלבד** עבור הפרוטוקול שנבחר: `{protocol}_working.txt` (לדוגמה `socks4_working.txt`).
   - הקובץ מכיל אך ורק את כל הפרוקסים התקינים שעמדו בדרישות הסינון בריצה (כגון מתחת ל-800ms), ממוינים מהמהיר לאיטי.


---


## 💻 הפעלה

### הרצה מהירה (Windows):
לחץ פעמיים על:
```cmd
run.bat
```

### הרצה ישירה בטרמינל:
```powershell
.\.venv\Scripts\python.exe main.py
```
