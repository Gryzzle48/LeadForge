// LeadForge — outreach drafts
// This script does NOT send email.
// It creates Gmail drafts for rows that have an email address.
// You review each draft in Gmail and send it yourself.
//
// Paste this into Extensions > Apps Script on the exported sheet.
// Set SENDER_NAME, save, then run createDrafts once.
// If an older version of this script added a timer, run removeAllTriggers.

const SHEET_NAME = 'Leads';
const SENDER_NAME = 'Your Name';
const COL = {
  NAME: 0,
  CATEGORY: 1,
  ADDRESS: 2,
  PHONE: 3,
  MAPS: 4,
  RATING: 5,
  REVIEWS: 6,
  WEBSITE: 7,
  EMAIL: 8,
  SUBJECT: 9,
  BODY: 10,
  STATUS: 11,
  NOTES: 12
};

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function createDrafts() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet) {
    Logger.log('Sheet "' + SHEET_NAME + '" not found.');
    return;
  }

  const data = sheet.getDataRange().getValues();
  let made = 0;

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const status = String(row[COL.STATUS] || '').trim();
    const email = String(row[COL.EMAIL] || '').trim();
    if (!email) continue;
    if (status === 'Draft ready' || status === 'Contacted' || status === 'Skip') continue;

    const subject = String(row[COL.SUBJECT] || ('Website for ' + row[COL.NAME]));
    const plain = String(row[COL.BODY] || '');
    const html = escapeHtml(plain).replace(/\n/g, '<br>')
      + '<br><br><hr><small>Draft only. ' + escapeHtml(SENDER_NAME) + '</small>';

    try {
      GmailApp.createDraft(email, subject, plain + '\n\n— ' + SENDER_NAME, {
        name: SENDER_NAME,
        htmlBody: html
      });
      sheet.getRange(i + 1, COL.STATUS + 1).setValue('Draft ready');
      made++;
    } catch (err) {
      sheet.getRange(i + 1, COL.STATUS + 1).setValue('Error: ' + err.message);
    }
  }

  Logger.log('Created ' + made + ' drafts. Nothing was sent.');
}

function removeAllTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    ScriptApp.deleteTrigger(trigger);
  });
  Logger.log('Removed every trigger. This script does not send email.');
}
