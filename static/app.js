const $ = (selector) => document.querySelector(selector);
if (location.protocol === 'file:') document.documentElement.classList.add('file-mode');
const storageKey = 'qrplatba.profiles.v1';
let profiles = loadProfiles();
let selectedId = null;
let editingId = null;
let current = null;
let revision = 0;
let debounce;

function loadProfiles() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) || '[]');
    return Array.isArray(value) ? value.filter(p => p && typeof p.id === 'string' && typeof p.name === 'string' && typeof p.account === 'string') : [];
  } catch { return []; }
}
function saveProfiles() {
  try { localStorage.setItem(storageKey, JSON.stringify(profiles)); }
  catch { setStatus('Profily nelze uložit. Zkontrolujte nastavení úložiště prohlížeče.', true); }
}
function setStatus(message, error = false) {
  $('#status').textContent = message;
  $('#status').classList.toggle('error', error);
}
function renderProfiles() {
  const list = $('#profiles');
  const select = $('#account');
  list.replaceChildren();
  select.replaceChildren(new Option('Vyberte uložený profil', ''));
  if (!profiles.length) {
    const empty = document.createElement('div'); empty.className = 'empty-profiles';
    empty.innerHTML = '<div>◎</div><strong>Zatím žádné účty</strong><span>Přidejte první profil tlačítkem +.</span>';
    list.append(empty);
  }
  for (const p of profiles) {
    const option = new Option(p.name, p.id); select.add(option);
    const row = document.createElement('div'); row.className = 'profile-row' + (p.id === selectedId ? ' selected' : '');
    const choose = document.createElement('button'); choose.type = 'button'; choose.className = 'profile-choose';
    const name = document.createElement('strong'); name.textContent = p.name;
    const account = document.createElement('small'); account.textContent = p.account;
    choose.append(name, account); choose.onclick = () => selectProfile(p.id);
    const menu = document.createElement('button'); menu.type = 'button'; menu.className = 'profile-menu'; menu.textContent = '⋯'; menu.title = 'Upravit profil'; menu.setAttribute('aria-label', `Upravit profil ${p.name}`); menu.onclick = () => openProfile(p.id);
    row.append(choose, menu); list.append(row);
  }
  select.value = selectedId || '';
}
function selectProfile(id) { selectedId = id || null; renderProfiles(); scheduleGenerate(); }
function openProfile(id = null) {
  editingId = id;
  const p = profiles.find(item => item.id === id);
  $('#dialogTitle').textContent = p ? 'Upravit profil' : 'Nový profil';
  $('#profileName').value = p?.name || '';
  $('#profileAccount').value = p?.account || '';
  $('#profileError').textContent = '';
  $('#deleteProfile')?.remove();
  if (p) {
    const button = document.createElement('button'); button.type = 'button'; button.id = 'deleteProfile'; button.className = 'danger'; button.textContent = 'Smazat profil';
    button.onclick = () => {
      if (!confirm(`Smazat profil „${p.name}“?`)) return;
      profiles = profiles.filter(item => item.id !== p.id);
      if (selectedId === p.id) selectedId = null;
      saveProfiles(); renderProfiles(); scheduleGenerate(); $('#profileDialog').close();
    };
    $('#profileForm .dialog-actions').prepend(button);
  }
  $('#profileDialog').showModal(); $('#profileName').focus();
}
async function api(path, data) {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Požadavek se nezdařil.');
  return result;
}
async function saveProfile(event) {
  event.preventDefault();
  const name = $('#profileName').value.trim();
  const account = $('#profileAccount').value.trim();
  if (!name) { $('#profileError').textContent = 'Zadejte název profilu.'; return; }
  try {
    const { iban } = await api('/api/account', { account });
    const id = editingId || crypto.randomUUID();
    const value = { id, name, account, iban };
    const index = profiles.findIndex(p => p.id === id);
    if (index < 0) profiles.push(value); else profiles[index] = value;
    selectedId = id; saveProfiles(); renderProfiles(); scheduleGenerate(); $('#profileDialog').close();
  } catch (error) { $('#profileError').textContent = error.message; }
}
function clearPreview() {
  current = null;
  $('#qrImage').hidden = true; $('#qrImage').removeAttribute('src');
  $('#qrPlaceholder').hidden = false; $('#ibanDisplay').hidden = true; $('#spaydText').textContent = '—';
  for (const id of ['copyQr', 'savePng', 'copySpayd', 'share']) $("#" + id).disabled = true;
}
function scheduleGenerate() { clearTimeout(debounce); debounce = setTimeout(generate, 160); }
async function generate() {
  const call = ++revision;
  const profile = profiles.find(p => p.id === selectedId);
  const amount = $('#amount').value.trim();
  clearPreview();
  if (!profile || !amount) { setStatus('Vyberte účet a zadejte částku.'); return; }
  if (!/^[0-9]{0,10}$/.test($('#vs').value)) { setStatus('Variabilní symbol může obsahovat jen číslice, nejvýše 10 znaků.', true); return; }
  setStatus('Připravuji QR kód…');
  try {
    const result = await api('/api/payment', { account: profile.account, amount, currency: $('#currency').value, vs: $('#vs').value, message: $('#message').value });
    if (call !== revision) return;
    current = result;
    $('#qrImage').src = result.png; $('#qrImage').hidden = false; $('#qrPlaceholder').hidden = true;
    $('#ibanText').textContent = result.iban; $('#ibanDisplay').hidden = false;
    $('#spaydText').textContent = result.spayd;
    for (const id of ['copyQr', 'savePng', 'copySpayd', 'share']) $('#' + id).disabled = false;
    setStatus('QR kód je připravený.');
  } catch (error) { if (call === revision) setStatus(error.message, true); }
}
function pngBlob() {
  const binary = atob(current.png.split(',', 2)[1]);
  const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
  return new Blob([bytes], { type: 'image/png' });
}
async function copyQr() {
  if (!current) return;
  try { await navigator.clipboard.write([new ClipboardItem({ 'image/png': pngBlob() })]); setStatus('QR kód zkopírován do schránky.'); }
  catch { setStatus('Kopírování obrázku není v tomto prohlížeči dostupné. Použijte Uložit PNG.', true); }
}
function savePng() {
  if (!current) return;
  const link = document.createElement('a'); link.href = current.png;
  link.download = `qr-platba-${Date.now()}.png`; document.body.append(link); link.click(); link.remove();
  setStatus('PNG připraveno ke stažení.');
}
async function copySpayd() {
  if (!current) return;
  try { await navigator.clipboard.writeText(current.spayd); setStatus('SPAYD řetězec zkopírován.'); }
  catch { setStatus('Kopírování není dostupné. Řetězec můžete označit pod QR kódem.', true); }
}
async function sharePayment() {
  if (!current || !navigator.share) return;
  try { const file = new File([pngBlob()], 'qr-platba.png', { type: 'image/png' }); await navigator.share({ title: 'QR Platba', text: current.spayd, files: [file] }); }
  catch (error) { if (error.name !== 'AbortError') setStatus('Sdílení není dostupné. Použijte Uložit PNG.', true); }
}
$('#addProfile').onclick = () => openProfile();
$('#closeDialog').onclick = () => $('#profileDialog').close();
$('#cancelDialog').onclick = () => $('#profileDialog').close();
$('#profileForm').onsubmit = saveProfile;
$('#account').onchange = event => selectProfile(event.target.value);
for (const id of ['amount', 'currency', 'vs', 'message']) $('#' + id).addEventListener('input', scheduleGenerate);
$('#newPayment').onclick = () => { for (const id of ['amount', 'vs', 'message']) $('#' + id).value = ''; scheduleGenerate(); $('#amount').focus(); };
document.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'n') { event.preventDefault(); $('#newPayment').click(); } });
$('#copyQr').onclick = copyQr; $('#savePng').onclick = savePng; $('#copySpayd').onclick = copySpayd;
if (navigator.share) { $('#share').hidden = false; $('#share').onclick = sharePayment; }
renderProfiles();
