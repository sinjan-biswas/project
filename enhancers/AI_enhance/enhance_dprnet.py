# Copyright (c) 2026 Raspberry Pi Ltd.
# SPDX-License-Identifier: BSD-2-Clause

import argparse
from PIL import Image
from dprnet import DPRNet
import numpy as np

# Enhance an image using the DPRNet model.
#
# Patch size is taken from the model's input shape. Pre- and post-processing
# are minimal: input is normalised to [0, 1], then the network output is
# converted to uint8.
#
# If you're running out of memory, consider trying DPRNet_512.tflite instead of
# the default model (DPRNet_1024.tflite).

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance an image using the DPRNet model")
    parser.add_argument("input", type=str, help="Input image file (required)")
    parser.add_argument("output", type=str, help="Output image file (required)")
    parser.add_argument("--model", type=str, default="DPRNet_1024.tflite", help="Model file (default: DPRNet_1024.tflite)")
    parser.add_argument("--num-threads", type=int, default=4, help="Number of threads to use for inference")
    parser.add_argument("--gain", type=float, default=1.0, help="Gain factor for the brightness adjustment")
    parser.add_argument("--local-strength", type=float, default=0.5, help="Blend strength between original and enhanced (0-1), default is 0.5")
    parser.add_argument("--quality", type=int, default=95, help="Quality of the output image (0-100), default is 95")
    parser.add_argument("--compress-level", type=int, default=1,
        help="Compression level of PNG output images (0-9), default is 1")
    args = parser.parse_args()

    args.quality = max(0, min(args.quality, 100))
    args.compress_level = max(0, min(args.compress_level, 9))

    image = Image.open(args.input)
    image = np.array(image)

    dprnet = DPRNet(args.model, num_threads=args.num_threads)
    enhanced_image = dprnet.enhance(
        image,
        gain=args.gain,
        local_strength=args.local_strength,
    )
    enhanced_image = Image.fromarray(enhanced_image)
    enhanced_image.save(args.output, quality=args.quality, compress_level=args.compress_level)
