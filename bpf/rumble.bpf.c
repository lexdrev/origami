// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Rumble of the ROG Xbox Ally X as a game means it: impulse triggers (BUGS.md, B19) and grip strength.
 *
 * InputPlumber 0.83 sends the rumble report 0x0D with both trigger motors at 0, and Steam asks for
 * every rumble at -5 dB, so a game's full rumble reaches a grip as about 32 of 100. On its way to the
 * controller this program fills each trigger from the grip motor on its side and lifts the grips,
 * both scaled by the strengths ORIGAMI keeps in the settings map. Reports that already drive a
 * trigger (Steam's haptic pulses, ORIGAMI's trigger test) keep their triggers.
 *
 * A game's rumble jumps with every shot (29, 22, 19, 28, ... every 10-60 ms), which makes a trigger
 * rough. A trigger follows a rise at once but falls no faster than RELEASE_PER_SECOND, and goes off
 * as soon as its grip does: the controller keeps any rumble until told otherwise.
 *
 * The gamepad interface has no interrupt OUT endpoint, so a hidraw write ends up as SET_REPORT:
 * the report is changed in hid_hw_request. ORIGAMI attaches the program only to that interface,
 * after checking that its report descriptor lays the report out as below.
 */

#include "hid_bpf_kernel.h"
#include <bpf/bpf_tracing.h>
#include <linux/bpf.h>

#define RUMBLE_REPORT		0x0D
#define RUMBLE_REPORT_SIZE	9
#define ALL_MOTORS		0x0F
/* Report bytes: id, enabled motors, left trigger, right trigger, left grip, right grip, timing. */
#define LEFT_TRIGGER		2
#define RIGHT_TRIGGER		3
#define LEFT_GRIP		4
#define RIGHT_GRIP		5
#define MAX_STRENGTH		100

/* InputPlumber gives a grip about 31 for a game's full rumble (Steam sends -5 dB). */
#define GAME_FULL		32

/* Between reports a trigger's strength is kept in 1/256 of a percent. */
#define FINE			256
#define RELEASE_PER_SECOND	40
#define NS_PER_RELEASE_STEP	(1000000000ULL / (RELEASE_PER_SECOND * FINE))

enum side {
	LEFT,
	RIGHT,
	SIDES,
};

/*
 * Strengths at a game's full rumble, in percent: of each trigger, where 0 keeps it still, and of
 * the grips, where 0 leaves them as the game sent them.
 */
struct rumble_settings {
	__u8 left_trigger;
	__u8 right_trigger;
	__u8 grips;
};

struct envelope {
	__u64 at_ns;
	__u32 level;
};

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, struct rumble_settings);
} settings SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, SIDES);
	__type(key, __u32);
	__type(value, struct envelope);
} envelopes SEC(".maps");

static __u32 scaled(__u8 grip, __u8 strength)
{
	__u32 value = grip * strength / GAME_FULL;

	return value < MAX_STRENGTH ? value : MAX_STRENGTH;
}

static __u8 trigger_strength(__u32 side, __u8 grip, __u8 setting)
{
	struct envelope *envelope = bpf_map_lookup_elem(&envelopes, &side);
	__u32 strength = scaled(grip, setting);
	__u64 now = bpf_ktime_get_ns();
	__u64 fall;
	__u32 level;

	if (!envelope)
		return strength;

	fall = (now - envelope->at_ns) / NS_PER_RELEASE_STEP;
	level = envelope->level > fall ? envelope->level - fall : 0;
	if (!strength)
		level = 0;
	else if (strength * FINE > level)
		level = strength * FINE;

	envelope->at_ns = now;
	envelope->level = level;
	return level / FINE;
}

SEC("struct_ops/hid_hw_request")
int BPF_PROG(origami_rumble, struct hid_bpf_ctx *hctx, unsigned char reportnum,
	     enum hid_report_type rtype, enum hid_class_request reqtype, __u64 source)
{
	struct rumble_settings *strength;
	__u8 left_grip, right_grip;
	__u32 key = 0;
	__u8 *data;

	if (reportnum != RUMBLE_REPORT || rtype != HID_OUTPUT_REPORT || reqtype != HID_REQ_SET_REPORT)
		return 0;

	strength = bpf_map_lookup_elem(&settings, &key);
	if (!strength || (!strength->left_trigger && !strength->right_trigger && !strength->grips))
		return 0;

	data = hid_bpf_get_data(hctx, 0, RUMBLE_REPORT_SIZE);
	if (!data || data[0] != RUMBLE_REPORT || data[1] != ALL_MOTORS)
		return 0;

	/* The triggers follow the grips as the game sent them, before the grips are lifted. */
	left_grip = data[LEFT_GRIP];
	right_grip = data[RIGHT_GRIP];
	if (!data[LEFT_TRIGGER] && !data[RIGHT_TRIGGER]) {
		data[LEFT_TRIGGER] = trigger_strength(LEFT, left_grip, strength->left_trigger);
		data[RIGHT_TRIGGER] = trigger_strength(RIGHT, right_grip, strength->right_trigger);
	}
	if (strength->grips) {
		data[LEFT_GRIP] = scaled(left_grip, strength->grips);
		data[RIGHT_GRIP] = scaled(right_grip, strength->grips);
	}
	return 0;
}

SEC(".struct_ops.link")
struct hid_bpf_ops rumble_ops = {
	.hid_hw_request = (void *)origami_rumble,
};

char _license[] SEC("license") = "GPL";
