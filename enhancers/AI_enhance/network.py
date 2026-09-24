# Copyright (c) 2026 Raspberry Pi Ltd.
# SPDX-License-Identifier: BSD-2-Clause

from ai_edge_litert.interpreter import Interpreter
import numpy as np
from tqdm import tqdm

class Network:
    """
    A class to represent a neural network model implemented in TFLite.

    The underlying TFLite model is expected to take rectangular patches of pixels as input, and return
    patches of the same size as output. The Network wrapper takes care of splitting an image
    into patches, padding them as necessary at the edges, running them through the neural network,
    and finally reassembling all the patches for the output image.

    Depending on the network, the inputs and outputs may have different numbers of channels (features),
    but their spatial dimensions will match.
    """

    def __init__(
            self, model_path: str,
            patch_size: tuple[int, int] | None = (256, 256),
            batch_size: int = 1,
            num_threads: int = 4,
            channel_first: bool = False,
            ) -> None:
        """
        Initialize the Network object by loading the TFLite model.

        Args:
            model_path (str): Path to the TFLite model file
            patch_size (tuple[int, int] | None): Size of the patches to process (height, width).
                If None, taken from the model's input tensor shape.
            batch_size (int): Number of patches to process in each batch
            num_threads (int): Number of threads to use for inference
            channel_first (bool): If True, the network expects input/output layout (B, C, H, W);
                if False, layout is (B, H, W, C). Default False.
        """
        if not model_path.endswith(".tflite"):
            raise ValueError("Model path must end with .tflite")
        self.channel_first = channel_first
        self.interpreter = Interpreter(model_path, num_threads=num_threads)
        input_shape = list(self.interpreter.get_input_details()[0]['shape'])
        if patch_size is None:
            if channel_first:
                # Shape is [B, C, H, W]
                patch_size = (input_shape[2], input_shape[3])
            else:
                # Shape is [B, H, W, C]
                patch_size = (input_shape[1], input_shape[2])
        input_shape[0] = batch_size
        if channel_first:
            # Shape is [B, C, H, W]
            input_shape[2] = patch_size[0]
            input_shape[3] = patch_size[1]
        else:
            # Shape is [B, H, W, C]
            input_shape[1] = patch_size[0]
            input_shape[2] = patch_size[1]
        self.interpreter.resize_tensor_input(0, input_shape)
        self.interpreter.allocate_tensors()
        self.patch_size = patch_size
        self.batch_size = batch_size

    def _calculate_patch_info(
            self,
            image_shape: tuple[int, int, int],
            overlap_pixels: int
            ) -> tuple[int, int, int, int, int]:
        """
        Calculate the number of patches and padding required to split an image into overlapping patches.

        Args:
            image_shape: Tuple of (height, width, channels) of the input image
            overlap_pixels: Number of pixels to overlap between patches

        Returns:
            Tuple of (stride_w, stride_h, num_patches_w, num_patches_h, width_padded, height_padded) where:
            - stride_w: The horizontal stride between patches
            - stride_h: The vertical stride between patches
            - num_patches_w: Number of patches in the width dimension
            - num_patches_h: Number of patches in the height dimension
            - width_padded: Width of the padded image needed to make complete patches
            - height_padded: Height of the padded image needed to make complete patches

        Note:
            The function ensures that the image can be split into complete patch_size_w x patch_size_h patches
            by calculating the necessary padding. The horizontal stride between patches is
            patch_size_w - overlap_pixels, and vertically the stride is patch_size_h - overlap_pixels.
        """
        # Get dimensions
        height, width, _ = image_shape
        patch_size_h, patch_size_w = self.patch_size

        # Patch-to-patch stride (patch_size - overlap)
        stride_w = patch_size_w - overlap_pixels
        stride_h = patch_size_h - overlap_pixels

        # Calculate the number of patches in each dimension, allowing an extra possibly imcomplete patch
        # at the end of each dimension.
        num_patches_w = (width - patch_size_w + stride_w - 1) // stride_w + 1
        num_patches_h = (height - patch_size_h + stride_h - 1) // stride_h + 1

        # Calculate the padded dimensions of the image to allow for those incomplete patches.
        width_padded = (num_patches_w - 1) * stride_w + patch_size_w
        height_padded = (num_patches_h - 1) * stride_h + patch_size_h

        return stride_w, stride_h, num_patches_w, num_patches_h, width_padded, height_padded

    def _split_into_patches(self, image: np.ndarray,
                            patch_info: tuple[int, int, int, int, int, int]) -> list[np.ndarray]:
        """
        Split an image into overlapping patch_size_w x patch_size_h patches with reflection padding.

        Args:
            image: Input image as a numpy array of shape (height, width, channels)
            patch_info: Tuple from calculate_patch_info with all the info about how to make the patches

        Returns:
            Array of patches with shape (num_patches, patch_size_h, patch_size_w, channels) where:
            - num_patches = num_patches_w * num_patches_h
            - Each patch is patch_size_w x patch_size_h pixels
            - channels here is the number of output channels of the network

        Note:
            The function pads the input image using reflection padding to ensure
            complete patches at the edges.
        """
        height, width, _ = image.shape

        # Retrieve all the info about how many patches we need, how much padding etc.
        stride_w, stride_h, num_patches_w, num_patches_h, width_padded, height_padded = patch_info
        patch_size_h, patch_size_w = self.patch_size

        # Create padded image with reflection padding
        img_padded = np.pad(
            image,
            ((0, height_padded - height), (0, width_padded - width), (0, 0)),
            mode='reflect'
        )

        # Extract patches.
        patches = []
        for i in range(num_patches_h):
            for j in range(num_patches_w):
                h_start = i * stride_h
                w_start = j * stride_w
                patch = img_padded[h_start:h_start + patch_size_h, w_start:w_start + patch_size_w]
                patches.append(patch)

        return patches

    def _reassemble_patches(
            self,
            output_shape: tuple[int, int, int],
            overlap_pixels: int,
            patch_info: tuple[int, int, int, int, int, int],
            processed_patches: np.ndarray
        ) -> np.ndarray:
        """
        Reassemble processed patches into a single image using linear blending in overlap regions.

        Args:
            image_shape: Tuple of (height, width, channels) of the input image
            overlap_pixels: Number of pixels to overlap between patches
            patch_info: Tuple from calculate_patch_info with all the info about the patches
            processed_patches: Array of processed patches with shape (num_patches, patch_size, patch_size, channels)

        Returns:
            Reassembled image as a numpy array with shape (height, width, channels)

        Note:
            The function uses linear blending in the overlap regions to create smooth transitions
            between patches. The blending weights are generated using a linear ramp from 0 to 1
            across the overlap region. The final image is cropped to the original dimensions
            by removing the padding added during patch extraction.
        """
        height, width, channels = output_shape

        # Get all the patch related info.
        stride_w, stride_h, num_patches_w, num_patches_h, width_padded, height_padded = patch_info
        patch_size_h, patch_size_w = self.patch_size
        # Create output image accumulator
        output_img = np.zeros((height_padded, width_padded, channels), dtype=np.float32)

        # Generate weights for linear blending in the overlap regions.
        weights_w = np.array([1.0] * patch_size_w)
        weights_h = np.array([1.0] * patch_size_h)
        weights_w[:overlap_pixels] = np.linspace(0.0, 1.0, overlap_pixels)
        weights_h[:overlap_pixels] = np.linspace(0.0, 1.0, overlap_pixels)
        weights_left_overlap, weights_top_overlap = np.meshgrid(weights_w, weights_h)
        weights_right_overlap, weights_bottom_overlap = np.meshgrid(weights_w[::-1], weights_h[::-1])
        weights_left_overlap = weights_left_overlap[..., np.newaxis]
        weights_top_overlap = weights_top_overlap[..., np.newaxis]
        weights_right_overlap = weights_right_overlap[..., np.newaxis]
        weights_bottom_overlap = weights_bottom_overlap[..., np.newaxis]

        for i in range(num_patches_h):
            for j in range(num_patches_w):
                patch_idx = i * num_patches_w + j
                h_start = i * stride_h
                w_start = j * stride_w

                patch = processed_patches[patch_idx]
                if i != 0:
                    patch = patch * weights_top_overlap
                if i != num_patches_h - 1:
                    patch = patch * weights_bottom_overlap
                if j != 0:
                    patch = patch * weights_left_overlap
                if j != num_patches_w - 1:
                    patch = patch * weights_right_overlap

                output_img[h_start:h_start + patch_size_h, w_start:w_start + patch_size_w] += patch

        # Remove padding.
        output_img = output_img[:height, :width]

        return output_img

    def _process_patches(self, patches: np.ndarray, show_progress: bool = False, batch_size: int = 1) -> list[np.ndarray]:
        """
        Process patches through the TFLite interpreter.

        Args:
            patches: List of patches; each (patch_size_h, patch_size_w, channels). When channel_first,
                patches are still (H, W, C) and are transposed to (B, C, H, W) before inference.
            show_progress: Whether to show a progress bar (default: False)
            batch_size: Number of patches to process in each batch (default: 1)
        Returns:
            List of processed patches, each (patch_size_h, patch_size_w, channels).
        """
        # Get input and output tensors
        input_details = self.interpreter.get_input_details()
        output_details = self.interpreter.get_output_details()

        # Check if model is quantized (INT8)
        is_quantized = input_details[0]['dtype'] == np.int8

        # Process patches in batches
        processed_patches = []
        total_patches = len(patches)

        # Create progress bar if requested
        if show_progress:
            pbar = tqdm(total=total_patches, desc="Enhancing patches")

        # Process patches in batches
        for i in range(0, total_patches, batch_size):
            end_idx = min(i + batch_size, total_patches)
            batch = np.array(patches[i:end_idx])
            current_batch_size = end_idx - i

            # Transpose (B, H, W, C) -> (B, C, H, W) if network expects channel_first
            if self.channel_first:
                batch = np.transpose(batch, (0, 3, 1, 2))

            # Scale input for INT8 models
            if is_quantized:
                input_scale = input_details[0]['quantization'][0]
                input_zero_point = input_details[0]['quantization'][1]
                batch = (batch / input_scale + input_zero_point).astype(np.int8)

            # The final batch may need padding to reach the batch size.
            if total_patches - i < batch_size:
                batch = np.concatenate([batch, np.zeros((batch_size - (total_patches - i), *batch.shape[1:]), dtype=batch.dtype)],
                    axis=0)
            self.interpreter.set_tensor(input_details[0]['index'], batch)
            self.interpreter.invoke()
            output = self.interpreter.get_tensor(output_details[0]['index'])
            # If the final batch was padded, then the outputs need trimming back.
            if total_patches - i < batch_size:
                output = output[: total_patches - i]

            # De-scale output for INT8 models
            if is_quantized:
                output_scale = output_details[0]['quantization'][0]
                output_zero_point = output_details[0]['quantization'][1]
                output = (output.astype(np.float32) - output_zero_point) * output_scale

            # Transpose (B, C, H, W) -> (B, H, W, C) if network used channel_first
            if self.channel_first:
                output = np.transpose(output, (0, 2, 3, 1))

            output = list(output)
            processed_patches += output

            # Update progress bar
            if show_progress:
                pbar.update(current_batch_size)

        if show_progress:
            pbar.close()

        return processed_patches

    def run_inference(self, image: np.ndarray, overlap_pixels: int = 16, show_progress: bool = False) -> np.ndarray:
        """
        Break the image up into patches, run them all through the neural network model, and
        reassemble them to make the output image.

        Args:
            image: The image to run inference on, shape (height, width, channels)
            overlap_pixels: The number of pixels to overlap between patches
            show_progress: Whether to show a progress bar (default: False)
            batch_size: Number of patches to process in each batch (default: 1)

        Returns:
            The output image.
        """
        if overlap_pixels >= self.patch_size[0] or overlap_pixels >= self.patch_size[1]:
            raise ValueError("Overlap pixels must be less than the patch size")
        # This tells us how many patches we will need, how much to pad the image etc.
        patch_info = self._calculate_patch_info(image.shape, overlap_pixels)
        # Break the image up into patches.
        patches = self._split_into_patches(image, patch_info)
        # Run the patches through the neural network model.
        outputs = self._process_patches(patches, show_progress, self.batch_size) # This is the slow part.
        # Reassemble the patches to make the output image.
        output_details = self.interpreter.get_output_details()[0]['shape']
        if self.channel_first:
            # Output tensor is [B, C, H, W]; image is (H, W, C)
            output_shape = (image.shape[0], image.shape[1], output_details[1])
        else:
            # Output tensor is [B, H, W, C]
            output_shape = (image.shape[0], image.shape[1], output_details[-1])
        output_image = self._reassemble_patches(output_shape, overlap_pixels, patch_info, outputs)
        return output_image
