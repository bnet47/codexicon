"""Synthetic viewport helpers with a misleading content-width defect."""


def content_size(width, height, chrome, footer):
    """Return content dimensions after browser chrome and footer deductions."""

    return (width - 2 * chrome, height - footer)


def asset_bounds(width, height, border):
    """Return the outer asset bounds, including the border on both sides."""

    return (width + 2 * border, height + 2 * border)
