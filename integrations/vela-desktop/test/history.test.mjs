import assert from "node:assert/strict";
import test from "node:test";

import { latestMessageByRole } from "../renderer/history.js";

test("finds the latest assistant message regardless of history order", () => {
  const newestFirst = [
    { role: "assistant", timestamp: 300, content: "new" },
    { role: "user", timestamp: 200, content: "request" },
    { role: "assistant", timestamp: 100, content: "old" }
  ];
  const oldestFirst = [...newestFirst].reverse();

  assert.equal(latestMessageByRole(newestFirst, "assistant")?.content, "new");
  assert.equal(latestMessageByRole(oldestFirst, "assistant")?.content, "new");
});

test("returns null when the requested role is absent", () => {
  assert.equal(latestMessageByRole([{ role: "user", timestamp: 1 }], "assistant"), null);
});
