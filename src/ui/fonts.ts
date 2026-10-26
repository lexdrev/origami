// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import monoCyrillic500 from "@fontsource/jetbrains-mono/files/jetbrains-mono-cyrillic-500-normal.woff2";
import monoCyrillic700 from "@fontsource/jetbrains-mono/files/jetbrains-mono-cyrillic-700-normal.woff2";
import monoLatin500 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-500-normal.woff2";
import monoLatin700 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-700-normal.woff2";
import sansCyrillic400 from "@fontsource/ibm-plex-sans/files/ibm-plex-sans-cyrillic-400-normal.woff2";
import sansCyrillic700 from "@fontsource/ibm-plex-sans/files/ibm-plex-sans-cyrillic-700-normal.woff2";
import sansLatin400 from "@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff2";
import sansLatin700 from "@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-700-normal.woff2";

// IBM Plex Sans and JetBrains Mono (both SIL OFL 1.1), Latin and Cyrillic subsets.
// Own family names keep them apart from fonts other plugins may declare.
export const SANS = "OrigamiSans";
export const MONO = "OrigamiMono";

const LATIN =
  "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329," +
  "U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD";
const CYRILLIC = "U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116";

function face(family: string, weight: number, url: string, range: string): string {
  return (
    `@font-face{font-family:"${family}";font-style:normal;font-weight:${weight};` +
    `font-display:block;src:url("${url}") format("woff2");unicode-range:${range}}`
  );
}

export const fontFaces = [
  face(SANS, 400, sansLatin400, LATIN),
  face(SANS, 400, sansCyrillic400, CYRILLIC),
  face(SANS, 700, sansLatin700, LATIN),
  face(SANS, 700, sansCyrillic700, CYRILLIC),
  face(MONO, 500, monoLatin500, LATIN),
  face(MONO, 500, monoCyrillic500, CYRILLIC),
  face(MONO, 700, monoLatin700, LATIN),
  face(MONO, 700, monoCyrillic700, CYRILLIC),
].join("\n");
