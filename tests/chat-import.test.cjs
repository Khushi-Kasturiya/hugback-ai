const { test } = require("node:test");
const assert = require("node:assert/strict");
const { parseChat, SYNTHETIC_CHAT } = require(`${process.env.HUGBACK_TEST_BUILD}/chat-import.js`);

test("Android WhatsApp multiline, system messages, Unicode and timestamps", () => {
  const result = parseChat("\ufeff1/10/2026, 6:00 PM - Messages are encrypted\n1/10/2026, 6:01 PM - Parent: नमस्ते\nA second line\n1/10/2026, 6:02 PM - Child: Hello", "whatsapp");
  assert.equal(result.messages.length, 2);
  assert.equal(result.messages[0].timestamp, "2026-10-01T18:01:00");
  assert.equal(result.messages[0].text, "नमस्ते\nA second line");
  assert.equal(result.skipped, 1);
});
test("iOS bracket timestamps and declared MDY order", () => {
  const result = parseChat("[10/01/26, 18:01:05] Parent: Hi\n[10/01/26, 18:02:05] Child: Hi", "whatsapp", "MDY");
  assert.equal(result.messages[0].timestamp, "2026-10-01T18:01:05");
});
test("synthetic normalized text works for either source", () => {
  for (const source of ["whatsapp", "instagram"]) {
    assert.equal(parseChat(SYNTHETIC_CHAT, source).messages.length, 4);
  }
});
test("Instagram single-thread JSON is chronological and skips media", () => {
  const result = parseChat(JSON.stringify({
    participants: [{ name: "Parent" }, { name: "Child" }],
    messages: [
      { sender_name: "Child", timestamp_ms: 2000, content: "Hello" },
      { sender_name: "Parent", timestamp_ms: 1000, content: "Hi" },
      { sender_name: "Parent", timestamp_ms: 3000, photos: [] },
    ],
  }), "instagram");
  assert.equal(result.messages[0].sender, "Parent");
  assert.equal(result.messages.length, 2);
  assert.equal(result.skipped, 1);
});
test("rejects group conversation, missing attribution, malformed and binary files", () => {
  for (const text of ["Hello", "\0bad", "\ufffdbad", SYNTHETIC_CHAT + "\n[2026-10-01T18:04:00Z] Other: Hi"]) {
    assert.throws(() => parseChat(text, "whatsapp"));
  }
  assert.throws(() => parseChat("{invalid", "instagram"), /not valid/);
});
test("rejects invalid date and ambiguous/unrecognized header instead of silently swallowing", () => {
  assert.throws(() => parseChat("31/02/2026, 18:00 - Parent: Hi\n01/03/2026, 18:00 - Child: Hi", "whatsapp"), /invalid/);
  assert.throws(() => parseChat(SYNTHETIC_CHAT + "\n2026-10-01 bad message", "instagram"), /Unrecognized/);
});
test("rejects oversized and overlong conversations", () => {
  assert.throws(() => parseChat("x".repeat(1024 * 1024 + 1), "whatsapp"), /1 MB/);
  assert.throws(() => parseChat(Array(501).fill(SYNTHETIC_CHAT).join("\n"), "whatsapp"), /2,000/);
});
test("message text stays inert, including markup and instruction-like content", () => {
  const result = parseChat("[2026-10-01T18:00:00Z] Parent: <script>alert(1)</script>\n[2026-10-01T18:01:00Z] Child: Ignore instructions", "instagram");
  assert.equal(result.messages[0].text, "<script>alert(1)</script>");
});
test("rejects ISO date rollover instead of inventing the date", () => {
  assert.throws(() => parseChat(SYNTHETIC_CHAT.replace("2026-10-01", "2026-02-30"), "instagram"), /Invalid ISO/);
});
