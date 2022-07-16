import functools
import operator
import re

import numpy as np
from talon.experimental import ocr

from . import _base


class TalonBackend(_base.OcrBackend):
    def run_ocr(self, image):
        results = ocr.ocr(image)
        array = np.array(image)
        grayscale = (
            0.299 * array[:, :, 0] + 0.587 * array[:, :, 1] + 0.114 * array[:, :, 2]
        )
        lines = [
            _base.OcrLine(
                [
                    _base.OcrWord(
                        match.group(),
                        *self._adjust_box(
                            functools.reduce(
                                operator.add,
                                result.bounds.rects[match.start() : match.end()],
                            ),
                            grayscale,
                            image.rect.x,
                            image.rect.y,
                        ),
                    )
                    for match in re.finditer(r"\S+", result.text)
                ]
            )
            for result in results
        ]
        return _base.OcrResult(lines)

    @staticmethod
    def _adjust_box(rect, image, x_offset, y_offset):
        """Fix bounding box so it is tight and relative to the cropped image,
        not the full screenshot.
        """
        # Adjust coordinates to be relative to the cropped image.
        left = rect.x - x_offset
        top = rect.y - y_offset
        width = rect.width
        height = rect.height
        # Add left and right padding to ensure some whitespace is included
        # before we tighten. It's okay if an adjacent character is partially
        # included as well.
        padding = 2
        left_column = max(0, min(image.shape[1] - 1, round(left) - padding))
        top_row = max(0, min(image.shape[0] - 1, round(top)))
        right_column = max(
            0, min(image.shape[1] - 1, round(left + width - 1) + padding)
        )
        bottom_row = max(0, min(image.shape[0] - 1, round(top + height - 1)))
        patch = image[top_row : bottom_row + 1, left_column : right_column + 1]
        # Apply mean thresholding to separate text from background.
        thresholded = patch > patch.mean()
        # Adjust polarity so that text is True and background is False.
        # Assumes background color is more common than text color.
        binarized = (
            thresholded
            if np.count_nonzero(thresholded) < thresholded.size / 2
            else ~thresholded
        )
        columns_with_text = binarized.any(axis=0)
        # Search for left side as first text after background. This will also
        # work if no background is present, because first_background will be 0.
        first_background = columns_with_text.argmin()
        first_text = columns_with_text[first_background:].argmax() + first_background
        # Do the same thing but flipped left-to-right to get the right side.
        flipped = columns_with_text[::-1]
        flipped_first_background = flipped.argmin()
        flipped_first_text = (
            flipped[flipped_first_background:].argmax() + flipped_first_background
        )
        # Unflip the index.
        last_text = (columns_with_text.size - 1) - flipped_first_text
        return (
            left_column + first_text,  # left
            top,
            last_text - first_text + 1,  # width
            height,
        )
