// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Router, type FocusableProps } from "@decky/ui";

// Steam's ESideMenu and QuickAccessTab values ORIGAMI uses; @decky/ui has them only as types.
export const SideMenu = { None: 0, QuickAccess: 2 } as const;
export const QuickAccessTab = { Performance: 5, Decky: 999 } as const;

/** Key of ORIGAMI's own tab in the quick access menu ("ORG" in ASCII). Steam's tabs use 0–7, Decky 999. */
export const ORIGAMI_TAB = 0x4f5247;

/** Steam's main window, whose menu store opens and closes the quick access menu. */
export const mainWindow = () => Router.WindowStore.GamepadUIMainWindowInstance;

type SteamTab = NonNullable<Parameters<ReturnType<typeof mainWindow>["MenuStore"]["OpenQuickAccessMenu"]>[0]>;

// How Steam picks the focus coming into a group (NavEntryPositionPreferences): the child marked
// preferredFocus. @decky/ui has the enum only as a type.
// eslint-disable-next-line @typescript-eslint/no-unsafe-enum-assignment
export const ENTER_PREFERRED_CHILD: NonNullable<FocusableProps["navEntryPreferPosition"]> = 4;

// @decky/ui has Steam's tab enum only as a type, listing Steam's own tabs; Steam opens any tab
// in its list by its key, ORIGAMI's and Decky's too.
// eslint-disable-next-line @typescript-eslint/no-unsafe-enum-assignment
export const steamTab = (key: number): SteamTab => key;
