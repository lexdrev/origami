// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

const NBSP = "\u00a0";

export function formatNumber(value: number, locale: string, fractionDigits = 0): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

/** A number and its unit that never break across lines. */
export function withUnit(value: string, unit: string): string {
  return `${value}${NBSP}${unit}`;
}

export function pluralForm<T>(
  locale: string,
  count: number,
  forms: Partial<Record<Intl.LDMLPluralRule, T>> & { other: T },
): T {
  return forms[new Intl.PluralRules(locale).select(count)] ?? forms.other;
}
