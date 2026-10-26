# בדיקת מקורות — 26.10.2026 (עודכן)

- ועדת הבחירות: https://www.bechirot.gov.il/home/ והעמוד הרשמי https://www.gov.il/he/departments/dynamiccollectors/election-timeline26 מציגים את 27.10.2026 כתאריך הבחירות.
- אתר התוצאות https://cdn-votes26.bechirot.gov.il/cityresults?lang=he הופיע בחיפוש עם הכיתוב „סביבת בדיקות”. אין להשתמש בו להזנת אמת בלי אימות מחדש. תוצאות ספירת קולות אינן בהכרח דיווח השתתפות במהלך היום.
- **GovMap (נתיב מוכן בקוד):** תבנית הקבצים בקוד המפה היא  
  `/data/votes/{N}/municipal_data.json` ו־`neighborhood_data.json`.  
  כנסות 24 ו־25 זמינות עם שדות `בזב` / `מצביעים` / `שם ישוב` ומפתח = סמל יישוב.  
  נתיב 26 עדיין לא הופיע בעת הבדיקה; `scripts/watch_govmap.py` בודק פתיחה.  
  מתאם: `scripts/adapt_govmap.py` → סכמת `live-turnout.json`. מיפוי יישובים ב־`scripts/city_codes.json`.
- קטלוג: https://elections.govmap.gov.il/data/votes/elections.json — בעת הבדיקה רק 24 ו־25.
- מפת ynet / ניר סמילגה: ייחוסי „לשכת הבחירות” ו„הלמ״ס” הם attribution היסטורי; הנתונים מוגשים דרך API מוגן. **לא לשימוש כפיד.**
- במהלך יום הבחירות הוועדה מפרסמת בעיקר אחוז ארצי (לעיתים מדגם למ״ס לפי שעה). פירוט לפי יישוב עשוי להגיע מאוחר יותר או אחרי סגירה.

מסקנה: מקור היעד לפיד יישובים הוא GovMap `municipal_data` לכנסת 26, לאחר אימות ידני ביום הבחירות. עד אז ההזנה נשארת נעולה (`OFFICIAL_FEED_VERIFIED`).
