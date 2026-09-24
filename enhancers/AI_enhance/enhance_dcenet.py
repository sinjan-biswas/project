# Copyright (c) 2026 Raspberry Pi Ltd.
# SPDX-License-Identifier: BSD-2-Clause

import argparse
from PIL import Image
from zero_dce import ZeroDCE
import numpy as np

# Enhance an image using the Zero-DCE algorithm.
#
# Mostly this is for dark or low-light images, which will be brightened, but it can be used
# for other images as well.
#
# The principal controls over the output include:
# - The gain parameter, which can be used to create brighter or darker outputs.
# - The local-strength parameter, which will allow very dark areas to be brighted a bit more, and
#   very bright areas a bit less. It's not a very sophisticated effect, but may be useful.
#
# The batch-size parameter doesn't seem to have a big effect on the runtime, but the patch-size is
# important to reduce the memory usage.
#
# The algorithm is based on the paper "Zero-Reference Deep Curve Estimation for Low-Light Image Enhancement"
# by Guo, Li et al. (https://arxiv.org/pdf/2001.06826).

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance an image using the Zero-DCE algorithm")
    parser.add_argument("input", type=str, help="Input image file (required)")
    parser.add_argument("output", type=str, help="Output image file (required)")
    parser.add_argument("--model", type=str, default="dcenet.tflite", help="Model file (default: dcenet.tflite)")
    parser.add_argument("--patch-size", type=int, default=256,
        help="Size of patches in which the image is processed (default: 256). 0 means use the image size.")
    parser.add_argument("--batch-size", type=int, default=1, help="Number of patches to process in each batch")
    parser.add_argument("--num-threads", type=int, default=4, help="Number of threads to use for inference")
    parser.add_argument("--overlap-pixels", type=int, default=16,
        help="Number of pixels to overlap between patches (default: 16)")
    parser.add_argument("--hide-progress", action="store_true", default=False, help="Hide progress bar")
    parser.add_argument("--gain", type=float, default=1.0, help="Gain factor for the brightness adjustment")
    parser.add_argument("--local-strength", type=float, default=0.25, help="Strength of the local brightness adjustment")
    parser.add_argument("--quality", type=int, default=95, help="Quality of the output image (0-100), default is 95")
    parser.add_argument("--compress-level", type=int, default=1,
        help="Compression level of PNG output images (0-9), default is 1")
    args = parser.parse_args()

    args.quality = max(0, min(args.quality, 100))
    args.compress_level = max(0, min(args.compress_level, 9))

    image = Image.open(args.input)
    image = np.array(image)
    if args.patch_size:
        patch_size = (min(args.patch_size, image.shape[0]), min(args.patch_size, image.shape[1]))
    else:
        patch_size = image.shape[:2]

    zero_dce = ZeroDCE(args.model, patch_size, args.batch_size, args.num_threads)
    enhanced_image = zero_dce.enhance(image, gain=args.gain, local_strength=args.local_strength,
        overlap_pixels=args.overlap_pixels, show_progress=not args.hide_progress)
    enhanced_image = Image.fromarray(enhanced_image)
    enhanced_image.save(args.output, quality=args.quality, compress_level=args.compress_level)