/**
 * Numbers for the price chart.
 *
 * The Strategy Analyst stores a numeric `price_value`, but leaves it empty for prices it
 * can't reduce to one number, such as ranges ("₹200-₹400 per meal"). Those competitors do
 * publish a price, so the chart reads the number(s) back out of the price text instead of
 * treating them as unpriced. Only currency-marked amounts count, so "500 ml" or "2 meals"
 * are never mistaken for prices.
 */

export interface ChartPrice {
  /** Plotted position: the price, or the midpoint of a range. */
  value: number;
  /** Set for a range: its ends, for drawing the range bar. */
  low?: number;
  high?: number;
}

const CURRENCY = String.raw`(?:₹|rs\.?|inr|\$)`;
const AMOUNT = String.raw`(\d[\d,]*(?:\.\d+)?)`;
const RANGE = new RegExp(
  String.raw`${CURRENCY}?\s*${AMOUNT}\s*(?:-|–|—|to)\s*${CURRENCY}?\s*${AMOUNT}`,
  "i",
);
const SINGLE = new RegExp(String.raw`${CURRENCY}\s*${AMOUNT}`, "i");
const HAS_CURRENCY = new RegExp(CURRENCY, "i");

const num = (s: string) => Number(s.replace(/,/g, ""));

export function parsePriceText(text: string | null | undefined): ChartPrice | null {
  if (!text || !HAS_CURRENCY.test(text)) return null;
  const range = RANGE.exec(text);
  if (range) {
    const a = num(range[1]);
    const b = num(range[2]);
    const low = Math.min(a, b);
    const high = Math.max(a, b);
    if (low > 0 && high > low) return { value: (low + high) / 2, low, high };
    if (low > 0 && high === low) return { value: low };
  }
  const single = SINGLE.exec(text);
  if (single) {
    const v = num(single[1]);
    if (v > 0) return { value: v };
  }
  return null;
}

/** The numeric price wins when the analyst gave one; otherwise fall back to the text. */
export function chartPrice(priceValue: number | null | undefined, priceText: string | null | undefined): ChartPrice | null {
  if (typeof priceValue === "number" && priceValue > 0) {
    const fromText = parsePriceText(priceText);
    // Keep the range bar when the analyst picked a value inside a range it was given.
    if (fromText?.low !== undefined && priceValue >= fromText.low && priceValue <= fromText.high!) {
      return { value: priceValue, low: fromText.low, high: fromText.high };
    }
    return { value: priceValue };
  }
  return parsePriceText(priceText);
}
