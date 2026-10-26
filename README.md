# דשבורד השתתפות בבחירות

האתר הראשי הוא `index.html`. נשמרו כל 50 היישובים שבמקור: 44 נבחרים בחמש קבוצות ושישה חלופיים. כל נתוני העבר, הגרפים, הסימולציות, בחירת היישובים, ייבוא, יצוא והדפסה נשמרו. נתוני העבר הם טיוטת המחקר המקורית ולא אומתו מחדש במסגרת ההקמה.

המדד: אחוז ההשתתפות הנוכחי חלקי אחוז ההשתתפות הסופי ב־2022, כפול 100. הפער הוא מול המדד הארצי באותו מועד. בקבוצות משתמשים בסך מצביעים חלקי סך זכאים; כשחסר דיווח מלא אין מדד קבוצתי מלא.

## שימוש

`live-turnout.json` מתחיל ללא רשומות וללא שיעור ארצי. הדגמות מופעלות רק בלחיצה ומסומנות כהדגמה. הכפתור „יציאה מהדגמה / חזרה לעדכונים” מנקה נתונים מקומיים וחוזר לקובץ הציבורי. בנתונים חיים הדפדפן בודק עדכונים כל שתי דקות, עם עקיפת מטמון. הדגמה או קובץ שיובא מקומית נשארים בתצוגה עד לחזרה לעדכונים; הם לא משנים את האתר עבור אחרים.

## פרסום ב־GitHub Pages

במאגר `6725838-blip/election-turnout-2026`, בוחרים Settings → Pages → Source → GitHub Actions.
כל push לענף `main` מפעיל את `.github/workflows/election_deploy.yml`: בדיקות, אריזת קובצי האתר והנתונים, ופרסום משותף. רק `index.html`, `live-turnout.json` ו־`.nojekyll` נכללים באתר הציבורי.

גם כשסקריפט העדכון שומר commit באמצעות `GITHUB_TOKEN`, אותה הרצה ממשיכה לפרסום; אין הסתמכות על הפעלת workflow נוספת. לאחר סיום Actions ייתכן עיכוב של מספר דקות בהפצת Pages, ועוד עד שתי דקות עד לרענון הדפדפן. כפתור „בדוק עכשיו” מרענן מיד.

לאחר כל פרסום הרצת Actions מורידה את ה־HTML ואת קובץ הנתונים מהכתובת הציבורית ומוודאת שהם זהים לקבצים שפורסמו. הבדיקה חוזרת במהלך הפצת Pages ונכשלת אם הגרסה הציבורית לא התעדכנה. כך נבדק שהעדכון הגיע לאתר עצמו.

## חיבור עתידי לנתוני אמת — כבוי

תזמון Actions מוגדר ל־27.10.2026, כל 20 דקות בשעות 07:07–23:47 לפי שעון ישראל (בדקות 07, 27, 47). בלי `OFFICIAL_FEED_VERIFIED=true` לא נשלחת בקשה למקור ואין פרסום של נתונים מומצאים.

הנתיב המוכן לפיד יישובים הוא **GovMap** (`municipal_data.json`), דרך מתאם ב־`scripts/adapt_govmap.py`. כל הרצה מתוזמנת גם מדווחת אם פיד כנסת 26 זמין (`scripts/watch_govmap.py`) — בלי להדליק אימות אוטומטית. מפות ynet / מקורות צד־שלישי אינם בשימוש.

### Runbook בוקר בחירות

1. `python scripts/watch_govmap.py` עד ש־`ready` הוא true.
2. הורדה ידנית של `municipal_data.json` ובדיקת 2–3 יישובים מול הבסיס.
3. הגדרת Repository Variables ואז Actions → Run workflow עם `refresh_verified_feed`.
4. אם יש רק אחוז ארצי מהוועדה — הזנה ב־«אחוז ארצי ידני» או JSON עם `national_turnout_pct` ו־`records: []`.

Repository Variables לאחר אימות:

- `OFFICIAL_FEED_VERIFIED`: `true` רק לאחר אימות.
- `OFFICIAL_FEED_URL`: למשל `https://elections.govmap.gov.il/data/votes/26/municipal_data.json` (HTTPS, בלי סיסמאות).
- `OFFICIAL_FEED_FORMAT`: `govmap_municipal` לפיד GovMap, או `live` אם ה־URL כבר בסכמת `live-turnout.json`.
- `ELECTION_DATE`: `2026-10-27`.

שגיאת מקור, ערכים לא תקינים או snapshot ישן מפסיקים את הפרסום ושומרים את הגרסה הקודמת. דיווח יישוב חסר, ישן או חלקי במקום דיווח מלא נשמר עם שעתו המקורית וסימון דיווח קודם.

## בדיקה ציבורית מקצה לקצה

Actions → Public end-to-end demo cycle → Run workflow מפעיל בדיקה יזומה. ההדגמה נמצאת רק ב־`test/live-turnout.json` ובנתיב האתר `/test/`, שמסומן תמיד בבאנר אזהרה. הנתיב החי חוסם הזנת הדגמה; הבדיקה משווה גם טביעת SHA256 של קובץ האמת כדי לוודא שלא השתנה.

ההרצה שומרת ב־main שתי גרסאות עם מספרים שונים, מפרסמת כל אחת באותה הרצה, משווה את קובצי ה־JSON הציבוריים, ומשאירה דפדפן Chromium פתוח בין הפרסומים. הדפדפן ממתין לרענון האמיתי של שתי דקות, בודק את כל 44 היישובים וחמש הקבוצות, ומתעד שלא התבצעה טעינת דף נוספת. בסיום נשמר snapshot בדיקה ריק ומתפרסם גם אם שלב בדיקה נכשל. צילומי מסך ודוח נשמרים ב־artifact בשם `public-browser-evidence` לשבעה ימים.

הרשאות: עבודת העדכון מקבלת רק `contents: write`; עבודת הפרסום מקבלת `contents: read`, `pages: write`, `id-token: write` ללא אישורי Git שמורים. בדיקת הקצה דורשת את הרשאות הכתיבה והפרסום כדי לשמור ולפרסם את שתי הגרסאות ולנקותן. לא נשמרים בקוד אסימוני גישה.

סכמה: `format_version: 1`, תיאור `source`, חותמת זמן `updated_at` עם אזור זמן, `national_turnout_pct` או null, ומערך `records`. כל רשומה דורשת `city` ו־`turnout_pct` או `eligible` ו־`voted`; לחישוב קבוצתי נדרשים שני המונים. `partial: true` או מספר קלפיות מדווחות קטן מהסך מסמנים דיווח חלקי. אפשר לצרף `as_of` עם אזור זמן. כאשר קיימים גם מונים וגם אחוז, הם חייבים להתאים. Snapshot ריק נשאר עם null וללא מספרים מומצאים.

## בדיקות מקומיות

```sh
python -m unittest discover -s tests
node tests/dashboard.test.cjs
python scripts/validate_live.py live-turnout.json
python scripts/watch_govmap.py
python scripts/adapt_govmap.py --fixture-from-25 --updated-at 2026-10-27T12:00:00+02:00 --out /tmp/live-from-25.json
python scripts/validate_live.py /tmp/live-from-25.json
python scripts/prepare_site.py
python -m http.server 8766 --bind 127.0.0.1
```

סנכרון קודי יישוב / בסיס 2022 מול GovMap 25: `python scripts/sync_baseline_codes.py --update-stats`.

פותחים `http://127.0.0.1:8766/index.html`. קובצי הבדיקה משתמשים בנתונים סינתטיים בזיכרון בלבד, ולא משנים את קובץ ההצבעה הציבורי.

הגיבויים המקומיים נמצאים ב־`original-backup/` ואינם מועלים. הקבצים `election_deploy.yml` ו־`update_live.py` בשורש נשמרו לתאימות; הקבצים הפעילים נמצאים תחת `.github/workflows/` ו־`scripts/`.
