# תחרות התחזיות — שמירה במאגר GitHub (בלי התחברות למשתתפים)

הממשק הציבורי הוא [`../forecast.html`](../forecast.html) ב־GitHub Pages.  
המשתתפים ממלאים שם + תחזית **בלי** חשבון Google או GitHub.

## איך זה עובד

| פעולה | איך |
|--------|-----|
| הגשת תחזית | הדפדפן שולח `repository_dispatch` ל־GitHub API |
| אימות + שמירה | Actions → קובץ ב־`forecasts/submissions/` |
| הצגה באתר | `forecasts-public.json` (אותו דומיין) |
| דירוג אחרי האמת | ממלאים `forecasts/truth.json` ומעלים commit |

## הגדרה חד־פעמית (רק בעל המאגר)

1. ב־GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate**.
2. Repository access: רק המאגר הזה.
3. Permissions → Repository permissions → **Contents: Read-only**.
4. העתיקו את הטוקן.
5. במאגר: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `FORECAST_DISPATCH_TOKEN`
   - Value: הטוקן
6. הריצו את ה־workflow **Update and deploy election turnout dashboard** (או דחפו commit קטן) כדי לפרוס מחדש את `forecast.html` עם הטוקן מוזרק.

אחרי הפריסה: פתחו `/forecast.html`, מלאו תחזית תקינה ולחצו «בדיקה והגשת התחזית». תוך דקה־שלוש היא תופיע ברשימה הציבורית.

## קבצים חשובים

- `forecasts/submissions/*.json` — כל הגשה תקינה
- `forecasts/truth.json` — תוצאות אמת (null עד שממלאים מספרים שסכומם 120)
- `forecasts-public.json` — העתק ציבורי לאתר
- `scripts/forecast_contest.py` / `accept_forecast.py` / `rebuild_forecasts.py`

## פרטיות ואבטחה

- אל תשמרו PAT בגיט. בסורס יש רק `__FORECAST_DISPATCH_TOKEN__`; ההזרקה קורית בפריסה ל־`_site`.
- הטוקן שמופיע ב־JS הציבורי מיועד לקריאה בלבד + שליחת `repository_dispatch`. הוא לא נותן דחיפת קוד.
- כינוי כפול נדחה בשרת. אחרי מועד הסגירה הגשות חדשות לא נשמרות.

## נטפרי

ההגשה עוברת דרך `api.github.com`. אם הרשת חוסמת את ה־API — ההגשה תיכשל (תוצג הודעה). קריאת הרשימה הציבורית נשארת מ־`github.io` בלבד.
