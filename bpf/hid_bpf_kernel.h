/* SPDX-FileCopyrightText: 2026 lexdrev */
/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * The few kernel types ORIGAMI's HID-BPF programs need, instead of a whole vmlinux.h.
 * Same layout as kernel 7.2.11-ogc4.1 (checked against its /sys/kernel/btf/vmlinux). libbpf matches
 * struct_ops members to the kernel's by name, so hid_bpf_ops keeps the kernel's names.
 */
#ifndef ORIGAMI_HID_BPF_KERNEL_H
#define ORIGAMI_HID_BPF_KERNEL_H

#include <stddef.h>
#include <linux/types.h>
#include <bpf/bpf_helpers.h>

enum hid_report_type {
	HID_INPUT_REPORT = 0,
	HID_OUTPUT_REPORT = 1,
	HID_FEATURE_REPORT = 2,
};

enum hid_class_request {
	HID_REQ_GET_REPORT = 1,
	HID_REQ_GET_IDLE = 2,
	HID_REQ_GET_PROTOCOL = 3,
	HID_REQ_SET_REPORT = 9,
	HID_REQ_SET_IDLE = 10,
	HID_REQ_SET_PROTOCOL = 11,
};

struct hid_device;

struct list_head {
	struct list_head *next;
	struct list_head *prev;
};

struct hid_bpf_ctx {
	struct hid_device *hid;
	__u32 allocated_size;
	union {
		__s32 retval;
		__s32 size;
	};
} __attribute__((preserve_access_index));

/* The loader writes the device's id into hid_id before loading, so it stays the first member. */
struct hid_bpf_ops {
	int hid_id;
	__u32 flags;
	struct list_head list;
	int (*hid_device_event)(struct hid_bpf_ctx *ctx, enum hid_report_type report_type, __u64 source);
	int (*hid_rdesc_fixup)(struct hid_bpf_ctx *ctx);
	int (*hid_hw_request)(struct hid_bpf_ctx *ctx, unsigned char reportnum, enum hid_report_type rtype,
			      enum hid_class_request reqtype, __u64 source);
	int (*hid_hw_output_report)(struct hid_bpf_ctx *ctx, __u64 source);
	struct hid_device *hdev;
};

extern __u8 *hid_bpf_get_data(struct hid_bpf_ctx *ctx, unsigned int offset, const size_t __sz) __ksym;

#endif
