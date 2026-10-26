/**
 * תחרות תחזיות שיתופית — מאגר Google Sheets פרטי + Google Form לכתיבה (נטפרי).
 *
 * זרימה:
 * 1) מריצים setupContest פעם אחת (יוצר גיליון + טופס, מדפיס FORM_CONFIG).
 * 2) מריצים installFormTrigger פעם אחת (onFormSubmit).
 * 3) Deploy > New deployment > Web app: Execute as Me, Who has access: Anyone.
 *    ה־doGet מחזיר JSON ציבורי בלבד עבור GitHub Actions (לא לדפדפן של המשתתפים).
 * 4) מדביקים את FORM_CONFIG ב־forecast.html ומגדירים FORECAST_EXPORT_URL ב־GitHub Secrets.
 */
const APP_CONFIG = {
  title: 'תחרות התחזיות השיתופית — בחירות 2026',
  // מועד הסגירה המקורי של תחרות התחזיות. לשינוי המועד, עדכנו כאן לפני הפרסום.
  cutoffIso: '2026-10-27T07:00:00+02:00',
  parties: [
    {id:'likud', name:'הליכוד', bloc:'right'},
    {id:'otzma', name:'עוצמה יהודית', bloc:'right'},
    {id:'tzionut', name:'הציונות הדתית', bloc:'right'},
    {id:'shas', name:'ש״ס', bloc:'right'},
    {id:'utj', name:'יהדות התורה', bloc:'right'},
    {id:'winter', name:'עמך ישראל (וינטר)', bloc:'right'},
    {id:'bennett', name:'ביחד (בנט ויש עתיד)', bloc:'center'},
    {id:'yashar', name:'ישר (אייזנקוט)', bloc:'center'},
    {id:'democrats', name:'הדמוקרטים', bloc:'center'},
    {id:'liberman', name:'ישראל ביתנו', bloc:'center'},
    {id:'zalicha', name:'המילואימניקים והכלכלית (הנדל–זליכה)', bloc:'center'},
    {id:'raam', name:'רע״מ', bloc:'arab'},
    {id:'joint', name:'המשותפת (חד״ש–תע״ל–בל״ד)', bloc:'arab'}
  ],
  blocs: [
    {id:'right', name:'ימין (כולל החרדים)'},
    {id:'center', name:'מרכז־שמאל'},
    {id:'arab', name:'ערבים'}
  ]
};

/** JSON export for CI only — not the contest UI (UI lives on GitHub Pages). */
function doGet() {
  const payload = getPublicForecasts();
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Run once from the Apps Script editor. Creates private sheet + public intake form. */
function setupContest() {
  const props = PropertiesService.getScriptProperties();
  let ssId = props.getProperty('SHARED_FORECAST_SHEET_ID');
  let ss;
  if (ssId) {
    ss = SpreadsheetApp.openById(ssId);
    Logger.log('המאגר כבר קיים: ' + ss.getUrl());
  } else {
    ss = SpreadsheetApp.create(APP_CONFIG.title + ' — מאגר פרטי');
    ss.setSpreadsheetTimeZone('Asia/Jerusalem');
    const sheet = ss.getSheets()[0];
    sheet.setName('תחזיות');
    sheet.getRange(1, 1, 1, 7).setValues([[
      'זמן הגשה', 'שם/כינוי', 'נימוק', 'תחזית מפלגות (JSON)', 'תחזית גושים (JSON)', 'גרסת טופס', 'תקינות'
    ]]);
    sheet.getRange(1, 1, 1, 7).setBackground('#183153').setFontColor('#ffffff').setFontWeight('bold');
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 165);
    sheet.setColumnWidth(2, 180);
    sheet.setColumnWidth(3, 260);
    sheet.setColumnWidth(4, 360);
    sheet.setColumnWidth(5, 220);
    sheet.setColumnWidth(6, 150);
    sheet.setColumnWidth(7, 100);
    const truth = ss.insertSheet('תוצאות אמת');
    truth.getRange(1, 1, 1, 4).setValues([['מפלגה', 'מזהה', 'גוש', 'תוצאת אמת — מנדטים']]);
    truth.getRange(2, 1, APP_CONFIG.parties.length, 4).setValues(APP_CONFIG.parties.map(p => [p.name, p.id, p.bloc, '']));
    truth.getRange(1, 1, 1, 4).setBackground('#183153').setFontColor('#ffffff').setFontWeight('bold');
    truth.getRange(2, 4, APP_CONFIG.parties.length, 1).setBackground('#e7f4fc');
    truth.setFrozenRows(1);
    truth.setColumnWidth(1, 280); truth.setColumnWidth(2, 130); truth.setColumnWidth(3, 140); truth.setColumnWidth(4, 190);
    truth.getRange(APP_CONFIG.parties.length + 3, 1).setValue('ממלאים רק עמודה D לאחר פרסום תוצאות האמת. כל המפלגות יחד חייבות להסתכם ב־120.');
    props.setProperty('SHARED_FORECAST_SHEET_ID', ss.getId());
    ssId = ss.getId();
    Logger.log('נוצר מאגר פרטי ונפרד: ' + ss.getUrl());
  }

  ensureIntakeForm_(ss);
  Logger.log('הדביקו את בלוק FORM_CONFIG הבא ב־forecast.html:');
  Logger.log(props.getProperty('FORM_CONFIG_JSON'));
  Logger.log('לאחר מכן הריצו installFormTrigger פעם אחת, פרסמו Web App (Anyone) ל־doGet, והעתיקו את כתובת ה־/exec ל־FORECAST_EXPORT_URL ב־GitHub Secrets.');
  return ss.getUrl();
}

/** Creates/updates the Google Form used by forecast.html (NetFree-friendly writes). */
function ensureIntakeForm_(ss) {
  const props = PropertiesService.getScriptProperties();
  let formId = props.getProperty('INTAKE_FORM_ID');
  let form;
  if (formId) {
    try {
      form = FormApp.openById(formId);
    } catch (err) {
      form = null;
    }
  }
  if (!form) {
    form = FormApp.create(APP_CONFIG.title + ' — קליטת הגשות');
    form.setDescription('טופס קליטה טכני לתחרות התחזיות. ההגשה נעשית מממשק האתר, לא מכאן.');
    form.setCollectEmail(false);
    form.setAllowResponseEdits(false);
    form.setLimitOneResponsePerUser(false);
    props.setProperty('INTAKE_FORM_ID', form.getId());
  }

  // Wipe and recreate items so entry IDs stay aligned with our field map.
  form.getItems().slice().forEach(item => form.deleteItem(item));
  const participantItem = form.addTextItem().setTitle('participant').setRequired(true);
  const methodItem = form.addParagraphTextItem().setTitle('method').setRequired(false);
  const partiesItem = form.addParagraphTextItem().setTitle('parties_json').setRequired(true);
  const blocsItem = form.addParagraphTextItem().setTitle('blocs_json').setRequired(true);
  const versionItem = form.addTextItem().setTitle('version').setRequired(false);

  // Destination spreadsheet for raw responses (optional audit). Validated rows go to «תחזיות».
  try {
    form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  } catch (err) {
    // Destination may already be set.
  }

  form.setAcceptingResponses(true);
  const published = form.getPublishedUrl() || '';
  // Client POSTs to …/formResponse (works for both /d/e/… and /d/ID… view URLs).
  let actionUrl = '';
  if (/\/formResponse\/?$/.test(published)) {
    actionUrl = published;
  } else if (published.indexOf('/viewform') !== -1) {
    actionUrl = published.replace(/\/viewform.*/, '/formResponse');
  } else if (published) {
    actionUrl = published.replace(/\/+$/, '') + '/formResponse';
  } else {
    actionUrl = form.getEditUrl().replace(/\/edit.*/, '/formResponse');
    Logger.log('אזהרה: אין published URL; נעשה שימוש בכתובת נגזרת מ־edit. בדקו ידנית.');
  }

  // Resolve real entry.XXXX keys from a prefilled URL (more reliable than item.getId alone).
  const prefill = form.createResponse()
    .withItemResponse(participantItem.createResponse('__p__'))
    .withItemResponse(methodItem.createResponse('__m__'))
    .withItemResponse(partiesItem.createResponse('__parties__'))
    .withItemResponse(blocsItem.createResponse('__blocs__'))
    .withItemResponse(versionItem.createResponse('__v__'))
    .toPrefilledUrl();
  const entryIds = [];
  const re = /[?&](entry\.\d+)=/g;
  let match;
  while ((match = re.exec(prefill)) !== null) entryIds.push(match[1]);
  if (entryIds.length < 5) {
    throw new Error('לא הצלחנו לחלץ entry IDs מכתובת הטופס. בדקו את הטופס ידנית.');
  }

  const config = {
    actionUrl: actionUrl,
    entries: {
      participant: entryIds[0],
      method: entryIds[1],
      parties: entryIds[2],
      blocs: entryIds[3],
      version: entryIds[4]
    },
    publishedUrl: published,
    formId: form.getId()
  };
  props.setProperty('FORM_CONFIG_JSON', JSON.stringify(config, null, 2));
  props.setProperty('FORM_ENTRY_PARTICIPANT', config.entries.participant);
  props.setProperty('FORM_ENTRY_METHOD', config.entries.method);
  props.setProperty('FORM_ENTRY_PARTIES', config.entries.parties);
  props.setProperty('FORM_ENTRY_BLOCS', config.entries.blocs);
  props.setProperty('FORM_ENTRY_VERSION', config.entries.version);
  return config;
}

/** Run once after setupContest to attach the installable form submit trigger. */
function installFormTrigger() {
  const props = PropertiesService.getScriptProperties();
  const formId = props.getProperty('INTAKE_FORM_ID');
  if (!formId) throw new Error('אין טופס. הריצו setupContest קודם.');
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'onFormSubmit') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('onFormSubmit')
    .forForm(formId)
    .onFormSubmit()
    .create();
  Logger.log('הותקן trigger onFormSubmit לטופס ' + formId);
}

/**
 * Installable trigger: validate Form response and append to «תחזיות» when תקין.
 * Named items: participant, method, parties_json, blocs_json, version.
 */
function onFormSubmit(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const named = {};
    (e.response.getItemResponses() || []).forEach(ir => {
      named[String(ir.getItem().getTitle() || '')] = String(ir.getResponse() || '');
    });
    let parties;
    let blocs;
    try {
      parties = JSON.parse(named.parties_json || 'null');
      blocs = JSON.parse(named.blocs_json || 'null');
    } catch (err) {
      appendRejected_(named.participant || '', named.method || '', named.parties_json || '', named.blocs_json || '', named.version || '', 'JSON לא תקין');
      return;
    }
    const payload = {
      participant: named.participant || '',
      method: named.method || '',
      parties: parties,
      blocs: blocs,
      version: named.version || 'form-v1'
    };
    const validated = validatePayload_(payload);
    if (!validated.ok) {
      appendRejected_(payload.participant, payload.method, JSON.stringify(parties || {}), JSON.stringify(blocs || {}), payload.version, validated.message);
      return;
    }
    if (Date.now() >= new Date(APP_CONFIG.cutoffIso).getTime()) {
      appendRejected_(validated.participant, validated.method, JSON.stringify(validated.parties), JSON.stringify(validated.blocs), payload.version, 'ההגשות נסגרו');
      return;
    }
    const sheet = getForecastSheet_();
    const lastRow = sheet.getLastRow();
    const normalizedName = validated.participant.trim().toLocaleLowerCase('he-IL');
    if (lastRow > 1) {
      const names = sheet.getRange(2, 2, lastRow - 1, 1).getValues().flat();
      const duplicate = names.some(name => String(name || '').trim().toLocaleLowerCase('he-IL') === normalizedName);
      if (duplicate) {
        appendRejected_(validated.participant, validated.method, JSON.stringify(validated.parties), JSON.stringify(validated.blocs), payload.version, 'כינוי כפול');
        return;
      }
    }
    sheet.appendRow([
      new Date(), validated.participant, validated.method,
      JSON.stringify(validated.parties), JSON.stringify(validated.blocs),
      String(payload.version || 'form-v1'), 'תקין'
    ]);
  } finally {
    lock.releaseLock();
  }
}

function appendRejected_(participant, method, partiesJson, blocsJson, version, reason) {
  try {
    const sheet = getForecastSheet_();
    sheet.appendRow([
      new Date(), String(participant || ''), String(method || ''),
      String(partiesJson || ''), String(blocsJson || ''),
      String(version || ''), 'נדחה: ' + String(reason || 'שגיאה')
    ]);
  } catch (err) {
    Logger.log('appendRejected_ failed: ' + err);
  }
}

function getPublicForecasts() {
  const sheet = getForecastSheet_();
  const lastRow = sheet.getLastRow();
  const forecasts = [];
  if (lastRow > 1) {
    const rows = sheet.getRange(2, 1, lastRow - 1, 7).getValues();
    rows.forEach(row => {
      if (!row[1] || row[6] !== 'תקין') return;
      try {
        forecasts.push({
          timestamp: row[0] instanceof Date ? row[0].toISOString() : new Date(row[0]).toISOString(),
          participant: String(row[1]),
          method: String(row[2] || ''),
          parties: JSON.parse(String(row[3] || '{}')),
          blocs: JSON.parse(String(row[4] || '{}'))
        });
      } catch (err) {
        // Skip malformed rows instead of breaking the public page.
      }
    });
  }
  const consensus = forecasts.length ? calculateConsensus_(forecasts) : null;
  const truth = readTruth_();
  const leaderboard = truth.ready ? calculateLeaderboard_(forecasts, truth) : [];
  return {
    forecasts: forecasts,
    consensus: consensus,
    truthReady: truth.ready,
    leaderboard: leaderboard,
    count: forecasts.length,
    closed: Date.now() >= new Date(APP_CONFIG.cutoffIso).getTime(),
    cutoff: APP_CONFIG.cutoffIso,
    parties: APP_CONFIG.parties,
    blocs: APP_CONFIG.blocs,
    syncedAt: new Date().toISOString()
  };
}

/** Kept for manual testing from the Apps Script editor. */
function submitForecast(payload) {
  const validated = validatePayload_(payload);
  if (!validated.ok) return validated;
  if (Date.now() >= new Date(APP_CONFIG.cutoffIso).getTime()) {
    return {ok:false, message:'ההגשות נסגרו במועד שנקבע לתחרות.'};
  }
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    if (Date.now() >= new Date(APP_CONFIG.cutoffIso).getTime()) {
      return {ok:false, message:'ההגשות נסגרו במועד שנקבע לתחרות.'};
    }
    const sheet = getForecastSheet_();
    const lastRow = sheet.getLastRow();
    const normalizedName = validated.participant.trim().toLocaleLowerCase('he-IL');
    if (lastRow > 1) {
      const names = sheet.getRange(2, 2, lastRow - 1, 1).getValues().flat();
      const duplicate = names.some(name => String(name || '').trim().toLocaleLowerCase('he-IL') === normalizedName);
      if (duplicate) return {ok:false, message:'כבר קיימת תחזית תחת הכינוי הזה. בחרו כינוי אחר; לא ניתן לשנות הגשה קיימת.'};
    }
    sheet.appendRow([
      new Date(), validated.participant, validated.method,
      JSON.stringify(validated.parties), JSON.stringify(validated.blocs),
      String(payload.version || 'shared-v1'), 'תקין'
    ]);
    return {ok:true, message:'התחזית נשמרה בהצלחה במאגר המשותף.', count:Math.max(0, sheet.getLastRow() - 1)};
  } finally {
    lock.releaseLock();
  }
}

function validatePayload_(payload) {
  if (!payload || typeof payload !== 'object') return {ok:false, message:'לא התקבלו נתוני תחזית.'};
  const participant = String(payload.participant || '').trim();
  const method = String(payload.method || '').trim();
  if (!participant || participant.length > 70) return {ok:false, message:'יש להזין כינוי באורך 1–70 תווים.'};
  if (method.length > 150) return {ok:false, message:'הנימוק ארוך מדי (מקסימום 150 תווים).'};
  if (!Array.isArray(payload.parties)) return {ok:false, message:'חסרה תחזית המפלגות.'};
  const partyMap = {};
  payload.parties.forEach(p => { if (p && p.id) partyMap[String(p.id)] = Number(p.seats); });
  if (APP_CONFIG.parties.some(p => !Object.prototype.hasOwnProperty.call(partyMap, p.id))) {
    return {ok:false, message:'תחזית המפלגות אינה כוללת את כל המפלגות.'};
  }
  const parties = {};
  let partyTotal = 0;
  for (const p of APP_CONFIG.parties) {
    const n = partyMap[p.id];
    if (!Number.isInteger(n) || n < 0 || n > 120 || (n > 0 && n < 4)) {
      return {ok:false, message:'מספר המנדטים אינו תקין עבור ' + p.name + '. יש לבחור 0 או מספר שלם מ־4 עד 120.'};
    }
    parties[p.id] = n;
    partyTotal += n;
  }
  if (partyTotal !== 120) return {ok:false, message:'תחזית המפלגות חייבת להסתכם בדיוק ב־120 מנדטים.'};
  const inputBlocs = payload.blocs || {};
  const blocs = {};
  let blocTotal = 0;
  for (const b of APP_CONFIG.blocs) {
    const n = Number(inputBlocs[b.id]);
    if (!Number.isInteger(n) || n < 0 || n > 120) {
      return {ok:false, message:'תחזית הגושים אינה תקינה: ' + b.name + '.'};
    }
    blocs[b.id] = n;
    blocTotal += n;
  }
  if (blocTotal !== 120) return {ok:false, message:'תחזית הגושים חייבת להסתכם בדיוק ב־120 מנדטים.'};
  return {ok:true, participant:participant, method:method, parties:parties, blocs:blocs};
}

function calculateConsensus_(forecasts) {
  const parties = {};
  const blocs = {};
  APP_CONFIG.parties.forEach(p => {
    parties[p.id] = forecasts.reduce((sum, f) => sum + Number((f.parties || {})[p.id] || 0), 0) / forecasts.length;
  });
  APP_CONFIG.blocs.forEach(b => {
    blocs[b.id] = forecasts.reduce((sum, f) => sum + Number((f.blocs || {})[b.id] || 0), 0) / forecasts.length;
  });
  return {parties:parties, blocs:blocs};
}

function readTruth_() {
  const ssId = PropertiesService.getScriptProperties().getProperty('SHARED_FORECAST_SHEET_ID');
  if (!ssId) return {ready:false};
  const sheet = SpreadsheetApp.openById(ssId).getSheetByName('תוצאות אמת');
  if (!sheet || sheet.getLastRow() < APP_CONFIG.parties.length + 1) return {ready:false};
  const rows = sheet.getRange(2, 1, APP_CONFIG.parties.length, 4).getValues();
  const parties = {};
  let total = 0;
  for (let i = 0; i < APP_CONFIG.parties.length; i++) {
    const p = APP_CONFIG.parties[i];
    const raw = rows[i][3];
    if (raw === '' || raw === null || raw === undefined || !Number.isInteger(Number(raw)) || Number(raw) < 0 || Number(raw) > 120) return {ready:false};
    parties[p.id] = Number(raw);
    total += Number(raw);
  }
  if (total !== 120) return {ready:false};
  const blocs = {};
  APP_CONFIG.blocs.forEach(b => {
    blocs[b.id] = APP_CONFIG.parties.reduce((sum, p) => sum + (p.bloc === b.id ? parties[p.id] : 0), 0);
  });
  return {ready:true, parties:parties, blocs:blocs};
}

function calculateLeaderboard_(forecasts, truth) {
  return forecasts.map(f => {
    let partyError = 0;
    APP_CONFIG.parties.forEach(p => {
      const actual = truth.parties[p.id];
      const predicted = Number((f.parties || {})[p.id] || 0);
      const weight = actual >= 4 && actual <= 8 ? 1.25 : 1;
      partyError += Math.abs(predicted - actual) * weight;
    });
    partyError /= 2;
    let blocError = 0;
    APP_CONFIG.blocs.forEach(b => {
      blocError += Math.abs(Number((f.blocs || {})[b.id] || 0) - truth.blocs[b.id]);
    });
    blocError = (blocError / 2) * 3;
    const predictedWinter = Number((f.parties || {}).winter || 0) >= 4;
    const actualWinter = truth.parties.winter >= 4;
    const predictedZalicha = Number((f.parties || {}).zalicha || 0) >= 4;
    const actualZalicha = truth.parties.zalicha >= 4;
    const predictedRight = APP_CONFIG.parties.reduce((sum, p) => sum + (p.bloc === 'right' ? Number((f.parties || {})[p.id] || 0) : 0), 0);
    const actualRightMajority = truth.blocs.right >= 61;
    const predictedRightMajority = predictedRight >= 61;
    const winterPenalty = predictedWinter === actualWinter ? 0 : 6;
    const zalichaPenalty = predictedZalicha === actualZalicha ? 0 : 6;
    const majorityPenalty = predictedRightMajority === actualRightMajority ? 0 : 12;
    return {
      participant:f.participant,
      timestamp:f.timestamp,
      partyError:partyError,
      blocError:blocError,
      winterPenalty:winterPenalty,
      zalichaPenalty:zalichaPenalty,
      majorityPenalty:majorityPenalty,
      total:partyError + blocError + winterPenalty + zalichaPenalty + majorityPenalty
    };
  }).sort((a,b) => a.total - b.total || String(a.timestamp).localeCompare(String(b.timestamp)))
    .map((row,index) => Object.assign({rank:index+1},row));
}

function getForecastSheet_() {
  const id = PropertiesService.getScriptProperties().getProperty('SHARED_FORECAST_SHEET_ID');
  if (!id) throw new Error('המאגר עדיין לא הוקם. יש להריץ פעם אחת את setupContest מתוך עורך Apps Script.');
  return SpreadsheetApp.openById(id).getSheetByName('תחזיות');
}
