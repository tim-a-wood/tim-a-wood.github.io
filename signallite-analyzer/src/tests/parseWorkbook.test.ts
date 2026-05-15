import { describe, it, expect } from "vitest";
import { validateFile, validateSheets } from "../xlsx/validateWorkbook";
import type { ParsedSheets } from "../xlsx/validateWorkbook";

describe("validateFile", () => {
  it("returns error for non-xlsx file", () => {
    const file = { name: "data.csv", size: 1000 } as File;
    expect(validateFile(file)).toMatch(/XLSX/i);
  });

  it("returns error for oversized file", () => {
    const file = { name: "data.xlsx", size: 21 * 1024 * 1024 } as File;
    expect(validateFile(file)).toMatch(/20 MB/i);
  });

  it("returns null for valid file", () => {
    const file = { name: "data.xlsx", size: 1024 } as File;
    expect(validateFile(file)).toBeNull();
  });
});

describe("validateSheets", () => {
  it("returns error when Case column is missing", () => {
    const sheets: ParsedSheets = {
      dataRows: [{ GrossWeight: 70000 }],
      dataHeaders: ["GrossWeight"],
      groups: null,
      variables: null,
    };
    const errors = validateSheets(sheets);
    expect(errors.some(e => e.includes("Case"))).toBe(true);
  });

  it("returns error for duplicate Case values", () => {
    const sheets: ParsedSheets = {
      dataRows: [{ Case: 1 }, { Case: 1 }],
      dataHeaders: ["Case"],
      groups: null,
      variables: null,
    };
    const errors = validateSheets(sheets);
    expect(errors.some(e => e.includes("Duplicate") || e.includes("duplicate"))).toBe(true);
  });

  it("returns error for non-numeric Case value", () => {
    const sheets: ParsedSheets = {
      dataRows: [{ Case: "not-a-number" }],
      dataHeaders: ["Case"],
      groups: null,
      variables: null,
    };
    const errors = validateSheets(sheets);
    expect(errors.some(e => e.includes("finite") || e.includes("not a finite"))).toBe(true);
  });

  it("returns no errors for valid data", () => {
    const sheets: ParsedSheets = {
      dataRows: [{ Case: 1 }, { Case: 2 }, { Case: 3 }],
      dataHeaders: ["Case"],
      groups: null,
      variables: null,
    };
    const errors = validateSheets(sheets);
    expect(errors).toHaveLength(0);
  });
});
