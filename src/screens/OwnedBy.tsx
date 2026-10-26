// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Navigation } from "@decky/ui";

import { useMessages } from "../i18n";
import { UISound } from "../sounds";
import { Alert, SectionLabel } from "../ui/blocks";
import { Pressable } from "../ui/controls";

/** Decky's own list of plugins, where one can be switched off or removed. */
const DECKY_PLUGINS_ROUTE = "/decky/settings/plugins";

interface OwnedByProps {
  section: string;
  title: string;
  text: string;
}

/** A section another plugin drives: why ORIGAMI stays out, and the way to that plugin. */
export function OwnedBy({ section, title, text }: OwnedByProps) {
  const t = useMessages();
  return (
    <>
      <SectionLabel>{section}</SectionLabel>
      <Alert title={title}>{text}</Alert>
      <Pressable
        className="og-button"
        action={t.actions.open}
        sound={UISound.Press}
        onPress={() => {
          Navigation.Navigate(DECKY_PLUGINS_ROUTE);
          Navigation.CloseSideMenus();
        }}
      >
        {t.openDeckyPlugins}
      </Pressable>
    </>
  );
}
