#!/usr/bin/env python3
"""Choose a repeating interval and append transparent optical-flow transitions."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PET = SKILL_DIR / "assets" / "deskpet-app" / "pets" / "予愿安洁莉娜"
LOOP_STATES = ("idle", "move", "sit", "sleep")


def premultiplied(path):
    with Image.open(path) as image:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255
    rgba[:, :, :3] *= rgba[:, :, 3:4]
    return rgba


def choose_range(folder, count, fps):
    """Match recurring poses at least half a second apart; end is exclusive."""
    samples = []
    for index in range(count):
        with Image.open(folder / f"frame_{index:04d}.png") as image:
            rgba = (
                np.asarray(image.convert("RGBA").resize((160, 160)), dtype=np.float32)
                / 255
            )
        rgba[:, :, :3] *= rgba[:, :, 3:4]
        samples.append(rgba)
    minimum = max(2, round(fps * 0.5))
    if count <= minimum:
        return 0, count
    # Compare movement into the matching pose too, avoiding a return pose
    # reached in the opposite direction (e.g. the midpoint of a sway).
    candidates = []
    for start in range(1, count - minimum):
        for end in range(start + minimum, count):
            pose = np.abs(samples[start] - samples[end]).mean()
            velocity = np.abs(
                (samples[start] - samples[start - 1])
                - (samples[end] - samples[end - 1])
            ).mean()
            candidates.append((float(pose + velocity), start, end))
    if not candidates:
        return 0, count
    _, start, end = min(candidates)
    return start, end


def transition_frames(first, last, total):
    """Interpolate last -> first in premultiplied RGBA to preserve transparency."""
    alpha = np.maximum(first[:, :, 3], last[:, :, 3])
    ys, xs = np.where(alpha > 0)
    if not len(xs):
        for _ in range(total):
            yield Image.fromarray(np.zeros(first.shape, dtype=np.uint8))
        return
    x0, x1 = max(0, int(xs.min()) - 24), min(first.shape[1], int(xs.max()) + 25)
    y0, y1 = max(0, int(ys.min()) - 24), min(first.shape[0], int(ys.max()) + 25)
    a, b = last[y0:y1, x0:x1].copy(), first[y0:y1, x0:x1].copy()
    # DIS optical flow needs a sufficiently large image, including small pets.
    bottom, right = max(0, 16 - a.shape[0]), max(0, 16 - a.shape[1])
    a = np.pad(a, ((0, bottom), (0, right), (0, 0)))
    b = np.pad(b, ((0, bottom), (0, right), (0, 0)))

    def gray(rgba):
        rgb = rgba[:, :, :3] + (1 - rgba[:, :, 3:4]) * 0.5
        return cv2.cvtColor(np.uint8(np.clip(rgb * 255, 0, 255)), cv2.COLOR_RGB2GRAY)

    flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    forward = flow.calc(gray(a), gray(b), None)
    backward = flow.calc(gray(b), gray(a), None)
    yy, xx = np.mgrid[: a.shape[0], : a.shape[1]].astype(np.float32)
    for index in range(total):
        t = (index + 1) / (total + 1)
        warped_a = cv2.remap(
            a,
            xx - t * forward[:, :, 0],
            yy - t * forward[:, :, 1],
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )
        warped_b = cv2.remap(
            b,
            xx - (1 - t) * backward[:, :, 0],
            yy - (1 - t) * backward[:, :, 1],
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )
        rgba = np.zeros(first.shape, dtype=np.float32)
        rgba[y0:y1, x0:x1] = (warped_a * (1 - t) + warped_b * t)[: y1 - y0, : x1 - x0]
        np.divide(
            rgba[:, :, :3],
            rgba[:, :, 3:4],
            out=rgba[:, :, :3],
            where=rgba[:, :, 3:4] > 1e-6,
        )
        yield Image.fromarray(np.uint8(np.clip(rgba * 255, 0, 255)))


def prepare_pet(pet, states=LOOP_STATES, start=None, end=None, extra=3):
    pet = Path(pet)
    path = pet / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if extra < 0:
        raise ValueError("transition frame count must be nonnegative")
    if (start is not None or end is not None) and len(states) != 1:
        raise ValueError("select exactly one --state when specifying a loop interval")
    for state in states:
        if state not in manifest["states"]:
            if len(states) == 1:
                raise ValueError(f"state not found: {state}")
            continue
        info = manifest["states"][state]
        source_count = info.get("source_count", info["count"])
        folder = pet / "frames" / state
        if start is None and end is None:
            loop_start, loop_end = choose_range(folder, source_count, manifest["fps"])
        else:
            loop_start = 0 if start is None else start
            loop_end = source_count if end is None else end
        if not 0 <= loop_start < loop_end <= source_count:
            raise ValueError(
                f"invalid loop interval for {state}: {loop_start}:{loop_end}"
            )
        first = premultiplied(folder / f"frame_{loop_start:04d}.png")
        last = premultiplied(folder / f"frame_{loop_end - 1:04d}.png")
        if first.shape != last.shape:
            raise ValueError(f"frame sizes differ in {state}")
        # Never replace source frames. Re-running replaces only generated frames.
        if extra:
            for index, image in enumerate(transition_frames(first, last, extra)):
                image.save(folder / f"frame_{source_count + index:04d}.png")
        for index in range(source_count + extra, info["count"]):
            (folder / f"frame_{index:04d}.png").unlink(missing_ok=True)
        sequence = list(range(loop_start, loop_end)) + list(
            range(source_count, source_count + extra)
        )
        info.update(
            source_count=source_count,
            count=source_count + extra,
            loop_start=loop_start,
            loop_end=loop_end,
            loop_frames=sequence,
            loop_duration=round(len(sequence) * 1000 / manifest["fps"]),
        )
        # Include the added frames in the geometry used by the player.
        bbox = list(info["bbox"])
        for index in range(source_count, source_count + extra):
            with Image.open(folder / f"frame_{index:04d}.png") as image:
                box = image.getchannel("A").getbbox()
            if box:
                bbox = [
                    min(bbox[0], box[0]),
                    min(bbox[1], box[1]),
                    max(bbox[2], box[2] - 1),
                    max(bbox[3], box[3] - 1),
                ]
        info["bbox"] = bbox
        print(
            f"{state}: loop {loop_start}:{loop_end}, {extra} transitions, {len(sequence)} frames"
        )
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pet", type=Path, default=DEFAULT_PET, help="pet directory with manifest.json"
    )
    parser.add_argument(
        "--state",
        choices=LOOP_STATES,
        default=None,
        help="process one state; default processes all loop states",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="first frame, inclusive; default detects a recurring pose",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="last frame, exclusive; default detects a recurring pose",
    )
    parser.add_argument(
        "--transition-frames",
        type=int,
        default=3,
        help="extra frames connecting the end to the start; 0 disables interpolation",
    )
    args = parser.parse_args()
    states = (args.state,) if args.state else LOOP_STATES
    prepare_pet(args.pet, states, args.start, args.end, args.transition_frames)


if __name__ == "__main__":
    main()
