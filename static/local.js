(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const dictionary = {
    ja: {
      eyebrow: "ローカル在留カードリーダー", title: "在留カードリーダー", subtitle: "カードを読み取り、内容を確認できます",
      ready: "ローカルサーバー稼働中", unavailable: "ローカルサーバーに接続できません", reader_kicker: "準備", reader_heading: "カードリーダー",
      refresh: "状態を更新", reader_select: "使用するカードリーダー", save: "保存", reader_ready: "接続済み", reader_missing: "リーダーが見つかりません",
      choose_reader: "リーダーを選択してください", reader_saved: "リーダー設定を保存しました。", scan_kicker: "このPCで読み取る", scan_heading: "在留カードの読み取り",
      step_1: "在留カードをリーダーに置きます", step_2: "カード表面の在留カード番号を入力します", step_3: "「読み取り開始」を押します", step_4: "読み取り結果をカードと照合します",
      privacy_title: "プライバシーについて", privacy_text: "本人の同意がある、確認を許可されたカードのみ読み取ってください。顔写真、マイナンバー、ICの生データは保存・表示しません。必要な画像処理はメモリ上で行い、画像自体は出力しません。",
      card_number: "在留カード番号（カード表面に印字）", sample_data: "開発・テスト用サンプルデータを使う", sample_hint: "サンプルデータを使用します。カードは不要です。",
      check_card: "カードを確認", start_read: "読み取り開始", checking: "カードを確認しています…", detected: "カードを検出しました。", not_detected: "カードを検出できませんでした。",
      invalid_number: "在留カード番号の形式を確認してください。", reading: "読み取り中です。カードを動かさないでください。", complete: "読み取りが完了しました。内容を確認してください。",
      failed: "読み取りできませんでした。もう一度お試しください。", result_kicker: "確認", result_heading: "読み取り結果", discard: "破棄する",
      ocr_diagnostics: "OCR診断を表示", ocr_diagnostics_title: "OCR安全診断（画像・OCR全文は表示しません）", warning_name: "氏名はOCR由来です。確認してください。",
      warning_address: "住所にOCR由来または未取得の項目があります。確認してください。", not_read_name: "氏名を読み取れませんでした。このアプリでは氏名を入力できません。カード表面を見て、必要に応じて記録先で修正してください。",
      not_read_address: "住所を読み取れませんでした。このアプリでは住所を入力できません。カード表面を見て、必要に応じて記録先で修正してください。", warning_signature: "署名検証の状態を確認してください。",
      needs_review: "確認が必要", ocr_review: "OCR確認（{field}・{confidence}）: {reasons}。候補: {candidate}", official_test_warning: "公的テストカード用モード: 本番カードの真正性確認結果ではありません。",
      trust_source_production: "信頼元: 出入国在留管理庁 公開鍵証明書", trust_source_test: "注意: 本番カードの真正性確認結果ではありません",
      fields: ["在留カード番号", "氏名", "生年月日", "性別", "国籍・地域", "在留資格", "在留期間", "在留期限", "カード有効期限", "許可日", "都道府県", "市区町村", "以降の住所", "就労制限", "資格外活動許可", "資格外活動許可の詳細", "真正性確認"]
    },
    en: {
      eyebrow: "Local Residence Card Reader", title: "Residence Card Reader", subtitle: "Read a card and review its details.", ready: "Local server is running", unavailable: "Cannot connect to the local server",
      reader_kicker: "Ready", reader_heading: "Card reader", refresh: "Refresh status", reader_select: "Card reader to use", save: "Save", reader_ready: "Connected", reader_missing: "No reader found",
      choose_reader: "Select a reader", reader_saved: "Reader setting saved.", scan_kicker: "Read on this PC", scan_heading: "Read a residence card", step_1: "Place the residence card on the reader",
      step_2: "Enter the residence card number printed on the card", step_3: "Select “Start reading”", step_4: "Review the result against the card", privacy_title: "Privacy",
      privacy_text: "Read only cards for which the holder has consented or verification is authorized. Face photos, My Number data, and raw IC data are never saved or displayed. Any required image processing stays in memory and images are not output.",
      card_number: "Residence card number (printed on the card)", sample_data: "Use sample data for development and testing", sample_hint: "Sample data is being used; no card is needed.", check_card: "Check card",
      start_read: "Start reading", checking: "Checking the card…", detected: "Card detected.", not_detected: "Card was not detected.", invalid_number: "Check the residence card number format.",
      reading: "Reading the card. Please do not move it.", complete: "Reading is complete. Review the details.", failed: "The card could not be read. Please try again.", result_kicker: "Review", result_heading: "Read result", discard: "Discard",
      ocr_diagnostics: "Show OCR diagnostics", ocr_diagnostics_title: "Safe OCR diagnostics (image and full OCR text are not shown)", warning_name: "The name is OCR-derived. Please review it.",
      warning_address: "The address is OCR-derived or incomplete. Please review it.", not_read_name: "The name could not be read. This app has no field for typing a name — read it from the card and correct the record if needed.",
      not_read_address: "The address could not be read. This app has no field for typing an address — read it from the card and correct the record if needed.", warning_signature: "Please review the signature verification status.",
      needs_review: "Review needed", ocr_review: "OCR review ({field}, {confidence}): {reasons}. Suggested: {candidate}", official_test_warning: "Official test-card mode: this is not a production-card authenticity result.",
      trust_source_production: "Trust source: Immigration Services Agency public-key certificate", trust_source_test: "Caution: this is not a production-card authenticity result",
      fields: ["Residence card number", "Name", "Date of birth", "Sex", "Nationality / region", "Residence status", "Period of stay", "Residence expiry", "Card expiry", "Permission date", "Prefecture", "Municipality", "Address after municipality", "Work restrictions", "Permission for activities outside status", "Permission details", "Authenticity"]
    }
  };
  const fieldKeys = ["card_number", "display_name", "birth_date", "display_sex", "nationality_label", "residence_status_label", "display_period_of_stay", "residence_expiry_date", "card_expiry_date", "permission_date", "address_prefecture", "address_municipality", "address_other", "work_restriction_label", "display_qualification_activity_permission", "display_qualification_activity_permission_detail", "display_signature_status"];
  const state = { language: navigator.language && navigator.language.toLowerCase().startsWith("ja") ? "ja" : "en", result: null, status: null };
  const t = (key, values) => {
    let text = dictionary[state.language][key] || key;
    Object.keys(values || {}).forEach((name) => { text = text.replace(`{${name}}`, values[name]); });
    return text;
  };
  const localToken = (document.querySelector('meta[name="local-request-token"]') || {}).content || "";
  const api = async (path, body) => {
    const headers = { "Accept-Language": state.language, "X-Local-Token": localToken };
    if (body) headers["Content-Type"] = "application/json";
    const response = await fetch(path, { method: body ? "POST" : "GET", headers, credentials: "same-origin", body: body ? JSON.stringify(body) : undefined });
    if (!response.ok) throw new Error(t("failed"));
    return response.json();
  };
  const say = (id, message, error) => {
    const node = $(id);
    node.textContent = message || "";
    node.classList.toggle("error", Boolean(error));
  };
  const notRead = (status) => String(status || "").startsWith("failed");

  function translatePage() {
    document.documentElement.lang = state.language;
    document.title = t("title");
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
    $("langJa").setAttribute("aria-pressed", String(state.language === "ja"));
    $("langEn").setAttribute("aria-pressed", String(state.language === "en"));
    $("sampleHint").textContent = t("sample_hint");
    if (state.status) renderStatus(state.status);
    renderResult();
  }
  function warningTexts(card) {
    const notes = [];
    if (notRead(card.name_ocr_status)) notes.push(t("not_read_name"));
    else if (card.name_ocr_status || (card.display_name || "").includes("OCR")) notes.push(t("warning_name"));
    if (notRead(card.address_ocr_status)) notes.push(t("not_read_address"));
    else if (card.address_ocr_status || !card.address_prefecture || !card.address_municipality) notes.push(t("warning_address"));
    if (card.signature_verification_status !== "verified_production") notes.push(t("warning_signature"));
    return notes;
  }
  function ocrReviewTexts(card) {
    const notes = [];
    [["name", "Name"], ["address", "Address"]].forEach(([prefix, label]) => {
      if (!card[`${prefix}_ocr_review_required`]) return;
      const reasons = (card[`${prefix}_ocr_review_reasons`] || []).join(", ") || "review_required";
      notes.push(`${t("needs_review")}: ${t("ocr_review", { field: state.language === "ja" ? (prefix === "name" ? "氏名" : "住所") : label, confidence: card[`${prefix}_ocr_confidence_category`] || "low", reasons, candidate: card[`${prefix}_ocr_suggested_candidate`] || "—" })}`);
    });
    return notes;
  }
  function displayValue(card, key) {
    if (state.language === "ja") return card[key] || "";
    if (key === "display_sex") return String(card.sex_code || "").toUpperCase() === "M" || String(card.sex_code || "") === "1" ? "Male" : String(card.sex_code || "").toUpperCase() === "F" || String(card.sex_code || "") === "2" ? "Female" : card[key] || "";
    if (key === "display_period_of_stay" && String(card.period_of_stay_raw || "").match(/^\d{4}$/)) { const raw = card.period_of_stay_raw; return raw === "0000" ? "Indefinite" : `${Number(raw.slice(0, 2))} year(s) ${Number(raw.slice(2))} month(s)`; }
    if (key === "display_qualification_activity_permission") return String(card.comprehensive_permission_code || card.individual_permission_code || "") === "0" ? "Not permitted" : "Permitted";
    if (key === "display_signature_status") {
      const labels = { verified: "Signature: Verified", not_verified: "Signature: Not verified", skipped_by_config: "Signature: Not checked; skipped by settings", certificate_unavailable: "Signature: Certificate unavailable", unsupported_card_generation: "Signature: Not supported for this card generation" };
      return labels[card.signature_verification_status] || card[key] || "";
    }
    return card[key] || "";
  }
  function renderResult() {
    const card = state.result;
    $("resultBlock").hidden = !card;
    $("ocrDebug").hidden = true;
    if (!card) return;
    const table = $("resultTable");
    table.innerHTML = "";
    fieldKeys.forEach((key, index) => {
      const row = table.insertRow();
      const heading = document.createElement("th");
      heading.textContent = dictionary[state.language].fields[index];
      const value = row.insertCell();
      value.textContent = displayValue(card, key);
      row.appendChild(heading);
    });
    const warnings = $("warnings");
    warnings.innerHTML = "";
    if (card.signature_verification_status === "verified_production" || card.signature_verification_status === "verified_official_test") {
      const note = document.createElement("p");
      note.className = card.signature_verification_status === "verified_official_test" ? "warning review-badge" : "message ok";
      note.textContent = t(card.signature_verification_status === "verified_production" ? "trust_source_production" : "trust_source_test");
      warnings.appendChild(note);
    }
    warningTexts(card).forEach((text) => { const note = document.createElement("p"); note.className = "warning"; note.textContent = text; warnings.appendChild(note); });
    ocrReviewTexts(card).forEach((text) => { const note = document.createElement("p"); note.className = "warning review-badge"; note.textContent = text; warnings.appendChild(note); });
  }
  function renderStatus(status) {
    state.status = status;
    const warning = $("officialTestWarning");
    warning.hidden = !(status.verification || {}).official_test_mode;
    warning.textContent = t("official_test_warning");
    const reader = status.reader || {};
    const indicator = $("readerIndicator");
    if (reader.available) {
      indicator.dataset.state = "ready";
      $("readerStatus").textContent = `${t("reader_ready")}: ${reader.name || t("choose_reader")}`;
      $("readerHint").textContent = reader.name || "";
    } else {
      indicator.dataset.state = "missing";
      $("readerStatus").textContent = t("reader_missing");
      $("readerHint").textContent = reader.message || "";
    }
    const select = $("readerSelect");
    select.innerHTML = "";
    (reader.readers || []).forEach((readerItem) => { const option = document.createElement("option"); option.value = String(readerItem.id); option.textContent = readerItem.name; select.appendChild(option); });
    select.value = String((status.config || {}).reader_id || 0);
  }
  async function refresh() {
    try { const status = await api("/api/local/status"); $("healthStatus").textContent = t("ready"); renderStatus(status); }
    catch (error) { $("healthStatus").textContent = t("unavailable"); }
  }
  async function scan() {
    const cardNumber = $("cardNumber").value.trim().toUpperCase();
    if (!/^[A-Z]{2}\d{8}[A-Z]{2}$/.test(cardNumber)) { say("scanMessage", t("invalid_number"), true); return; }
    say("scanMessage", t("reading"));
    try {
      const result = await api("/api/local/manual-scan", { reader_id: Number($("readerSelect").value || 0), card_number: cardNumber, use_mock: $("useMock").checked });
      if (!result.success) { say("scanMessage", result.message || t("failed"), true); return; }
      state.result = result.data;
      renderResult();
      say("scanMessage", t("complete"));
    } catch (error) { say("scanMessage", t("failed"), true); }
  }

  $("langJa").addEventListener("click", () => { state.language = "ja"; translatePage(); });
  $("langEn").addEventListener("click", () => { state.language = "en"; translatePage(); });
  $("refreshReaders").addEventListener("click", refresh);
  $("saveReader").addEventListener("click", async () => {
    try { await api("/api/local/config", { reader_id: Number($("readerSelect").value || 0) }); say("scanMessage", t("reader_saved")); await refresh(); }
    catch (error) { say("scanMessage", t("failed"), true); }
  });
  $("useMock").addEventListener("change", () => { $("sampleHint").hidden = !$("useMock").checked; });
  $("checkCard").addEventListener("click", async () => {
    say("scanMessage", t("checking"));
    try { const status = await api("/api/local/status?check_card=true"); say("scanMessage", status.card && status.card.card_detected ? t("detected") : t("not_detected"), !(status.card && status.card.card_detected)); }
    catch (error) { say("scanMessage", t("failed"), true); }
  });
  $("readCard").addEventListener("click", scan);
  $("showOcrDebug").addEventListener("click", () => {
    if (!state.result) return;
    const card = state.result;
    const dimension = card.front_image_width && card.front_image_height ? `${card.front_image_width} × ${card.front_image_height}` : "—";
    $("ocrDebug").textContent = [t("ocr_diagnostics_title"), `status: ${card.front_ocr_status || "—"}`, `engine: ${card.front_ocr_engine || "—"}`, `model: ${card.front_ocr_model || "—"}`, `confidence: ${card.front_ocr_confidence || "—"}`, `detected text rows: ${card.front_ocr_row_count || "—"}`, `image dimensions: ${dimension}`, `nationality extraction: ${card.front_ocr_nationality_strategy || "—"}`, `address extraction: ${card.front_ocr_address_strategy || "—"}`, `name review: ${card.name_ocr_status || "—"}`, `address review: ${card.address_ocr_status || "—"}`].join("\n");
    $("ocrDebug").hidden = !$("ocrDebug").hidden;
  });
  $("discard").addEventListener("click", () => { state.result = null; renderResult(); });
  translatePage();
  refresh();
})();
