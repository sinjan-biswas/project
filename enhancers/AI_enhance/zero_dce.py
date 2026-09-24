# Copyright (c) 2026 Raspberry Pi Ltd.
# SPDX-License-Identifier: BSD-2-Clause

import numpy as np
import cv2

from network import Network

class ZeroDCE:
    """Zero-Reference Deep Curve Estimation for low-light image enhancement.

    This class implements the Zero-DCE algorithm which enhances low-light images
    without requiring paired training data. It uses learned curve parameters to
    iteratively adjust pixel values for improved visibility and contrast.

    Attributes:
        network: The neural network used for inference to predict enhancement curves.
    """

    def __init__(
        self, model_path: str,
        patch_size: tuple[int, int] = (256, 256),
        batch_size: int = 1,
        num_threads: int = 4
        ) -> None:
        """Initialize the ZeroDCE enhancer with a pre-trained model.

        Args:
            model_path: Path to the pre-trained TFLite model file.
            patch_size: Size of patches (height, width) for processing large images.
                Defaults to (256, 256).
            batch_size: Number of patches to process simultaneously. Defaults to 1.
            num_threads: Number of CPU threads for inference. Defaults to 4.
        """
        self.network = Network(model_path, patch_size, batch_size, num_threads)

    def _prepare_image(self, image: np.ndarray, gain: float = 1.0, local_strength: float = 0.25) -> np.ndarray:
        """Prepare the input image by normalizing and adding a brightness channel.

        This method normalizes the image to [0, 1] range and computes a brightness
        map that is appended as a fourth channel. The brightness map helps guide
        the enhancement by providing spatial illumination information.

        Args:
            image: Input RGB image as uint8 array with shape (H, W, 3).
            gain: Controls overall brightness boost. Higher values result in
                brighter output. Defaults to 1.0.
            local_strength: Balance between local and global brightness estimation.
                0.0 uses only global mean, 1.0 uses only local values.
                Defaults to 0.25.

        Returns:
            Prepared image as float32 array with shape (H, W, 4), where the fourth
            channel contains the brightness guidance map.
        """
        image = image.astype(np.float32) / 255.0
        h, w = image.shape[:2]

        brightness_image = np.mean(image, axis=-1, keepdims=True)
        sz = (4, 4)

        brightness_image = cv2.resize(brightness_image, sz, interpolation=cv2.INTER_LINEAR)
        brightness_image = brightness_image[..., np.newaxis]

        brightness = np.mean(brightness_image)
        brightness_image = brightness_image * local_strength + brightness * (1 - local_strength)
        brightness_image = np.minimum(brightness_image / gain, 0.5)

        brightness_image = cv2.resize(brightness_image, (w, h), interpolation=cv2.INTER_LINEAR)
        if len(brightness_image.shape) == 2:
            brightness_image = brightness_image[..., np.newaxis]

        image = np.concatenate([image, brightness_image], axis=-1)
        return image

    def _run_network(self, image: np.ndarray, overlap_pixels: int = 16, show_progress: bool = False) -> np.ndarray:
        """Run the neural network to predict enhancement curve parameters.

        Args:
            image: Prepared image as float32 array with shape (H, W, 4).
            overlap_pixels: Number of pixels to overlap between adjacent patches
                to reduce seam artifacts. Defaults to 16.
            show_progress: If True, display a progress bar during inference.
                Defaults to False.

        Returns:
            Enhancement parameters as float32 array with shape (H, W, 24),
            containing 8 sets of RGB curve parameters (3 channels x 8 iterations).
        """
        return self.network.run_inference(image, overlap_pixels, show_progress)

    def _finish_image(self, image: np.ndarray, output_params: np.ndarray) -> np.ndarray:
        """Apply the predicted curve parameters to enhance the image.

        This method applies 8 iterations of pixel-wise curve adjustments using
        the formula: I' = I + r * (I^2 - I), where r is the learned curve
        parameter. Each iteration progressively refines the enhancement.

        Args:
            image: Prepared image as float32 array with shape (H, W, 4).
                Only the first 3 channels (RGB) are used for enhancement.
            output_params: Enhancement parameters as float32 array with shape
                (H, W, 24), containing 8 sets of RGB curve parameters.

        Returns:
            Enhanced RGB image as uint8 array with shape (H, W, 3),
            with pixel values clipped to [0, 255].
        """
        r1 = output_params[:, :, :3]
        r2 = output_params[:, :, 3:6]
        r3 = output_params[:, :, 6:9]
        r4 = output_params[:, :, 9:12]
        r5 = output_params[:, :, 12:15]
        r6 = output_params[:, :, 15:18]
        r7 = output_params[:, :, 18:21]
        r8 = output_params[:, :, 21:24]
        image= image[..., :3]
        image = image + r1 * (np.square(image) - image)
        image = image + r2 * (np.square(image) - image)
        image = image + r3 * (np.square(image) - image)
        image = image + r4 * (np.square(image) - image)
        image = image + r5 * (np.square(image) - image)
        image = image + r6 * (np.square(image) - image)
        image = image + r7 * (np.square(image) - image)
        image = image + r8 * (np.square(image) - image)

        image = image * 255.0
        image = image.clip(0.0, 255.0)
        image = image.astype(np.uint8)
        return image

    def enhance(
            self, image: np.ndarray, gain: float = 1.0, local_strength: float = 0.25,
            overlap_pixels: int = 16, show_progress: bool = False
            ) -> np.ndarray:
        """Enhance a low-light image using the Zero-DCE algorithm.

        This is the main entry point for image enhancement. It prepares the input
        image, runs neural network inference to predict enhancement curves, and
        applies those curves to produce the final enhanced image.

        Args:
            image: Input RGB image as uint8 array with shape (H, W, 3).
            gain: Controls overall brightness boost. Higher values result in
                brighter output. Defaults to 1.0.
            local_strength: Balance between local and global brightness estimation.
                0.0 uses only global mean, 1.0 uses only local values.
                Defaults to 0.25.
            overlap_pixels: Number of pixels to overlap between adjacent patches
                to reduce seam artifacts when processing large images.
                Defaults to 16.
            show_progress: If True, display a progress bar during inference.
                Defaults to False.

        Returns:
            Enhanced RGB image as uint8 array with shape (H, W, 3).

        Example:
            >>> model = ZeroDCE("dcenet.tflite")
            >>> image = np.array(Image.open("dark_image.jpg"))
            >>> enhanced = model.enhance(image)
            >>> Image.fromarray(enhanced).save("enhanced_image.jpg")
        """
        image = self._prepare_image(image, gain, local_strength)
        output_params = self._run_network(image, overlap_pixels, show_progress)
        return self._finish_image(image, output_params)
