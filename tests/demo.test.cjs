const { test } = require("node:test");
const assert = require("node:assert/strict");
const { join } = require("node:path");
const { reviewedExcerpts } = require(join(process.env.HUGBACK_TEST_BUILD, "demo-api.js"));
const { parseChat, SYNTHETIC_CHAT } = require(join(process.env.HUGBACK_TEST_BUILD, "chat-import.js"));

test("demo review preserves exact quotes, participants, dates and source indexes", () => {
  const preview = parseChat(SYNTHETIC_CHAT, "whatsapp");
  const result = reviewedExcerpts(preview, [1, 3], "Child", "Parent");
  assert.equal(result[0].sourceIndex, 1);
  assert.deepEqual(result[1], { ...preview.messages[3], sourceIndex: 3 });
  assert.equal(result[0].text, preview.messages[1].text);
  assert.equal("parentId" in result[0], false);
});
test("demo review rejects unreviewed, duplicated, oversized or unmapped input", () => {
  const preview = parseChat(SYNTHETIC_CHAT, "whatsapp");
  for (const indexes of [[], [0, 0], [-1], [2000], [0.5]]) {
    assert.throws(() => reviewedExcerpts(preview, indexes, "Child", "Parent"));
  }
  assert.throws(() => reviewedExcerpts(preview, [0], "Child", "Child"));
  assert.throws(() => reviewedExcerpts(preview, [0], "Stranger", "Parent"));
  preview.messages[0].text = "x".repeat(501);
  assert.throws(() => reviewedExcerpts(preview, [0], "Child", "Parent"));
});

const { recipientCallPayload, parentCallUrl } = require(join(process.env.HUGBACK_TEST_BUILD, "demo-api.js"));
const { importsForRecipient } = require(join(process.env.HUGBACK_TEST_BUILD, "portal-storage.js"));
const mother = { recipientId: "mother", revision: 3, busy: false, voice: { mode: "standard", profileId: null } };
const father = { recipientId: "father", revision: 1, busy: false, voice: { mode: "child", profileId: "child-profile" } };
const family = { recipients: [mother, father] };
const voice = { mode: "preset", replicatedTtsEnabled: true,
  profile: { id: "child-profile", enabled: true, expired: false, expiresAt: "2099-01-01T00:00:00Z" } };

test("recipient selection scopes calls while allowing the same authorized voice", () => {
  assert.deepEqual(recipientCallPayload(family, "mother", voice), {
    demoParent: true, demoRecipientId: "mother", demoRecipientRevision: 3,
  });
  assert.deepEqual(recipientCallPayload(family, "father", voice), {
    demoParent: true, demoRecipientId: "father", demoRecipientRevision: 1, voiceProfileId: "child-profile",
  });
  const shared = { recipients: [{ ...mother, voice: father.voice }, father] };
  assert.equal(recipientCallPayload(shared, "mother", voice).voiceProfileId, "child-profile");
  assert.equal(recipientCallPayload(shared, "father", voice).voiceProfileId, "child-profile");
});
test("recipient selector never defaults, accepts a foreign recipient, or silently replaces voices", () => {
  for (const id of [undefined, "", "foreign"]) assert.throws(() => recipientCallPayload(family, id, voice), /Choose a recipient/);
  assert.throws(() => recipientCallPayload({ recipients: [{ ...mother, busy: true }] }, "mother", voice), /active/);
  assert.throws(() => recipientCallPayload(family, "father", { ...voice, profile: { ...voice.profile, id: "replacement" } }), /unavailable/);
  assert.throws(() => recipientCallPayload(family, "father", { ...voice, profile: null }), /unavailable/);
  assert.throws(() => recipientCallPayload(family, "father", { ...voice, profile: { ...voice.profile, expired: true } }), /expired/);
  assert.equal(recipientCallPayload(family, "mother", { ...voice, profile: null }).voiceProfileId, undefined);
});
test("call links carry a recipient hint, never a provider key", () => {
  assert.equal(parentCallUrl("a&b"), "/call?recipient=a%26b");
  assert.equal(parentCallUrl(), "/call");
});
test("local preview listing isolates recipients, owners and unassigned legacy files", () => {
  const records = [
    { owner: "a", recipientId: "mother", id: "m" },
    { owner: "a", recipientId: "father", id: "f" },
    { owner: "a", id: "legacy" },
    { owner: "b", recipientId: "mother", id: "foreign" },
  ];
  assert.deepEqual(importsForRecipient(records, "a", "mother").map(r => r.id), ["m"]);
  assert.deepEqual(importsForRecipient(records, "a", "father").map(r => r.id), ["f"]);
  assert.deepEqual(importsForRecipient(records, "a").map(r => r.id), ["legacy"]);
  assert.deepEqual(importsForRecipient(records, "a", "old-parent", true).map(r => r.id), ["legacy"]);
});
