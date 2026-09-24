# Copyright (c) 2026 Raspberry Pi Ltd.
# SPDX-License-Identifier: BSD-2-Clause

from math import log
import cv2
import numpy as np

from network import Network


class DPRNet:
    """DPRNet model for image enhancement.

    Applies a DPRNet TFLite model to enhance images. Patch size is taken from
    the model's input tensor shape. Pre- and post-processing are minimal:
    input is normalised to [0, 1], then the network output is converted to uint8.
    """

    def __init__(
        self,
        model_path: str,
        batch_size: int = 1,
        num_threads: int = 4,
    ) -> None:
        """Initialize the DPRNet enhancer with a pre-trained model.

        Args:
            model_path: Path to the pre-trained TFLite model file.
            batch_size: Number of patches to process simultaneously. Defaults to 1.
            num_threads: Number of CPU threads for inference. Defaults to 4.
        """
        self.network = Network(
            model_path,
            patch_size=None,
            batch_size=batch_size,
            num_threads=num_threads,
            channel_first=True,
        )

    def _prepare_image(self, image: np.ndarray) -> np.ndarray:
        """Prepare the input image by normalising to [0, 1].

        Args:
            image: Input RGB image as uint8 or uint16 array with shape (H, W, 3).

        Returns:
            Prepared image as float32 array .
        """
        if image.dtype == np.uint16:
            max_val = 65535.0
        else:
            max_val = 255.0
        return image.astype(np.float32) / max_val

    def _run_network(
        self,
        image: np.ndarray,
        overlap_pixels: int = 16,
        show_progress: bool = False,
    ) -> np.ndarray:
        """Run the neural network on the prepared image.

        Args:
            image: Prepared image as float32 array.
            overlap_pixels: Number of pixels to overlap between adjacent patches
                to reduce seam artifacts. Defaults to 16.
            show_progress: If True, display a progress bar during inference.
                Defaults to False.

        Returns:
            Network output as float32 array.
        """
        return self.network.run_inference(image, overlap_pixels, show_progress)

    def _finish_image(self, image: np.ndarray) -> np.ndarray:
        """Convert the network output to uint8.

        Args:
            image: Network output as float32 array.

        Returns:
            Image as uint8 array with shape (H, W, C).
        """
        return np.clip(image * 255, 0, 255).astype(np.uint8)

    def enhance(
        self,
        image: np.ndarray,
        overlap_pixels: int = 128,
        gain: float = 1.0,
        local_strength: float = 0.5,
    ) -> np.ndarray:
        """Enhance an image using the DPRNet model.

        Args:
            image: Input RGB image as uint8 array with shape (H, W, 3).
            overlap_pixels: Number of pixels to overlap between adjacent patches
                to reduce seam artifacts. Defaults to 16.
            show_progress: If True, display a progress bar during inference.
                Defaults to False.
            gain: Gain factor for the brightness adjustment. Defaults to 1.0.
            local_strength: Blend between original and enhanced (0-1). Defaults to 0.5.

        Returns:
            Enhanced RGB image as uint8 array with shape (H, W, 3).
        """
        image = self._prepare_image(image)
        patch_size = (self.network.patch_size[1], self.network.patch_size[0])
        image_size = (image.shape[1], image.shape[0])
        downscaled = cv2.resize(image, patch_size, interpolation=cv2.INTER_LINEAR)
        upscaled = cv2.resize(downscaled, image_size, interpolation=cv2.INTER_LINEAR)
        output = self._run_network(downscaled, overlap_pixels, False)
        eps = 1e-6
        # First make sure it's not darkening any pixels, which could create weird
        # effects in saturated image areas.
        ratios = (output + eps) / (downscaled + eps)
        ratios = np.maximum(ratios, 1.0)
        output = downscaled * ratios
        output = cv2.resize(output, image_size, interpolation=cv2.INTER_LINEAR)
        # Now try to add back some of the full resolution detail.
        ratios = (image + eps) / (upscaled + eps)
        output = output * ratios
        # Now create a version without such aggressive local contrast boosting, so
        # that we can blend the two versions together.
        output_mean = np.mean(output)
        gain = gain if gain > 1.0 else gain * gain
        image_mean = np.mean(image) * gain
        gamma = (log(output_mean / image_mean) + 1) / 2
        image = image ** gamma
        # And the final mixture of the two:
        output = local_strength * output + (1 - local_strength) * image
        return self._finish_image(output)
