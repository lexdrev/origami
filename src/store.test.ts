// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { latestOnly } from "./store";

describe("latestOnly", () => {
  it("sends the newest value after the one on its way, skipping those in between", async () => {
    const sent: number[] = [];
    let finish: () => void = () => undefined;
    const sender = latestOnly(async (value: number) => {
      sent.push(value);
      await new Promise<void>((resolve) => {
        finish = resolve;
      });
    });

    sender.send(1);
    sender.send(2);
    sender.send(3);
    finish();
    await Promise.resolve();
    await Promise.resolve();

    expect(sent).toEqual([1, 3]);
  });

  it("forgets a value that was not sent yet", async () => {
    const sent: number[] = [];
    let finish: () => void = () => undefined;
    const sender = latestOnly(async (value: number) => {
      sent.push(value);
      await new Promise<void>((resolve) => {
        finish = resolve;
      });
    });

    sender.send(1);
    sender.send(2);
    sender.drop();
    finish();
    await Promise.resolve();
    await Promise.resolve();

    expect(sent).toEqual([1]);
  });
});
