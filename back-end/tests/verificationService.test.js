const assert = require("node:assert/strict");
const test = require("node:test");
const { verifyContent } = require("../services/verificationService");

test("verification service fails closed without a verdict or confidence", async () => {
  const originalRandom = Math.random;
  Math.random = () => {
    throw new Error("random output is forbidden");
  };

  try {
    const result = await verifyContent({
      type: "text",
      content: "Breaking shocking claim",
    });

    assert.equal(result.status, "unavailable");
    assert.equal(result.isMock, true);
    assert.equal(result.evidenceStatus, "not_implemented");
    assert.equal(result.verdict, null);
    assert.equal(result.confidence, null);
    assert.equal(result.confidenceSemantics, "not_available");
    assert.equal(result.label, "Verification unavailable");
    assert.deepEqual(result.reasoning, []);
  } finally {
    Math.random = originalRandom;
  }
});

test("URL and filename heuristics do not change the unavailable response", async () => {
  const textResult = await verifyContent({
    type: "text",
    content: "government hiding secret miracle",
  });
  const trustedUrlResult = await verifyContent({
    type: "website",
    content: "https://reuters.com/example",
  });
  const fileResult = await verifyContent({
    type: "image",
    file: { originalname: "breaking-claim.png" },
  });

  for (const result of [textResult, trustedUrlResult, fileResult]) {
    assert.equal(result.status, "unavailable");
    assert.equal(result.verdict, null);
    assert.equal(result.confidence, null);
  }
});
