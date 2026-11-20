// Run with: npm test   (Node's built-in test runner; Node 24 runs TypeScript directly)
import assert from "node:assert/strict";
import { test } from "node:test";
import { chartPrice, parsePriceText } from "./price.ts";

test("ranges plot at the midpoint and keep their ends", () => {
  assert.deepEqual(parsePriceText("₹200-₹400 per meal"), { value: 300, low: 200, high: 400 });
  assert.deepEqual(parsePriceText("₹1,299 – ₹1,869 per session"), { value: 1584, low: 1299, high: 1869 });
  assert.deepEqual(parsePriceText("Rs. 150 to 250 per box"), { value: 200, low: 150, high: 250 });
});

test("single prices, with or without qualifiers", () => {
  assert.deepEqual(parsePriceText("₹1,200 onwards per session"), { value: 1200 });
  assert.deepEqual(parsePriceText("₹40 per order (approx.)"), { value: 40 });
  assert.deepEqual(parsePriceText("INR 799"), { value: 799 });
});

test("no price when nothing is currency-marked", () => {
  assert.equal(parsePriceText("Not publicly listed"), null);
  assert.equal(parsePriceText("Custom quote, 500 ml bowls"), null);
  assert.equal(parsePriceText(""), null);
  assert.equal(parsePriceText(null), null);
});

test("the analyst's number wins; text fills the gap", () => {
  assert.deepEqual(chartPrice(200, "₹200 per order (approx.)"), { value: 200 });
  assert.deepEqual(chartPrice(null, "₹200-₹400 per meal"), { value: 300, low: 200, high: 400 });
  assert.deepEqual(chartPrice(250, "₹200-₹400 per meal"), { value: 250, low: 200, high: 400 });
  assert.deepEqual(chartPrice(999, "₹200-₹400 per meal"), { value: 999 });
  assert.equal(chartPrice(null, "Not publicly listed"), null);
});
