#!/usr/bin/env node
// Dựng docs/Slide.pptx. Chạy: NODE_PATH=.report-tools/node_modules node docs/build_slides.js
// Lời thoại trong ghi chú diễn giả lấy từ docs/thuyet-trinh.md (khối trích dẫn dưới mỗi "### Slide N").
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = __dirname;
const A = (n) => path.join(DOCS, "report-assets", n);
const FIG = {
  usecase: [A("figure-01-6e86c7e31c9f.png"), 3326, 2014],
  erd: [A("figure-03-ae1e2568049c.png"), 4160, 4316],
  arch: [A("figure-04-3674c9b62e85.png"), 3998, 4342],
  seq: [A("figure-05-0017d40ad0bb.png"), 5068, 4370],
  saga: [A("figure-07-a111143eac14.png"), 950, 1792],
  c51: [A("figure-08-6238377bd978.png"), 1888, 1366],
  c52: [A("figure-09-4ddd3edc2c39.png"), 2006, 1610],
};

const THEME = {
  name: "iBanking Hoc Phi",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "12262B", lt1: "FFFFFF", dk2: "0B3C49", lt2: "E6F0F1",
    accent1: "0B3C49", accent2: "F2A541", accent3: "1B7F79", accent4: "C8553D",
    accent5: "5C7C85", accent6: "9FC5C9", hlink: "1B7F79", folHlink: "5C7C85",
  },
};

const md = fs.readFileSync(path.join(DOCS, "thuyet-trinh.md"), "utf8");
const notes = {};
for (const block of md.split(/^### Slide /m).slice(1)) {
  const n = parseInt(block, 10);
  notes[n] = block.split("\n").filter((l) => l.startsWith(">")).map((l) => l.replace(/^>\s?/, "")).join("\n").trim();
}

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Phân hệ đóng học phí iBanking — Nhóm 11";
pres.author = "Nhóm 11";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.9, w: 5.2, h: 2.2, fontSize: 34, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.65, fontSize: 28, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Nhóm 11 · Đóng học phí iBanking", options: { x: 0.5, y: 5.2, w: 5, h: 0.25, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.25, fontSize: 10, color: C.accent5, align: "right" },
});

let section = "";
function slide(n, master, title) {
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  if (notes[n]) s.addNotes(notes[n]);
  return s;
}
// Đặt hình vừa khung (x, y, w, h), giữ tỷ lệ, canh giữa.
function fit(s, [file, pw, ph], x, y, w, h, name) {
  const k = Math.min(w / pw, h / ph);
  const iw = pw * k, ih = ph * k;
  s.addImage({ path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih, objectName: name, altText: name });
}
function card(s, x, y, w, h, fill = C.background2) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill, width: 0 } });
}
function text(s, t, o) {
  s.addText(t, { isTextBox: true, margin: 0, color: C.text1, fontSize: 14, valign: "top", ...o });
}
// Thẻ có tiêu đề đậm và một dòng mô tả.
function labelCard(s, x, y, w, h, head, body, fill) {
  card(s, x, y, w, h, fill);
  text(s, [
    { text: head, options: { bold: true, fontSize: 14, color: C.text2, breakLine: true } },
    { text: body, options: { fontSize: 12, color: C.text1 } },
  ], { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h - 0.2, valign: "middle" });
}
// Con số lớn kèm nhãn.
function stat(s, x, y, w, big, label) {
  card(s, x, y, w, 0.95);
  text(s, big, { x, y: y + 0.08, w, h: 0.5, fontSize: 26, bold: true, color: C.accent3, align: "center", fontFace: THEME.headFontFace });
  text(s, label, { x, y: y + 0.58, w, h: 0.3, fontSize: 11, color: C.text1, align: "center" });
}

// ---------- 1. Tổng quan ----------
pres.addSection({ title: "Tổng quan" }); section = "Tổng quan";
{
  const s = slide(1, "DARK", "Phân hệ đóng học phí trên iBanking");
  text(s, "Kiến trúc Microservices · Đồ án giữa kỳ SOA (504070)", { x: 0.6, y: 2.55, w: 4.6, h: 0.6, fontSize: 16, color: C.accent2 });
  text(s, [
    { text: "Nhóm 11", options: { bold: true, breakLine: true } },
    { text: "Lê Nam Giang · 523H0020", options: { breakLine: true } },
    { text: "Nguyễn Gia Nhật Khánh · 523H0149", options: { breakLine: true } },
    { text: "Nguyễn Hoàng Thanh Minh · 519H0194", options: { breakLine: true } },
    { text: "GVHD: Dương Hữu Phúc" },
  ], { x: 0.6, y: 3.45, w: 4.6, h: 1.5, fontSize: 13, color: C.background1, paraSpaceAfter: 3 });

  const steps = [
    ["1", "Đăng nhập, xem số dư"],
    ["2", "Tra cứu học phí theo MSSV"],
    ["3", "Thanh toán có OTP qua email"],
    ["4", "Gạch nợ, lịch sử, biên lai"],
  ];
  steps.forEach(([num, label], i) => {
    const y = 0.9 + i * 0.82;
    card(s, 5.9, y, 3.6, 0.67, C.background1);
    s.addShape(pres.shapes.OVAL, { x: 6.05, y: y + 0.13, w: 0.41, h: 0.41, fill: { color: C.accent2 }, line: { color: C.accent2, width: 0 } });
    text(s, num, { x: 6.05, y: y + 0.13, w: 0.41, h: 0.41, fontSize: 14, bold: true, color: C.text2, align: "center", valign: "middle" });
    text(s, label, { x: 6.62, y, w: 2.8, h: 0.67, fontSize: 14, color: C.text2, valign: "middle" });
  });
  text(s, "6 service · API Gateway · Web  |  FastAPI · PostgreSQL · Docker Compose (11 container)", { x: 5.9, y: 4.3, w: 3.6, h: 0.6, fontSize: 11, color: C.accent6 });
}

// ---------- 2. Use Case ----------
pres.addSection({ title: "Phân tích và thiết kế" }); section = "Phân tích và thiết kế";
{
  const s = slide(2, "CONTENT", "Use Case: 1 tác nhân chính, 7 chức năng");
  fit(s, FIG.usecase, 0.5, 1.15, 6.1, 3.85, "Sơ đồ Use Case");
  labelCard(s, 6.9, 1.15, 2.6, 0.95, "Người dùng iBanking", "Tác nhân chính, đã có tài khoản");
  labelCard(s, 6.9, 2.25, 2.6, 0.95, "Hệ thống Email", "Nhận OTP và biên lai (MailHog)");
  labelCard(s, 6.9, 3.35, 2.6, 0.95, "Hệ thống Đào tạo", "Nguồn sinh viên và công nợ");
  text(s, "Không có đăng ký tài khoản: đề bài không yêu cầu.", { x: 6.9, y: 4.45, w: 2.6, h: 0.55, fontSize: 11, italic: true, color: C.accent5 });
}

// ---------- 3. ERD ----------
{
  const s = slide(3, "CONTENT", "Dữ liệu: mỗi service một database");
  fit(s, FIG.erd, 0.5, 1.1, 4.0, 3.95, "Sơ đồ ERD");
  const head = (t) => ({ text: t, options: { bold: true, color: THEME.colors.lt1, fill: { color: THEME.colors.dk2 }, fontSize: 12 } });
  const rows = [
    ["authdb", "users"],
    ["accountdb", "accounts, ledger_entries"],
    ["tuitiondb", "students, tuition_fees"],
    ["paymentdb", "payments, payment_events"],
    ["otpdb", "otp_codes"],
    ["notificationdb", "email_logs"],
  ];
  s.addTable([[head("Database"), head("Bảng")], ...rows.map((r) => r.map((t) => ({ text: t, options: { fontSize: 12, color: THEME.colors.dk1 } })))], {
    x: 4.8, y: 1.1, w: 4.7, colW: [1.7, 3.0], rowH: 0.3, border: { type: "solid", pt: 0.5, color: THEME.colors.accent6 }, valign: "middle",
  });
  card(s, 4.8, 3.4, 4.7, 1.65);
  text(s, [
    { text: "Ràng buộc đặt ở tầng database", options: { bold: true, color: C.text2, breakLine: true } },
    { text: "CHECK balance >= 0: không chi vượt số dư", options: { bullet: true, breakLine: true } },
    { text: "UNIQUE reference: mỗi bút toán ghi một lần", options: { bullet: true, breakLine: true } },
    { text: "UNIQUE fee_id khi SUCCESS: một khoản, một giao dịch", options: { bullet: true } },
  ], { x: 4.95, y: 3.5, w: 4.4, h: 1.45, fontSize: 12, paraSpaceAfter: 4, valign: "middle" });
}

// ---------- 4. Kiến trúc ----------
{
  const s = slide(4, "CONTENT", "Kiến trúc: Gateway và 6 service nghiệp vụ");
  fit(s, FIG.arch, 0.5, 1.1, 3.7, 3.95, "Sơ đồ kiến trúc microservices");
  const svc = [
    ["api-gateway", "Điểm vào duy nhất, JWT, định tuyến"],
    ["auth", "Người dùng, phát hành JWT"],
    ["account", "Số dư, sổ cái, khóa dòng"],
    ["tuition", "Sinh viên, công nợ, gạch nợ"],
    ["otp", "Sinh và xác thực mã OTP"],
    ["notification", "Cổng gửi email duy nhất"],
  ];
  svc.forEach(([h, b], i) => {
    const x = 4.5 + (i % 2) * 2.55, y = 1.1 + Math.floor(i / 2) * 0.93;
    labelCard(s, x, y, 2.45, 0.83, h, b);
  });
  card(s, 4.5, 3.89, 5.0, 1.16, C.text2);
  text(s, [
    { text: "payment-service · bộ điều phối", options: { bold: true, fontSize: 14, color: C.accent2, breakLine: true } },
    { text: "Không tự sửa số dư hay học phí, chỉ gọi service sở hữu dữ liệu", options: { fontSize: 12, color: C.background1 } },
  ], { x: 4.65, y: 3.95, w: 4.7, h: 1.04, valign: "middle" });
}

// ---------- 5. Giao tiếp và OTP ----------
pres.addSection({ title: "Giải pháp kỹ thuật" }); section = "Giải pháp kỹ thuật";
{
  const s = slide(5, "CONTENT", "Giao tiếp REST đồng bộ và xác thực OTP");
  fit(s, FIG.seq, 0.5, 1.1, 4.5, 3.95, "Sơ đồ tuần tự luồng thanh toán");
  stat(s, 5.3, 1.1, 1.3, "6 số", "gắn 1 giao dịch");
  stat(s, 6.75, 1.1, 1.3, "5 phút", "hết hạn");
  stat(s, 8.2, 1.1, 1.3, "5 lần", "sai thì khóa");
  text(s, [
    { text: "OTP", options: { bold: true, color: C.text2, breakLine: true } },
    { text: "Dùng một lần, gửi lại thì mã cũ bị thu hồi", options: { bullet: true, breakLine: true } },
    { text: "Chỉ lưu băm SHA-256, không lưu mã gốc", options: { bullet: true, breakLine: true } },
    { text: "Giao tiếp", options: { bold: true, color: C.text2, breakLine: true } },
    { text: "REST/JSON đồng bộ vì người dùng chờ kết quả", options: { bullet: true, breakLine: true } },
    { text: "/internal có token riêng, gateway chặn từ ngoài", options: { bullet: true, breakLine: true } },
    { text: "Truy vết OpenTelemetry, xem trên Jaeger", options: { bullet: true } },
  ], { x: 5.3, y: 2.3, w: 4.2, h: 2.75, fontSize: 13, paraSpaceAfter: 5 });
}

// ---------- 6. Saga ----------
{
  const s = slide(6, "CONTENT", "Transaction: Saga có bù trừ");
  fit(s, FIG.saga, 7.2, 1.1, 2.3, 3.95, "Lưu đồ saga và bù trừ");
  labelCard(s, 0.5, 1.1, 3.1, 0.95, "Trong một service", "Transaction ACID của PostgreSQL");
  labelCard(s, 3.8, 1.1, 3.1, 0.95, "Xuyên service", "Saga do payment-service điều phối");
  const flow = ["Xác thực OTP", "Trừ tiền", "Gạch nợ", "Biên lai"];
  flow.forEach((t, i) => {
    const x = 0.5 + i * 1.62;
    card(s, x, 2.35, 1.4, 0.6, C.text2);
    text(s, t, { x, y: 2.35, w: 1.4, h: 0.6, fontSize: 13, bold: true, color: C.background1, align: "center", valign: "middle" });
    if (i < flow.length - 1) text(s, "→", { x: x + 1.4, y: 2.35, w: 0.22, h: 0.6, fontSize: 16, color: C.accent5, align: "center", valign: "middle" });
  });
  card(s, 2.12, 3.1, 3.02, 0.5, C.accent2);
  text(s, "Gạch nợ lỗi → hoàn tiền", { x: 2.12, y: 3.1, w: 3.02, h: 0.5, fontSize: 13, bold: true, color: C.text2, align: "center", valign: "middle" });
  text(s, [
    { text: "Mỗi bước idempotent theo mã giao dịch: gọi lại không trừ tiền hai lần", options: { bullet: true, breakLine: true } },
    { text: "Job đối soát mỗi 30 giây xử lý giao dịch treo khi service sập", options: { bullet: true, breakLine: true } },
    { text: "Mỗi bước ghi vào payment_events để kiểm toán", options: { bullet: true } },
  ], { x: 0.5, y: 3.85, w: 6.4, h: 1.2, fontSize: 13, paraSpaceAfter: 5 });
}

// ---------- 7. Concurrency ----------
{
  const s = slide(7, "CONTENT", "Concurrency: hai tình huống của đề bài");
  const cols = [
    [0.5, FIG.c51, "5.1 · Nhiều giao dịch, một tài khoản", "Khóa dòng tài khoản. Một thành công, một bị từ chối. Số dư không âm."],
    [5.1, FIG.c52, "5.2 · Nhiều tài khoản, một học phí", "Khóa dòng học phí. Một thành công, người còn lại được hoàn tiền."],
  ];
  for (const [x, fig, head, body] of cols) {
    text(s, head, { x, y: 1.1, w: 4.4, h: 0.3, fontSize: 14, bold: true, color: C.text2 });
    fit(s, fig, x, 1.5, 4.4, 2.5, head);
    card(s, x, 4.15, 4.4, 0.9);
    text(s, body, { x: x + 0.15, y: 4.15, w: 4.1, h: 0.9, fontSize: 12, valign: "middle" });
  }
}

// ---------- 8. Demo ----------
pres.addSection({ title: "Demo" }); section = "Demo";
{
  const s = slide(8, "DARK", "Demo hệ thống");
  text(s, "Hệ thống đang chạy thật: 11 container, PostgreSQL, email qua MailHog", { x: 0.6, y: 2.0, w: 4.6, h: 0.9, fontSize: 16, color: C.accent2 });
  const items = ["Luồng thanh toán thành công", "OTP sai và email biên lai", "Tình huống đồng thời 5.1 và 5.2", "Nhật ký saga và hoàn tiền", "Truy vết trên Jaeger"];
  items.forEach((t, i) => {
    const y = 0.9 + i * 0.75;
    card(s, 5.9, y, 3.6, 0.6, C.background1);
    text(s, t, { x: 6.1, y, w: 3.3, h: 0.6, fontSize: 14, color: C.text2, valign: "middle" });
  });
}

(async () => {
  const out = path.join(DOCS, "Slide.pptx");
  await pres.writeFile({ fileName: out });
  const skill = process.env.PPTX_SKILL;
  if (skill) await require(path.join(skill, "scripts/apply_theme.js")).applyTheme(out, THEME);
  else console.warn("Chưa đặt PPTX_SKILL: màu theme chưa được ghi vào file.");
  console.log(out);
})();
