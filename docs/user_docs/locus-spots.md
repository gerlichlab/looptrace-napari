## Viewing locus spots

### Quickstart
To visualise the locus-specific spots masks, you need to __drag-and-drop files__ into an active Napari window. 
1. First, drag one of the `PXXXX.zarr` files--from the `locus_spots_visualisation` (previously `locus_spot_images`) subfolder in your analysis folder from `looptrace`--into Napari.
1. Choose to open the ZARR with the Napari native plugin(s) / readers, not this plugin's.
1. Select "continuous" for the value of the "auto-contrast" option in the upper-left panel of the Napari window.
1. Second, drag a the corresponding (by field of view) pair of `*qcpass.csv` and `*qcfail.csv` files into Napari.
1. Choose to open these QC pass/fail CSVs with this plugin rather than Napari builtins.

### What you should see
A Napari window with a three sliders and three layers (QC pass, QC fail, and pixel data).
- Bottom slider: ROI/trace
- Middle slider: imaging timepoint
- Top slider: slice in `z`

### Details and troubleshooting
__Scrolling__

In version 0.2 of this plugin, there's an image plane for every z-slice, for every timepoint, for every ROI in the particular field of view. 
This can makes scrolling time-consuming and will be simplified in a future release. 

__Finding points (centers of Gaussian fits to pixel volume)__

In version 0.3 of this plugin, points should be visible throughout each z-stack, and the color of point which passed QC has been changed from red to yellow. 
The shape is an star in the $z$ slice closest to the center of the Gaussian fit to a pixel volume, and a circle in other $z$ slices. 
In this version, then, shape relates to $z$ position rather than to QC status; we allow point color to disambiguate QC status.

In version 0.2 of this plugin, a point (blue or red indicator) can only be visible only in the z-slice closest to the z-coordinate of the the center of the Gaussian fit to a particular pixel volume. Generally, these will be more toward the middle of the z-stack rather than at either end, so focus scrolling mainly through the midrange of the z-axis.

### Frequently asked questions (FAQ)
1. Why do point centers appear _slightly_ off (thinking about subpixel resolution)?\
    We think this comes from the fact that Napari is regarding the _center_ of the upper-left pixel as the origin, rather than the upper-left corner of the upper-left pixel.
