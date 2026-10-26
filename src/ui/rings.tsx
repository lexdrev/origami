// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Lighting } from "../backend";
import { useMessages } from "../i18n";
import { ringLook } from "../lighting";

interface RingsProps {
  lighting: Lighting;
  /** Rings the screen is changing; their labels light up. */
  editing?: { left: boolean; right: boolean };
}

/** Both stick rings as they light up now, so a change shows on the screen as well. */
export function Rings({ lighting, editing }: RingsProps) {
  const t = useMessages();
  const rings = [
    { key: "left", label: t.display.rings.left, rgb: lighting.left, active: editing?.left ?? false },
    { key: "right", label: t.display.rings.right, rgb: lighting.right, active: editing?.right ?? false },
  ];
  return (
    <div className="og-rings" aria-hidden="true">
      {rings.map(({ key, label, rgb, active }) => {
        const look = ringLook(lighting, rgb);
        return (
          <span key={key} className="og-ring">
            <span className="og-ring__face" style={{ opacity: look.opacity }}>
              <span
                className="og-ring__light"
                style={{ background: look.background, boxShadow: look.boxShadow, animation: look.animation }}
              />
              <span className="og-ring__gap" />
              <span className="og-ring__cap" />
            </span>
            <span className={active ? "og-ring__label og-ring__label--active" : "og-ring__label"}>{label}</span>
          </span>
        );
      })}
    </div>
  );
}
